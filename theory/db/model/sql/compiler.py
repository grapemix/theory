import datetime

from theory.conf import settings
from theory.core.exceptions import FieldError
from theory.db.backends.utils import truncateName
from theory.db.model.constants import LOOKUP_SEP
from theory.db.model.expressions import ExpressionNode
from theory.db.model.queryUtils import selectRelatedDescend, QueryWrapper
from theory.db.model.sql.constants import (CURSOR, SINGLE, MULTI, NO_RESULTS,
    ORDER_DIR, GET_ITERATOR_CHUNK_SIZE, SelectInfo)
from theory.db.model.sql.datastructures import EmptyResultSet
from theory.db.model.sql.expressions import SQLEvaluator
from theory.db.model.sql.query import getOrderDir, Query
from theory.db.transaction import TransactionManagementError
from theory.db.utils import DatabaseError
from theory.utils import six
from theory.utils.six.moves import zip
from theory.utils import timezone


class SQLCompiler(object):
  def __init__(self, query, connection, using):
    self.query = query
    self.connection = connection
    self.using = using
    self.quoteCache = {'*': '*'}
    # When ordering a queryset with distinct on a column not part of the
    # select set, the ordering column needs to be added to the select
    # clause. This information is needed both in SQL construction and
    # masking away the ordering selects from the returned row.
    self.orderingAliases = []
    self.orderingParams = []

  def preSqlSetup(self):
    """
    Does any necessary class setup immediately prior to producing SQL. This
    is for things that can't necessarily be done in __init__ because we
    might not have all the pieces in place at that time.
    # TODO: after the query has been executed, the altered state should be
    # cleaned. We are not using a clone() of the query here.
    """
    if not self.query.tables:
      self.query.join((None, self.query.getMeta().dbTable, None))
    if (not self.query.select and self.query.defaultCols and not
        self.query.includedInheritedModels):
      self.query.setupInheritedModels()
    if self.query.selectRelated and not self.query.relatedSelectCols:
      self.fillRelatedSelections()

  def __call__(self, name):
    """
    A wrapper around connection.ops.quoteName that doesn't quote aliases
    for table names. This avoids problems with some SQL dialects that treat
    quoted strings specially (e.g. PostgreSQL).
    """
    if name in self.quoteCache:
      return self.quoteCache[name]
    if ((name in self.query.aliasMap and name not in self.query.tableMap) or
        name in self.query.extraSelect):
      self.quoteCache[name] = name
      return name
    r = self.connection.ops.quoteName(name)
    self.quoteCache[name] = r
    return r

  def quoteNameUnlessAlias(self, name):
    """
    A wrapper around connection.ops.quoteName that doesn't quote aliases
    for table names. This avoids problems with some SQL dialects that treat
    quoted strings specially (e.g. PostgreSQL).
    """
    return self(name)

  def compile(self, node):
    vendorImpl = getattr(
      node, 'as_' + self.connection.vendor, None)
    if vendorImpl:
      return vendorImpl(self, self.connection)
    else:
      return node.asSql(self, self.connection)

  def asSql(self, withLimits=True, withColAliases=False):
    """
    Creates the SQL for this query. Returns the SQL string and list of
    parameters.

    If 'withLimits' is False, any limit/offset information is not included
    in the query.
    """
    if withLimits and self.query.lowMark == self.query.highMark:
      return '', ()

    self.preSqlSetup()
    # After executing the query, we must get rid of any joins the query
    # setup created. So, take note of alias counts before the query ran.
    # However we do not want to get rid of stuff done in preSqlSetup(),
    # as the preSqlSetup will modify query state in a way that forbids
    # another run of it.
    self.refcountsBefore = self.query.aliasRefcount.copy()
    outCols, sParams = self.getColumns(withColAliases)
    ordering, oParams, orderingGroupBy = self.getOrdering()

    distinctFields = self.getDistinct()

    # This must come after 'select', 'ordering' and 'distinct' -- see
    # docstring of getFromClause() for details.
    from_, fParams = self.getFromClause()

    where, wParams = self.compile(self.query.where)
    having, hParams = self.compile(self.query.having)
    havingGroupBy = self.query.having.getGroupByCols()
    params = []
    for val in six.itervalues(self.query.extraSelect):
      params.extend(val[1])

    result = ['SELECT']

    if self.query.distinct:
      result.append(self.connection.ops.distinctSql(distinctFields))

    result.append(', '.join(outCols + self.orderingAliases))
    params.extend(sParams)
    params.extend(self.orderingParams)

    result.append('FROM')
    result.extend(from_)
    params.extend(fParams)

    if where:
      result.append('WHERE %s' % where)
      params.extend(wParams)

    grouping, gbParams = self.getGrouping(havingGroupBy, orderingGroupBy)
    if grouping:
      if distinctFields:
        raise NotImplementedError(
          "annotate() + distinct(fields) not implemented.")
      if not ordering:
        ordering = self.connection.ops.forceNoOrdering()
      result.append('GROUP BY %s' % ', '.join(grouping))
      params.extend(gbParams)

    if having:
      result.append('HAVING %s' % having)
      params.extend(hParams)

    if ordering:
      result.append('ORDER BY %s' % ', '.join(ordering))
      params.extend(oParams)

    if withLimits:
      if self.query.highMark is not None:
        result.append('LIMIT %d' % (self.query.highMark - self.query.lowMark))
      if self.query.lowMark:
        if self.query.highMark is None:
          val = self.connection.ops.noLimitValue()
          if val:
            result.append('LIMIT %d' % val)
        result.append('OFFSET %d' % self.query.lowMark)

    if self.query.selectForUpdate and self.connection.features.hasSelectForUpdate:
      if self.connection.getAutocommit():
        raise TransactionManagementError("selectForUpdate cannot be used outside of a transaction.")

      # If we've been asked for a NOWAIT query but the backend does not support it,
      # raise a DatabaseError otherwise we could get an unexpected deadlock.
      nowait = self.query.selectForUpdateNowait
      if nowait and not self.connection.features.hasSelectForUpdateNowait:
        raise DatabaseError('NOWAIT is not supported on this database backend.')
      result.append(self.connection.ops.forUpdateSql(nowait=nowait))

    # Finally do cleanup - get rid of the joins we created above.
    self.query.resetRefcounts(self.refcountsBefore)

    return ' '.join(result), tuple(params)

  def asNestedSql(self):
    """
    Perform the same functionality as the asSql() method, returning an
    SQL string and parameters. However, the alias prefixes are bumped
    beforehand (in a copy -- the current query isn't changed), and any
    ordering is removed if the query is unsliced.

    Used when nesting this query inside another.
    """
    obj = self.query.clone()
    if obj.lowMark == 0 and obj.highMark is None and not self.query.distinctFields:
      # If there is no slicing in use, then we can safely drop all ordering
      obj.clearOrdering(True)
    return obj.getCompiler(connection=self.connection).asSql()

  def getColumns(self, withAliases=False):
    """
    Returns the list of columns to use in the select statement, as well as
    a list any extra parameters that need to be included. If no columns
    have been specified, returns all columns relating to fields in the
    modal.

    If 'withAliases' is true, any column names that are duplicated
    (without the table names) are given unique aliases. This is needed in
    some cases to avoid ambiguity with nested queries.
    """
    qn = self
    qn2 = self.connection.ops.quoteName
    result = ['(%s) AS %s' % (col[0], qn2(alias)) for alias, col in six.iteritems(self.query.extraSelect)]
    params = []
    aliases = set(self.query.extraSelect.keys())
    if withAliases:
      colAliases = aliases.copy()
    else:
      colAliases = set()
    if self.query.select:
      onlyLoad = self.deferredToColumns()
      for col, _ in self.query.select:
        if isinstance(col, (list, tuple)):
          alias, column = col
          table = self.query.aliasMap[alias].tableName
          if table in onlyLoad and column not in onlyLoad[table]:
            continue
          r = '%s.%s' % (qn(alias), qn(column))
          if withAliases:
            if col[1] in colAliases:
              cAlias = 'Col%d' % len(colAliases)
              result.append('%s AS %s' % (r, cAlias))
              aliases.add(cAlias)
              colAliases.add(cAlias)
            else:
              result.append('%s AS %s' % (r, qn2(col[1])))
              aliases.add(r)
              colAliases.add(col[1])
          else:
            result.append(r)
            aliases.add(r)
            colAliases.add(col[1])
        else:
          colSql, colParams = self.compile(col)
          result.append(colSql)
          params.extend(colParams)

          if hasattr(col, 'alias'):
            aliases.add(col.alias)
            colAliases.add(col.alias)

    elif self.query.defaultCols:
      cols, newAliases = self.getDefaultColumns(withAliases,
          colAliases)
      result.extend(cols)
      aliases.update(newAliases)

    maxNameLength = self.connection.ops.maxNameLength()
    for alias, aggregate in self.query.aggregateSelect.items():
      aggSql, aggParams = self.compile(aggregate)
      if alias is None:
        result.append(aggSql)
      else:
        result.append('%s AS %s' % (aggSql, qn(truncateName(alias, maxNameLength))))
      params.extend(aggParams)

    for (table, col), _ in self.query.relatedSelectCols:
      r = '%s.%s' % (qn(table), qn(col))
      if withAliases and col in colAliases:
        cAlias = 'Col%d' % len(colAliases)
        result.append('%s AS %s' % (r, cAlias))
        aliases.add(cAlias)
        colAliases.add(cAlias)
      else:
        result.append(r)
        aliases.add(r)
        colAliases.add(col)

    self._selectAliases = aliases
    return result, params

  def getDefaultColumns(self, withAliases=False, colAliases=None,
      startAlias=None, opts=None, asPairs=False, fromParent=None):
    """
    Computes the default columns for selecting every field in the base
    modal. Will sometimes be called to pull in related model (e.g. via
    selectRelated), in which case "opts" and "startAlias" will be given
    to provide a starting point for the traversal.

    Returns a list of strings, quoted appropriately for use in SQL
    directly, as well as a set of aliases used in the select statement (if
    'asPairs' is True, returns a list of (alias, colName) pairs instead
    of strings as the first component and None as the second component).
    """
    result = []
    if opts is None:
      opts = self.query.getMeta()
    qn = self
    qn2 = self.connection.ops.quoteName
    aliases = set()
    onlyLoad = self.deferredToColumns()
    if not startAlias:
      startAlias = self.query.getInitialAlias()
    # The 'seenModels' is used to optimize checking the needed parent
    # alias for a given field. This also includes None -> startAlias to
    # be used by local fields.
    seenModels = {None: startAlias}

    for field, modal in opts.getConcreteFieldsWithModel():
      if fromParent and modal is not None and issubclass(fromParent, modal):
        # Avoid loading data for already loaded parents.
        continue
      alias = self.query.joinParentModel(opts, modal, startAlias,
                         seenModels)
      column = field.column
      for seenModel, seenAlias in seenModels.items():
        if seenModel and seenAlias == alias:
          ancestorLink = seenModel._meta.getAncestorLink(modal)
          if ancestorLink:
            column = ancestorLink.column
          break
      table = self.query.aliasMap[alias].tableName
      if table in onlyLoad and column not in onlyLoad[table]:
        continue
      if asPairs:
        result.append((alias, field))
        aliases.add(alias)
        continue
      if withAliases and column in colAliases:
        cAlias = 'Col%d' % len(colAliases)
        result.append('%s.%s AS %s' % (qn(alias),
          qn2(column), cAlias))
        colAliases.add(cAlias)
        aliases.add(cAlias)
      else:
        r = '%s.%s' % (qn(alias), qn2(column))
        result.append(r)
        aliases.add(r)
        if withAliases:
          colAliases.add(column)
    return result, aliases

  def getDistinct(self):
    """
    Returns a quoted list of fields to use in DISTINCT ON part of the query.

    Note that this method can alter the tables in the query, and thus it
    must be called before getFromClause().
    """
    qn = self
    qn2 = self.connection.ops.quoteName
    result = []
    opts = self.query.getMeta()

    for name in self.query.distinctFields:
      parts = name.split(LOOKUP_SEP)
      _, targets, alias, joins, path, _ = self._setupJoins(parts, opts, None)
      targets, alias, _ = self.query.trimJoins(targets, joins, path)
      for target in targets:
        result.append("%s.%s" % (qn(alias), qn2(target.column)))
    return result

  def getOrdering(self):
    """
    Returns a tuple containing a list representing the SQL elements in the
    "order by" clause, and the list of SQL elements that need to be added
    to the GROUP BY clause as a result of the ordering.

    Also sets the orderingAliases attribute on this instance to a list of
    extra aliases needed in the select.

    Determining the ordering SQL can change the tables we need to include,
    so this should be run *before* getFromClause().
    """
    if self.query.extraOrderBy:
      ordering = self.query.extraOrderBy
    elif not self.query.defaultOrdering:
      ordering = self.query.orderBy
    else:
      ordering = (self.query.orderBy
            or self.query.getMeta().ordering
            or [])
    qn = self
    qn2 = self.connection.ops.quoteName
    distinct = self.query.distinct
    selectAliases = self._selectAliases
    result = []
    groupBy = []
    orderingAliases = []
    if self.query.standardOrdering:
      asc, desc = ORDER_DIR['ASC']
    else:
      asc, desc = ORDER_DIR['DESC']

    # It's possible, due to modal inheritance, that normal usage might try
    # to include the same field more than once in the ordering. We track
    # the table/column pairs we use and discard any after the first use.
    processedPairs = set()

    params = []
    orderingParams = []
    # For plain DISTINCT queries any ORDER BY clause must appear
    # in SELECT clause.
    # http://www.postgresql.org/message-id/27009.1171559417@sss.pgh.pa.us
    mustAppendToSelect = distinct and not self.query.distinctFields
    for pos, field in enumerate(ordering):
      if field == '?':
        result.append(self.connection.ops.randomFunctionSql())
        continue
      if isinstance(field, int):
        if field < 0:
          order = desc
          field = -field
        else:
          order = asc
        result.append('%s %s' % (field, order))
        groupBy.append((str(field), []))
        continue
      col, order = getOrderDir(field, asc)
      if col in self.query.aggregateSelect:
        result.append('%s %s' % (qn(col), order))
        continue
      if '.' in field:
        # This came in through an extra(orderBy=...) addition. Pass it
        # on verbatim.
        table, col = col.split('.', 1)
        if (table, col) not in processedPairs:
          elt = '%s.%s' % (qn(table), col)
          processedPairs.add((table, col))
          if not mustAppendToSelect or elt in selectAliases:
            result.append('%s %s' % (elt, order))
            groupBy.append((elt, []))
      elif not self.query._extra or getOrderDir(field)[0] not in self.query._extra:
        # 'col' is of the form 'field' or 'field1__field2' or
        # '-field1__field2__field', etc.
        for table, cols, order in self.findOrderingName(field,
            self.query.getMeta(), defaultOrder=asc):
          for col in cols:
            if (table, col) not in processedPairs:
              elt = '%s.%s' % (qn(table), qn2(col))
              processedPairs.add((table, col))
              if mustAppendToSelect and elt not in selectAliases:
                orderingAliases.append(elt)
              result.append('%s %s' % (elt, order))
              groupBy.append((elt, []))
      else:
        elt = qn2(col)
        if col not in self.query.extraSelect:
          if mustAppendToSelect:
            sql = "(%s) AS %s" % (self.query.extra[col][0], elt)
            orderingAliases.append(sql)
            orderingParams.extend(self.query.extra[col][1])
            result.append('%s %s' % (elt, order))
          else:
            result.append("(%s) %s" % (self.query.extra[col][0], order))
            params.extend(self.query.extra[col][1])
        else:
          result.append('%s %s' % (elt, order))
        groupBy.append(self.query.extra[col])
    self.orderingAliases = orderingAliases
    self.orderingParams = orderingParams
    return result, params, groupBy

  def findOrderingName(self, name, opts, alias=None, defaultOrder='ASC',
              alreadySeen=None):
    """
    Returns the table alias (the name might be ambiguous, the alias will
    not be) and column name for ordering by the given 'name' parameter.
    The 'name' is of the form 'field1__field2__...__fieldN'.
    """
    name, order = getOrderDir(name, defaultOrder)
    pieces = name.split(LOOKUP_SEP)
    field, targets, alias, joins, path, opts = self._setupJoins(pieces, opts, alias)

    # If we get to this point and the field is a relation to another modal,
    # append the default ordering for that modal unless the attribute name
    # of the field is specified.
    if field.rel and path and opts.ordering and name != field.attname:
      # Firstly, avoid infinite loops.
      if not alreadySeen:
        alreadySeen = set()
      joinTuple = tuple(self.query.aliasMap[j].tableName for j in joins)
      if joinTuple in alreadySeen:
        raise FieldError('Infinite loop caused by ordering.')
      alreadySeen.add(joinTuple)

      results = []
      for item in opts.ordering:
        results.extend(self.findOrderingName(item, opts, alias,
                            order, alreadySeen))
      return results
    targets, alias, _ = self.query.trimJoins(targets, joins, path)
    return [(alias, [t.column for t in targets], order)]

  def _setupJoins(self, pieces, opts, alias):
    """
    A helper method for getOrdering and getDistinct.

    Note that getOrdering and getDistinct must produce same target
    columns on same input, as the prefixes of getOrdering and getDistinct
    must match. Executing SQL where this is not true is an error.
    """
    if not alias:
      alias = self.query.getInitialAlias()
    field, targets, opts, joins, path = self.query.setupJoins(
      pieces, opts, alias)
    alias = joins[-1]
    return field, targets, alias, joins, path, opts

  def getFromClause(self):
    """
    Returns a list of strings that are joined together to go after the
    "FROM" part of the query, as well as a list any extra parameters that
    need to be included. Sub-classes, can override this to create a
    from-clause via a "select".

    This should only be called after any SQL construction methods that
    might change the tables we need. This means the select columns,
    ordering and distinct must be done first.
    """
    result = []
    qn = self
    qn2 = self.connection.ops.quoteName
    first = True
    fromParams = []
    for alias in self.query.tables:
      if not self.query.aliasRefcount[alias]:
        continue
      try:
        name, alias, joinType, lhs, joinCols, _, joinField = self.query.aliasMap[alias]
      except KeyError:
        # Extra tables can end up in self.tables, but not in the
        # aliasMap if they aren't in a join. That's OK. We skip them.
        continue
      aliasStr = '' if alias == name else (' %s' % alias)
      if joinType and not first:
        extraCond = joinField.getExtraRestriction(
          self.query.whereClass, alias, lhs)
        if extraCond:
          extraSql, extraParams = self.compile(extraCond)
          extraSql = 'AND (%s)' % extraSql
          fromParams.extend(extraParams)
        else:
          extraSql = ""
        result.append('%s %s%s ON ('
            % (joinType, qn(name), aliasStr))
        for index, (lhsCol, rhsCol) in enumerate(joinCols):
          if index != 0:
            result.append(' AND ')
          result.append('%s.%s = %s.%s' %
          (qn(lhs), qn2(lhsCol), qn(alias), qn2(rhsCol)))
        result.append('%s)' % extraSql)
      else:
        connector = '' if first else ', '
        result.append('%s%s%s' % (connector, qn(name), aliasStr))
      first = False
    for t in self.query.extraTables:
      alias, unused = self.query.tableAlias(t)
      # Only add the alias if it's not already present (the tableAlias()
      # calls increments the refcount, so an alias refcount of one means
      # this is the only reference.
      if alias not in self.query.aliasMap or self.query.aliasRefcount[alias] == 1:
        connector = '' if first else ', '
        result.append('%s%s' % (connector, qn(alias)))
        first = False
    return result, fromParams

  def getGrouping(self, havingGroupBy, orderingGroupBy):
    """
    Returns a tuple representing the SQL elements in the "group by" clause.
    """
    qn = self
    result, params = [], []
    if self.query.groupBy is not None:
      selectCols = self.query.select + self.query.relatedSelectCols
      # Just the column, not the fields.
      selectCols = [s[0] for s in selectCols]
      if (len(self.query.getMeta().concreteFields) == len(self.query.select)
          and self.connection.features.allowsGroupByPk):
        self.query.groupBy = [
          (self.query.getMeta().dbTable, self.query.getMeta().pk.column)
        ]
        selectCols = []
      seen = set()
      cols = self.query.groupBy + havingGroupBy + selectCols
      for col in cols:
        colParams = ()
        if isinstance(col, (list, tuple)):
          sql = '%s.%s' % (qn(col[0]), qn(col[1]))
        elif hasattr(col, 'asSql'):
          self.compile(col)
        else:
          sql = '(%s)' % str(col)
        if sql not in seen:
          result.append(sql)
          params.extend(colParams)
          seen.add(sql)

      # Still, we need to add all stuff in ordering (except if the backend can
      # group by just by PK).
      if orderingGroupBy and not self.connection.features.allowsGroupByPk:
        for order, orderParams in orderingGroupBy:
          # Even if we have seen the same SQL string, it might have
          # different params, so, we add same SQL in "has params" case.
          if order not in seen or orderParams:
            result.append(order)
            params.extend(orderParams)
            seen.add(order)

      # Unconditionally add the extraSelect items.
      for extraSelect, extraParams in self.query.extraSelect.values():
        sql = '(%s)' % str(extraSelect)
        result.append(sql)
        params.extend(extraParams)

    return result, params

  def fillRelatedSelections(self, opts=None, rootAlias=None, curDepth=1,
      requested=None, restricted=None):
    """
    Fill in the information needed for a selectRelated query. The current
    depth is measured as the number of connections away from the root modal
    (for example, curDepth=1 means we are looking at model with direct
    connections to the root modal).
    """
    if not restricted and self.query.maxDepth and curDepth > self.query.maxDepth:
      # We've recursed far enough; bail out.
      return

    if not opts:
      opts = self.query.getMeta()
      rootAlias = self.query.getInitialAlias()
      self.query.relatedSelectCols = []
    onlyLoad = self.query.getLoadedFieldNames()

    # Setup for the case when only particular related fields should be
    # included in the related selection.
    if requested is None:
      if isinstance(self.query.selectRelated, dict):
        requested = self.query.selectRelated
        restricted = True
      else:
        restricted = False

    for f, modal in opts.getFieldsWithModel():
      # The getFieldsWithModel() returns None for fields that live
      # in the field's local modal. So, for those fields we want to use
      # the f.modal - that is the field's local modal.
      fieldModel = modal or f.modal
      if not selectRelatedDescend(f, restricted, requested,
                     onlyLoad.get(fieldModel)):
        continue
      _, _, _, joins, _ = self.query.setupJoins(
        [f.name], opts, rootAlias)
      alias = joins[-1]
      columns, _ = self.getDefaultColumns(startAlias=alias,
          opts=f.rel.to._meta, asPairs=True)
      self.query.relatedSelectCols.extend(
        SelectInfo((col[0], col[1].column), col[1]) for col in columns)
      if restricted:
        next = requested.get(f.name, {})
      else:
        next = False
      self.fillRelatedSelections(f.rel.to._meta, alias, curDepth + 1,
          next, restricted)

    if restricted:
      relatedFields = [
        (o.field, o.modal)
        for o in opts.getAllRelatedObjects()
        if o.field.unique
      ]
      for f, modal in relatedFields:
        if not selectRelatedDescend(f, restricted, requested,
                       onlyLoad.get(modal), reverse=True):
          continue

        _, _, _, joins, _ = self.query.setupJoins(
          [f.relatedQueryName()], opts, rootAlias)
        alias = joins[-1]
        fromParent = (opts.modal if issubclass(modal, opts.modal)
                else None)
        columns, _ = self.getDefaultColumns(startAlias=alias,
          opts=modal._meta, asPairs=True, fromParent=fromParent)
        self.query.relatedSelectCols.extend(
          SelectInfo((col[0], col[1].column), col[1]) for col in columns)
        next = requested.get(f.relatedQueryName(), {})
        self.fillRelatedSelections(modal._meta, alias, curDepth + 1,
                       next, restricted)

  def deferredToColumns(self):
    """
    Converts the self.deferredLoading data structure to mapping of table
    names to sets of column names which are to be loaded. Returns the
    dictionary.
    """
    columns = {}
    self.query.deferredToData(columns, self.query.deferredToColumnsCb)
    return columns

  def resultsIter(self):
    """
    Returns an iterator over the results from executing this query.
    """
    resolveColumns = hasattr(self, 'resolveColumns')
    fields = None
    hasAggregateSelect = bool(self.query.aggregateSelect)
    for rows in self.executeSql(MULTI):
      for row in rows:
        if hasAggregateSelect:
          loadedFields = self.query.getLoadedFieldNames().get(self.query.modal, set()) or self.query.select
          aggregateStart = len(self.query.extraSelect) + len(loadedFields)
          aggregateEnd = aggregateStart + len(self.query.aggregateSelect)
        if resolveColumns:
          if fields is None:
            # We only set this up here because
            # relatedSelectCols isn't populated until
            # executeSql() has been called.

            # We also include types of fields of related model that
            # will be included via selectRelated() for the benefit
            # of MySQL/MySQLdb when boolean fields are involved
            # (#15040).

            # This code duplicates the logic for the order of fields
            # found in getColumns(). It would be nice to clean this up.
            if self.query.select:
              fields = [f.field for f in self.query.select]
            elif self.query.defaultCols:
              fields = self.query.getMeta().concreteFields
            else:
              fields = []
            fields = fields + [f.field for f in self.query.relatedSelectCols]

            # If the field was deferred, exclude it from being passed
            # into `resolveColumns` because it wasn't selected.
            onlyLoad = self.deferredToColumns()
            if onlyLoad:
              fields = [f for f in fields if f.modal._meta.dbTable not in onlyLoad or
                   f.column in onlyLoad[f.modal._meta.dbTable]]
            if hasAggregateSelect:
              # pad None in to fields for aggregates
              fields = fields[:aggregateStart] + [
                None for x in range(0, aggregateEnd - aggregateStart)
              ] + fields[aggregateStart:]
          row = self.resolveColumns(row, fields)

        if hasAggregateSelect:
          row = tuple(row[:aggregateStart]) + tuple(
            self.query.resolveAggregate(value, aggregate, self.connection)
            for (alias, aggregate), value
            in zip(self.query.aggregateSelect.items(), row[aggregateStart:aggregateEnd])
          ) + tuple(row[aggregateEnd:])

        yield row

  def hasResults(self):
    """
    Backends (e.g. NoSQL) can override this in order to use optimized
    versions of "query has any results."
    """
    # This is always executed on a query clone, so we can modify self.query
    self.query.addExtra({'a': 1}, None, None, None, None, None)
    self.query.setExtraMask(['a'])
    return bool(self.executeSql(SINGLE))

  def executeSql(self, resultType=MULTI):
    """
    Run the query against the database and returns the result(s). The
    return value is a single data item if resultType is SINGLE, or an
    iterator over the results if the resultType is MULTI.

    resultType is either MULTI (use fetchmany() to retrieve all rows),
    SINGLE (only retrieve a single row), or None. In this last case, the
    cursor is returned if any query is executed, since it's used by
    subclasses such as InsertQuery). It's possible, however, that no query
    is needed, as the filters describe an empty set. In that case, None is
    returned, to avoid any unnecessary database interaction.
    """
    if not resultType:
      resultType = NO_RESULTS
    try:
      sql, params = self.asSql()
      if not sql:
        raise EmptyResultSet
    except EmptyResultSet:
      if resultType == MULTI:
        return iter([])
      else:
        return

    cursor = self.connection.cursor()
    try:
      cursor.execute(sql, params)
    except Exception:
      cursor.close()
      raise

    if resultType == CURSOR:
      # Caller didn't specify a resultType, so just give them back the
      # cursor to process (and close).
      return cursor
    if resultType == SINGLE:
      try:
        if self.orderingAliases:
          return cursor.fetchone()[:-len(self.orderingAliases)]
        return cursor.fetchone()
      finally:
        # done with the cursor
        cursor.close()
    if resultType == NO_RESULTS:
      cursor.close()
      return

    # The MULTI case.
    if self.orderingAliases:
      result = orderModifiedIter(cursor, len(self.orderingAliases),
          self.connection.features.emptyFetchmanyValue)
    else:
      result = cursorIter(cursor,
        self.connection.features.emptyFetchmanyValue)
    if not self.connection.features.canUseChunkedReads:
      try:
        # If we are using non-chunked reads, we return the same data
        # structure as normally, but ensure it is all read into memory
        # before going any further.
        return list(result)
      finally:
        # done with the cursor
        cursor.close()
    return result

  def asSubqueryCondition(self, alias, columns, qn):
    innerQn = self
    qn2 = self.connection.ops.quoteName
    if len(columns) == 1:
      sql, params = self.asSql()
      return '%s.%s IN (%s)' % (qn(alias), qn2(columns[0]), sql), params

    for index, selectCol in enumerate(self.query.select):
      lhs = '%s.%s' % (innerQn(selectCol.col[0]), qn2(selectCol.col[1]))
      rhs = '%s.%s' % (qn(alias), qn2(columns[index]))
      self.query.where.add(
        QueryWrapper('%s = %s' % (lhs, rhs), []), 'AND')

    sql, params = self.asSql()
    return 'EXISTS (%s)' % sql, params


class SQLInsertCompiler(SQLCompiler):

  def __init__(self, *args, **kwargs):
    self.returnId = False
    super(SQLInsertCompiler, self).__init__(*args, **kwargs)

  def placeholder(self, field, val):
    if field is None:
      # A field value of None means the value is raw.
      return val
    elif hasattr(field, 'getPlaceholder'):
      # Some fields (e.g. geo fields) need special munging before
      # they can be inserted.
      return field.getPlaceholder(val, self.connection)
    else:
      # Return the common case for the placeholder
      return '%s'

  def asSql(self):
    # We don't need quoteNameUnlessAlias() here, since these are all
    # going to be column names (so we can avoid the extra overhead).
    qn = self.connection.ops.quoteName
    opts = self.query.getMeta()
    result = ['INSERT INTO %s' % qn(opts.dbTable)]

    hasFields = bool(self.query.fields)
    fields = self.query.fields if hasFields else [opts.pk]
    result.append('(%s)' % ', '.join(qn(f.column) for f in fields))

    if hasFields:
      params = values = [
        [
          f.getDbPrepSave(getattr(obj, f.attname) if self.query.raw else f.preSave(obj, True), connection=self.connection)
          for f in fields
        ]
        for obj in self.query.objs
      ]
    else:
      values = [[self.connection.ops.pkDefaultValue()] for obj in self.query.objs]
      params = [[]]
      fields = [None]
    canBulk = (not any(hasattr(field, "getPlaceholder") for field in fields) and
      not self.returnId and self.connection.features.hasBulkInsert)

    if canBulk:
      placeholders = [["%s"] * len(fields)]
    else:
      placeholders = [
        [self.placeholder(field, v) for field, v in zip(fields, val)]
        for val in values
      ]
      # Oracle Spatial needs to remove some values due to #10888
      params = self.connection.ops.modifyInsertParams(placeholders, params)
    if self.returnId and self.connection.features.canReturnIdFromInsert:
      params = params[0]
      col = "%s.%s" % (qn(opts.dbTable), qn(opts.pk.column))
      result.append("VALUES (%s)" % ", ".join(placeholders[0]))
      rFmt, rParams = self.connection.ops.returnInsertId()
      # Skip empty rFmt to allow subclasses to customize behavior for
      # 3rd party backends. Refs #19096.
      if rFmt:
        result.append(rFmt % col)
        params += rParams
      return [(" ".join(result), tuple(params))]
    if canBulk:
      result.append(self.connection.ops.bulkInsertSql(fields, len(values)))
      return [(" ".join(result), tuple(v for val in values for v in val))]
    else:
      return [
        (" ".join(result + ["VALUES (%s)" % ", ".join(p)]), vals)
        for p, vals in zip(placeholders, params)
      ]

  def executeSql(self, returnId=False):
    assert not (returnId and len(self.query.objs) != 1)
    self.returnId = returnId
    with self.connection.cursor() as cursor:
      for sql, params in self.asSql():
        cursor.execute(sql, params)
      if not (returnId and cursor):
        return
      if self.connection.features.canReturnIdFromInsert:
        return self.connection.ops.fetchReturnedInsertId(cursor)
      return self.connection.ops.lastInsertId(cursor,
          self.query.getMeta().dbTable, self.query.getMeta().pk.column)


class SQLDeleteCompiler(SQLCompiler):
  def asSql(self):
    """
    Creates the SQL for this query. Returns the SQL string and list of
    parameters.
    """
    assert len(self.query.tables) == 1, \
      "Can only delete from one table at a time."
    qn = self
    result = ['DELETE FROM %s' % qn(self.query.tables[0])]
    where, params = self.compile(self.query.where)
    if where:
      result.append('WHERE %s' % where)
    return ' '.join(result), tuple(params)


class SQLUpdateCompiler(SQLCompiler):
  def asSql(self):
    """
    Creates the SQL for this query. Returns the SQL string and list of
    parameters.
    """
    self.preSqlSetup()
    if not self.query.values:
      return '', ()
    table = self.query.tables[0]
    qn = self
    result = ['UPDATE %s' % qn(table)]
    result.append('SET')
    values, updateParams = [], []
    for field, modal, val in self.query.values:
      if hasattr(val, 'prepareDatabaseSave'):
        if field.rel or isinstance(val, ExpressionNode):
          val = val.prepareDatabaseSave(field)
        else:
          raise TypeError("Database is trying to update a relational field "
                  "of type %s with a value of type %s. Make sure "
                  "you are setting the correct relations" %
                  (field.__class__.__name__, val.__class__.__name__))
      else:
        val = field.getDbPrepSave(val, connection=self.connection)

      # Getting the placeholder for the field.
      if hasattr(field, 'getPlaceholder'):
        placeholder = field.getPlaceholder(val, self.connection)
      else:
        placeholder = '%s'

      if hasattr(val, 'evaluate'):
        val = SQLEvaluator(val, self.query, allowJoins=False)
      name = field.column
      if hasattr(val, 'asSql'):
        sql, params = self.compile(val)
        values.append('%s = %s' % (qn(name), sql))
        updateParams.extend(params)
      elif val is not None:
        values.append('%s = %s' % (qn(name), placeholder))
        updateParams.append(val)
      else:
        values.append('%s = NULL' % qn(name))
    if not values:
      return '', ()
    result.append(', '.join(values))
    where, params = self.compile(self.query.where)
    if where:
      result.append('WHERE %s' % where)
    return ' '.join(result), tuple(updateParams + params)

  def executeSql(self, resultType):
    """
    Execute the specified update. Returns the number of rows affected by
    the primary update query. The "primary update query" is the first
    non-empty query that is executed. Row counts for any subsequent,
    related queries are not available.
    """
    cursor = super(SQLUpdateCompiler, self).executeSql(resultType)
    try:
      rows = cursor.rowcount if cursor else 0
      isEmpty = cursor is None
    finally:
      if cursor:
        cursor.close()
    for query in self.query.getRelatedUpdates():
      auxRows = query.getCompiler(self.using).executeSql(resultType)
      if isEmpty and auxRows:
        rows = auxRows
        isEmpty = False
    return rows

  def preSqlSetup(self):
    """
    If the update depends on results from other tables, we need to do some
    munging of the "where" conditions to match the format required for
    (portable) SQL updates. That is done here.

    Further, if we are going to be running multiple updates, we pull out
    the id values to update at this point so that they don't change as a
    result of the progressive updates.
    """
    self.query.selectRelated = False
    self.query.clearOrdering(True)
    super(SQLUpdateCompiler, self).preSqlSetup()
    count = self.query.countActiveTables()
    if not self.query.relatedUpdates and count == 1:
      return

    # We need to use a sub-select in the where clause to filter on things
    # from other tables.
    query = self.query.clone(klass=Query)
    query._extra = {}
    query.select = []
    query.addFields([query.getMeta().pk.name])
    # Recheck the count - it is possible that fiddling with the select
    # fields above removes tables from the query. Refs #18304.
    count = query.countActiveTables()
    if not self.query.relatedUpdates and count == 1:
      return

    mustPreSelect = count > 1 and not self.connection.features.updateCanSelfSelect

    # Now we adjust the current query: reset the where clause and get rid
    # of all the tables we don't need (since they're in the sub-select).
    self.query.where = self.query.whereClass()
    if self.query.relatedUpdates or mustPreSelect:
      # Either we're using the idents in multiple update queries (so
      # don't want them to change), or the db backend doesn't support
      # selecting from the updating table (e.g. MySQL).
      idents = []
      for rows in query.getCompiler(self.using).executeSql(MULTI):
        idents.extend(r[0] for r in rows)
      self.query.addFilter(('pk__in', idents))
      self.query.relatedIds = idents
    else:
      # The fast path. Filters and updates in one query.
      self.query.addFilter(('pk__in', query))
    for alias in self.query.tables[1:]:
      self.query.aliasRefcount[alias] = 0


class SQLAggregateCompiler(SQLCompiler):
  def asSql(self, qn=None):
    """
    Creates the SQL for this query. Returns the SQL string and list of
    parameters.
    """
    if qn is None:
      qn = self

    sql, params = [], []
    for aggregate in self.query.aggregateSelect.values():
      aggSql, aggParams = self.compile(aggregate)
      sql.append(aggSql)
      params.extend(aggParams)
    sql = ', '.join(sql)
    params = tuple(params)

    sql = 'SELECT %s FROM (%s) subquery' % (sql, self.query.subquery)
    params = params + self.query.subParams
    return sql, params


class SQLDateCompiler(SQLCompiler):
  def resultsIter(self):
    """
    Returns an iterator over the results from executing this query.
    """
    resolveColumns = hasattr(self, 'resolveColumns')
    if resolveColumns:
      from theory.db.model.fields import DateField
      fields = [DateField()]
    else:
      from theory.db.backends.utils import typecastDate
      needsStringCast = self.connection.features.needsDatetimeStringCast

    offset = len(self.query.extraSelect)
    for rows in self.executeSql(MULTI):
      for row in rows:
        date = row[offset]
        if resolveColumns:
          date = self.resolveColumns(row, fields)[offset]
        elif needsStringCast:
          date = typecastDate(str(date))
        if isinstance(date, datetime.datetime):
          date = date.date()
        yield date


class SQLDateTimeCompiler(SQLCompiler):
  def resultsIter(self):
    """
    Returns an iterator over the results from executing this query.
    """
    resolveColumns = hasattr(self, 'resolveColumns')
    if resolveColumns:
      from theory.db.model.fields import DateTimeField
      fields = [DateTimeField()]
    else:
      from theory.db.backends.utils import typecastTimestamp
      needsStringCast = self.connection.features.needsDatetimeStringCast

    offset = len(self.query.extraSelect)
    for rows in self.executeSql(MULTI):
      for row in rows:
        datetime = row[offset]
        if resolveColumns:
          datetime = self.resolveColumns(row, fields)[offset]
        elif needsStringCast:
          datetime = typecastTimestamp(str(datetime))
        # Datetimes are artificially returned in UTC on databases that
        # don't support time zone. Restore the zone used in the query.
        if settings.USE_TZ:
          if datetime is None:
            raise ValueError("Database returned an invalid value "
                     "in QuerySet.datetimes(). Are time zone "
                     "definitions for your database and pytz installed?")
          datetime = datetime.replace(tzinfo=None)
          datetime = timezone.makeAware(datetime, self.query.tzinfo)
        yield datetime


def cursorIter(cursor, sentinel):
  """
  Yields blocks of rows from a cursor and ensures the cursor is closed when
  done.
  """
  try:
    for rows in iter((lambda: cursor.fetchmany(GET_ITERATOR_CHUNK_SIZE)),
        sentinel):
      yield rows
  finally:
    cursor.close()


def orderModifiedIter(cursor, trim, sentinel):
  """
  Yields blocks of rows from a cursor. We use this iterator in the special
  case when extra output columns have been added to support ordering
  requirements. We must trim those extra columns before anything else can use
  the results, since they're only needed to make the SQL valid.
  """
  try:
    for rows in iter((lambda: cursor.fetchmany(GET_ITERATOR_CHUNK_SIZE)),
        sentinel):
      yield [r[:-trim] for r in rows]
  finally:
    cursor.close()
