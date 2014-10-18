"""
Create SQL statements for QuerySets.

The code in here encapsulates all of the SQL construction so that QuerySets
themselves do not have to (and could be backed by things other than SQL
databases). The abstraction barrier only works one way: this module has to know
all about the internals of model in order to get the information it needs.
"""

from collections import OrderedDict
import copy
import warnings

from theory.core.exceptions import FieldError
from theory.db import connections, DEFAULT_DB_ALIAS
from theory.db.model.constants import LOOKUP_SEP
from theory.db.model.aggregates import refsAggregate
from theory.db.model.expressions import ExpressionNode
from theory.db.model.fields import FieldDoesNotExist
from theory.db.model.queryUtils import Q
from theory.db.model.related import PathInfo
from theory.db.model.sql import aggregates as baseAggregatesModule
from theory.db.model.sql.constants import (QUERY_TERMS, ORDER_DIR, SINGLE,
    ORDER_PATTERN, JoinInfo, SelectInfo)
from theory.db.model.sql.datastructures import EmptyResultSet, Empty, MultiJoin, Col
from theory.db.model.sql.expressions import SQLEvaluator
from theory.db.model.sql.where import (WhereNode, Constraint, EverythingNode,
  ExtraWhere, AND, OR, EmptyWhere)
from theory.utils import six
from theory.utils.deprecation import RemovedInTheory19Warning
from theory.utils.encoding import forceText
from theory.utils.tree import Node

__all__ = ['Query', 'RawQuery']


class RawQuery(object):
  """
  A single raw SQL query
  """

  def __init__(self, sql, using, params=None):
    self.params = params or ()
    self.sql = sql
    self.using = using
    self.cursor = None

    # Mirror some properties of a normal query so that
    # the compiler can be used to process results.
    self.lowMark, self.highMark = 0, None  # Used for offset/limit
    self.extraSelect = {}
    self.aggregateSelect = {}

  def clone(self, using):
    return RawQuery(self.sql, using, params=self.params)

  def convertValues(self, value, field, connection):
    """Convert the database-returned value into a type that is consistent
    across database backends.

    By default, this defers to the underlying backend operations, but
    it can be overridden by Query classes for specific backends.
    """
    return connection.ops.convertValues(value, field)

  def getColumns(self):
    if self.cursor is None:
      self._executeQuery()
    converter = connections[self.using].introspection.tableNameConverter
    return [converter(columnMeta[0])
        for columnMeta in self.cursor.description]

  def __iter__(self):
    # Always execute a new query for a new iterator.
    # This could be optimized with a cache at the expense of RAM.
    self._executeQuery()
    if not connections[self.using].features.canUseChunkedReads:
      # If the database can't use chunked reads we need to make sure we
      # evaluate the entire query up front.
      result = list(self.cursor)
    else:
      result = self.cursor
    return iter(result)

  def __repr__(self):
    return "<RawQuery: %r>" % (self.sql % tuple(self.params))

  def _executeQuery(self):
    self.cursor = connections[self.using].cursor()
    self.cursor.execute(self.sql, self.params)


class Query(object):
  """
  A single SQL query.
  """
  # SQL join types. These are part of the class because their string forms
  # vary from database to database and can be customised by a subclass.
  INNER = 'INNER JOIN'
  LOUTER = 'LEFT OUTER JOIN'

  aliasPrefix = 'T'
  subqAliases = frozenset([aliasPrefix])
  queryTerms = QUERY_TERMS
  aggregatesModule = baseAggregatesModule

  compiler = 'SQLCompiler'

  def __init__(self, modal, where=WhereNode):
    self.modal = modal
    self.aliasRefcount = {}
    # aliasMap is the most important data structure regarding joins.
    # It's used for recording which joins exist in the query and what
    # type they are. The key is the alias of the joined table (possibly
    # the table name) and the value is JoinInfo from constants.py.
    self.aliasMap = {}
    self.tableMap = {}     # Maps table names to list of aliases.
    self.joinMap = {}
    self.defaultCols = True
    self.defaultOrdering = True
    self.standardOrdering = True
    self.usedAliases = set()
    self.filterIsSticky = False
    self.includedInheritedModels = {}

    # SQL-related attributes
    # Select and related select clauses as SelectInfo instances.
    # The select is used for cases where we want to set up the select
    # clause to contain other than default fields (values(), annotate(),
    # subqueries...)
    self.select = []
    # The relatedSelectCols is used for columns needed for
    # selectRelated - this is populated in the compile stage.
    self.relatedSelectCols = []
    self.tables = []    # Aliases in the order they are created.
    self.where = where()
    self.whereClass = where
    self.groupBy = None
    self.having = where()
    self.orderBy = []
    self.lowMark, self.highMark = 0, None  # Used for offset/limit
    self.distinct = False
    self.distinctFields = []
    self.selectForUpdate = False
    self.selectForUpdateNowait = False
    self.selectRelated = False

    # SQL aggregate-related attributes
    # The _aggregates will be an OrderedDict when used. Due to the cost
    # of creating OrderedDict this attribute is created lazily (in
    # self.aggregates property).
    self._aggregates = None  # Maps alias -> SQL aggregate function
    self.aggregateSelectMask = None
    self._aggregateSelectCache = None

    # Arbitrary maximum limit for selectRelated. Prevents infinite
    # recursion. Can be changed by the depth parameter to selectRelated().
    self.maxDepth = 5

    # These are for extensions. The contents are more or less appended
    # verbatim to the appropriate clause.
    # The _extra attribute is an OrderedDict, lazily created similarly to
    # .aggregates
    self._extra = None  # Maps colAlias -> (colSql, params).
    self.extraSelectMask = None
    self._extraSelectCache = None

    self.extraTables = ()
    self.extraOrderBy = ()

    # A tuple that is a set of modal field names and either True, if these
    # are the fields to defer, or False if these are the only fields to
    # load.
    self.deferredLoading = (set(), True)

  @property
  def extra(self):
    if self._extra is None:
      self._extra = OrderedDict()
    return self._extra

  @property
  def aggregates(self):
    if self._aggregates is None:
      self._aggregates = OrderedDict()
    return self._aggregates

  def __str__(self):
    """
    Returns the query as a string of SQL with the parameter values
    substituted in (use sqlWithParams() to see the unsubstituted string).

    Parameter values won't necessarily be quoted correctly, since that is
    done by the database interface at execution time.
    """
    sql, params = self.sqlWithParams()
    return sql % params

  def sqlWithParams(self):
    """
    Returns the query as an SQL string and the parameters that will be
    substituted into the query.
    """
    return self.getCompiler(DEFAULT_DB_ALIAS).asSql()

  def __deepcopy__(self, memo):
    result = self.clone(memo=memo)
    memo[id(self)] = result
    return result

  def prepare(self):
    return self

  def getCompiler(self, using=None, connection=None):
    if using is None and connection is None:
      raise ValueError("Need either using or connection")
    if using:
      connection = connections[using]

    # Check that the compiler will be able to execute the query
    for alias, aggregate in self.aggregateSelect.items():
      connection.ops.checkAggregateSupport(aggregate)

    return connection.ops.compiler(self.compiler)(self, connection, using)

  def getMeta(self):
    """
    Returns the Options instance (the modal._meta) from which to start
    processing. Normally, this is self.modal._meta, but it can be changed
    by subclasses.
    """
    return self.modal._meta

  def clone(self, klass=None, memo=None, **kwargs):
    """
    Creates a copy of the current instance. The 'kwargs' parameter can be
    used by clients to update attributes after copying has taken place.
    """
    obj = Empty()
    obj.__class__ = klass or self.__class__
    obj.modal = self.modal
    obj.aliasRefcount = self.aliasRefcount.copy()
    obj.aliasMap = self.aliasMap.copy()
    obj.tableMap = self.tableMap.copy()
    obj.joinMap = self.joinMap.copy()
    obj.defaultCols = self.defaultCols
    obj.defaultOrdering = self.defaultOrdering
    obj.standardOrdering = self.standardOrdering
    obj.includedInheritedModels = self.includedInheritedModels.copy()
    obj.select = self.select[:]
    obj.relatedSelectCols = []
    obj.tables = self.tables[:]
    obj.where = self.where.clone()
    obj.whereClass = self.whereClass
    if self.groupBy is None:
      obj.groupBy = None
    else:
      obj.groupBy = self.groupBy[:]
    obj.having = self.having.clone()
    obj.orderBy = self.orderBy[:]
    obj.lowMark, obj.highMark = self.lowMark, self.highMark
    obj.distinct = self.distinct
    obj.distinctFields = self.distinctFields[:]
    obj.selectForUpdate = self.selectForUpdate
    obj.selectForUpdateNowait = self.selectForUpdateNowait
    obj.selectRelated = self.selectRelated
    obj.relatedSelectCols = []
    obj._aggregates = self._aggregates.copy() if self._aggregates is not None else None
    if self.aggregateSelectMask is None:
      obj.aggregateSelectMask = None
    else:
      obj.aggregateSelectMask = self.aggregateSelectMask.copy()
    # _aggregateSelectCache cannot be copied, as doing so breaks the
    # (necessary) state in which both aggregates and
    # _aggregateSelectCache point to the same underlying objects.
    # It will get re-populated in the cloned queryset the next time it's
    # used.
    obj._aggregateSelectCache = None
    obj.maxDepth = self.maxDepth
    obj._extra = self._extra.copy() if self._extra is not None else None
    if self.extraSelectMask is None:
      obj.extraSelectMask = None
    else:
      obj.extraSelectMask = self.extraSelectMask.copy()
    if self._extraSelectCache is None:
      obj._extraSelectCache = None
    else:
      obj._extraSelectCache = self._extraSelectCache.copy()
    obj.extraTables = self.extraTables
    obj.extraOrderBy = self.extraOrderBy
    obj.deferredLoading = copy.copy(self.deferredLoading[0]), self.deferredLoading[1]
    if self.filterIsSticky and self.usedAliases:
      obj.usedAliases = self.usedAliases.copy()
    else:
      obj.usedAliases = set()
    obj.filterIsSticky = False
    if 'aliasPrefix' in self.__dict__:
      obj.aliasPrefix = self.aliasPrefix
    if 'subqAliases' in self.__dict__:
      obj.subqAliases = self.subqAliases.copy()

    obj.__dict__.update(kwargs)
    if hasattr(obj, '_setupQuery'):
      obj._setupQuery()
    return obj

  def convertValues(self, value, field, connection):
    """Convert the database-returned value into a type that is consistent
    across database backends.

    By default, this defers to the underlying backend operations, but
    it can be overridden by Query classes for specific backends.
    """
    return connection.ops.convertValues(value, field)

  def resolveAggregate(self, value, aggregate, connection):
    """Resolve the value of aggregates returned by the database to
    consistent (and reasonable) types.

    This is required because of the predisposition of certain backends
    to return Decimal and long types when they are not needed.
    """
    if value is None:
      if aggregate.isOrdinal:
        return 0
      # Return None as-is
      return value
    elif aggregate.isOrdinal:
      # Any ordinal aggregate (e.g., count) returns an int
      return int(value)
    elif aggregate.isComputed:
      # Any computed aggregate (e.g., avg) returns a float
      return float(value)
    else:
      # Return value depends on the type of the field being processed.
      return self.convertValues(value, aggregate.field, connection)

  def getAggregation(self, using, forceSubq=False):
    """
    Returns the dictionary with the values of the existing aggregations.
    """
    if not self.aggregateSelect:
      return {}

    # If there is a group by clause, aggregating does not add useful
    # information but retrieves only the first row. Aggregate
    # over the subquery instead.
    if self.groupBy is not None or forceSubq:

      from theory.db.model.sql.subqueries import AggregateQuery
      query = AggregateQuery(self.modal)
      obj = self.clone()
      if not forceSubq:
        # In forced subq case the ordering and limits will likely
        # affect the results.
        obj.clearOrdering(True)
        obj.clearLimits()
      obj.selectForUpdate = False
      obj.selectRelated = False
      obj.relatedSelectCols = []

      relabels = dict((t, 'subquery') for t in self.tables)
      # Remove any aggregates marked for reduction from the subquery
      # and move them to the outer AggregateQuery.
      for alias, aggregate in self.aggregateSelect.items():
        if aggregate.isSummary:
          query.aggregates[alias] = aggregate.relabeledClone(relabels)
          del obj.aggregateSelect[alias]

      try:
        query.addSubquery(obj, using)
      except EmptyResultSet:
        return dict(
          (alias, None)
          for alias in query.aggregateSelect
        )
    else:
      query = self
      self.select = []
      self.defaultCols = False
      self._extra = {}
      self.removeInheritedModels()

    query.clearOrdering(True)
    query.clearLimits()
    query.selectForUpdate = False
    query.selectRelated = False
    query.relatedSelectCols = []

    result = query.getCompiler(using).executeSql(SINGLE)
    if result is None:
      result = [None for q in query.aggregateSelect.items()]

    return dict(
      (alias, self.resolveAggregate(val, aggregate, connection=connections[using]))
      for (alias, aggregate), val
      in zip(query.aggregateSelect.items(), result)
    )

  def getCount(self, using):
    """
    Performs a COUNT() query using the current filter constraints.
    """
    obj = self.clone()
    if len(self.select) > 1 or self.aggregateSelect or (self.distinct and self.distinctFields):
      # If a select clause exists, then the query has already started to
      # specify the columns that are to be returned.
      # In this case, we need to use a subquery to evaluate the count.
      from theory.db.model.sql.subqueries import AggregateQuery
      subquery = obj
      subquery.clearOrdering(True)
      subquery.clearLimits()

      obj = AggregateQuery(obj.modal)
      try:
        obj.addSubquery(subquery, using=using)
      except EmptyResultSet:
        # addSubquery evaluates the query, if it's an EmptyResultSet
        # then there are can be no results, and therefore there the
        # count is obviously 0
        return 0

    obj.addCountColumn()
    number = obj.getAggregation(using=using)[None]

    # Apply offset and limit constraints manually, since using LIMIT/OFFSET
    # in SQL (in variants that provide them) doesn't change the COUNT
    # output.
    number = max(0, number - self.lowMark)
    if self.highMark is not None:
      number = min(number, self.highMark - self.lowMark)

    return number

  def hasFilters(self):
    return self.where or self.having

  def hasResults(self, using):
    q = self.clone()
    if not q.distinct:
      q.clearSelectClause()
    q.clearOrdering(True)
    q.setLimits(high=1)
    compiler = q.getCompiler(using=using)
    return compiler.hasResults()

  def combine(self, rhs, connector):
    """
    Merge the 'rhs' query into the current one (with any 'rhs' effects
    being applied *after* (that is, "to the right of") anything in the
    current query. 'rhs' is not modified during a call to this function.

    The 'connector' parameter describes how to connect filters from the
    'rhs' query.
    """
    assert self.modal == rhs.modal, \
      "Cannot combine queries on two different base model."
    assert self.canFilter(), \
      "Cannot combine queries once a slice has been taken."
    assert self.distinct == rhs.distinct, \
      "Cannot combine a unique query with a non-unique query."
    assert self.distinctFields == rhs.distinctFields, \
      "Cannot combine queries with different distinct fields."

    self.removeInheritedModels()
    # Work out how to relabel the rhs aliases, if necessary.
    changeMap = {}
    conjunction = (connector == AND)

    # Determine which existing joins can be reused. When combining the
    # query with AND we must recreate all joins for m2m filters. When
    # combining with OR we can reuse joins. The reason is that in AND
    # case a single row can't fulfill a condition like:
    #     revrel__col=1 & revrel__col=2
    # But, there might be two different related rows matching this
    # condition. In OR case a single True is enough, so single row is
    # enough, too.
    #
    # Note that we will be creating duplicate joins for non-m2m joins in
    # the AND case. The results will be correct but this creates too many
    # joins. This is something that could be fixed later on.
    reuse = set() if conjunction else set(self.tables)
    # Base table must be present in the query - this is the same
    # table on both sides.
    self.getInitialAlias()
    joinpromoter = JoinPromoter(connector, 2, False)
    joinpromoter.addVotes(
      j for j in self.aliasMap if self.aliasMap[j].joinType == self.INNER)
    rhsVotes = set()
    # Now, add the joins from rhs query into the new query (skipping base
    # table).
    for alias in rhs.tables[1:]:
      table, _, joinType, lhs, joinCols, nullable, joinField = rhs.aliasMap[alias]
      # If the left side of the join was already relabeled, use the
      # updated alias.
      lhs = changeMap.get(lhs, lhs)
      newAlias = self.join(
        (lhs, table, joinCols), reuse=reuse,
        nullable=nullable, joinField=joinField)
      if joinType == self.INNER:
        rhsVotes.add(newAlias)
      # We can't reuse the same join again in the query. If we have two
      # distinct joins for the same connection in rhs query, then the
      # combined query must have two joins, too.
      reuse.discard(newAlias)
      changeMap[alias] = newAlias
      if not rhs.aliasRefcount[alias]:
        # The alias was unused in the rhs query. Unref it so that it
        # will be unused in the new query, too. We have to add and
        # unref the alias so that join promotion has information of
        # the join type for the unused alias.
        self.unrefAlias(newAlias)
    joinpromoter.addVotes(rhsVotes)
    joinpromoter.updateJoinTypes(self)

    # Now relabel a copy of the rhs where-clause and add it to the current
    # one.
    if rhs.where:
      w = rhs.where.clone()
      w.relabelAliases(changeMap)
      if not self.where:
        # Since 'self' matches everything, add an explicit "include
        # everything" where-constraint so that connections between the
        # where clauses won't exclude valid results.
        self.where.add(EverythingNode(), AND)
    elif self.where:
      # rhs has an empty where clause.
      w = self.whereClass()
      w.add(EverythingNode(), AND)
    else:
      w = self.whereClass()
    self.where.add(w, connector)

    # Selection columns and extra extensions are those provided by 'rhs'.
    self.select = []
    for col, field in rhs.select:
      if isinstance(col, (list, tuple)):
        newCol = changeMap.get(col[0], col[0]), col[1]
        self.select.append(SelectInfo(newCol, field))
      else:
        newCol = col.relabeledClone(changeMap)
        self.select.append(SelectInfo(newCol, field))

    if connector == OR:
      # It would be nice to be able to handle this, but the queries don't
      # really make sense (or return consistent value sets). Not worth
      # the extra complexity when you can write a real query instead.
      if self._extra and rhs._extra:
        raise ValueError("When merging querysets using 'or', you "
            "cannot have extra(select=...) on both sides.")
    self.extra.update(rhs.extra)
    extraSelectMask = set()
    if self.extraSelectMask is not None:
      extraSelectMask.update(self.extraSelectMask)
    if rhs.extraSelectMask is not None:
      extraSelectMask.update(rhs.extraSelectMask)
    if extraSelectMask:
      self.setExtraMask(extraSelectMask)
    self.extraTables += rhs.extraTables

    # Ordering uses the 'rhs' ordering, unless it has none, in which case
    # the current ordering is used.
    self.orderBy = rhs.orderBy[:] if rhs.orderBy else self.orderBy
    self.extraOrderBy = rhs.extraOrderBy or self.extraOrderBy

  def deferredToData(self, target, callback):
    """
    Converts the self.deferredLoading data structure to an alternate data
    structure, describing the field that *will* be loaded. This is used to
    compute the columns to select from the database and also by the
    QuerySet class to work out which fields are being initialized on each
    modal. Models that have all their fields included aren't mentioned in
    the result, only those that have field restrictions in place.

    The "target" parameter is the instance that is populated (in place).
    The "callback" is a function that is called whenever a (modal, field)
    pair need to be added to "target". It accepts three parameters:
    "target", and the modal and list of fields being added for that modal.
    """
    fieldNames, defer = self.deferredLoading
    if not fieldNames:
      return
    origOpts = self.getMeta()
    seen = {}
    mustInclude = {origOpts.concreteModel: set([origOpts.pk])}
    for fieldName in fieldNames:
      parts = fieldName.split(LOOKUP_SEP)
      curModel = self.modal
      opts = origOpts
      for name in parts[:-1]:
        oldModel = curModel
        source = opts.getFieldByName(name)[0]
        if isReverseO2o(source):
          curModel = source.modal
        else:
          curModel = source.rel.to
        opts = curModel._meta
        # Even if we're "just passing through" this modal, we must add
        # both the current modal's pk and the related reference field
        # (if it's not a reverse relation) to the things we select.
        if not isReverseO2o(source):
          mustInclude[oldModel].add(source)
        addToDict(mustInclude, curModel, opts.pk)
      field, modal, _, _ = opts.getFieldByName(parts[-1])
      if modal is None:
        modal = curModel
      if not isReverseO2o(field):
        addToDict(seen, modal, field)

    if defer:
      # We need to load all fields for each modal, except those that
      # appear in "seen" (for all model that appear in "seen"). The only
      # slight complexity here is handling fields that exist on parent
      # model.
      workset = {}
      for modal, values in six.iteritems(seen):
        for field, m in modal._meta.getFieldsWithModel():
          if field in values:
            continue
          addToDict(workset, m or modal, field)
      for modal, values in six.iteritems(mustInclude):
        # If we haven't included a modal in workset, we don't add the
        # corresponding mustInclude fields for that modal, since an
        # empty set means "include all fields". That's why there's no
        # "else" branch here.
        if modal in workset:
          workset[modal].update(values)
      for modal, values in six.iteritems(workset):
        callback(target, modal, values)
    else:
      for modal, values in six.iteritems(mustInclude):
        if modal in seen:
          seen[modal].update(values)
        else:
          # As we've passed through this modal, but not explicitly
          # included any fields, we have to make sure it's mentioned
          # so that only the "must include" fields are pulled in.
          seen[modal] = values
      # Now ensure that every modal in the inheritance chain is mentioned
      # in the parent list. Again, it must be mentioned to ensure that
      # only "must include" fields are pulled in.
      for modal in origOpts.getParentList():
        if modal not in seen:
          seen[modal] = set()
      for modal, values in six.iteritems(seen):
        callback(target, modal, values)

  def deferredToColumnsCb(self, target, modal, fields):
    """
    Callback used by deferredToColumns(). The "target" parameter should
    be a set instance.
    """
    table = modal._meta.dbTable
    if table not in target:
      target[table] = set()
    for field in fields:
      target[table].add(field.column)

  def tableAlias(self, tableName, create=False):
    """
    Returns a table alias for the given tableName and whether this is a
    new alias or not.

    If 'create' is true, a new alias is always created. Otherwise, the
    most recently created alias for the table (if one exists) is reused.
    """
    current = self.tableMap.get(tableName)
    if not create and current:
      alias = current[0]
      self.aliasRefcount[alias] += 1
      return alias, False

    # Create a new alias for this table.
    if current:
      alias = '%s%d' % (self.aliasPrefix, len(self.aliasMap) + 1)
      current.append(alias)
    else:
      # The first occurrence of a table uses the table name directly.
      alias = tableName
      self.tableMap[alias] = [alias]
    self.aliasRefcount[alias] = 1
    self.tables.append(alias)
    return alias, True

  def refAlias(self, alias):
    """ Increases the reference count for this alias. """
    self.aliasRefcount[alias] += 1

  def unrefAlias(self, alias, amount=1):
    """ Decreases the reference count for this alias. """
    self.aliasRefcount[alias] -= amount

  def promoteJoins(self, aliases):
    """
    Promotes recursively the join type of given aliases and its children to
    an outer join. If 'unconditional' is False, the join is only promoted if
    it is nullable or the parent join is an outer join.

    The children promotion is done to avoid join chains that contain a LOUTER
    b INNER c. So, if we have currently a INNER b INNER c and a->b is promoted,
    then we must also promote b->c automatically, or otherwise the promotion
    of a->b doesn't actually change anything in the query results.
    """
    aliases = list(aliases)
    while aliases:
      alias = aliases.pop(0)
      if self.aliasMap[alias].joinCols[0][1] is None:
        # This is the base table (first FROM entry) - this table
        # isn't really joined at all in the query, so we should not
        # alter its join type.
        continue
      # Only the first alias (skipped above) should have None joinType
      assert self.aliasMap[alias].joinType is not None
      parentAlias = self.aliasMap[alias].lhsAlias
      parentLouter = (
        parentAlias
        and self.aliasMap[parentAlias].joinType == self.LOUTER)
      alreadyLouter = self.aliasMap[alias].joinType == self.LOUTER
      if ((self.aliasMap[alias].nullable or parentLouter) and
          not alreadyLouter):
        data = self.aliasMap[alias]._replace(joinType=self.LOUTER)
        self.aliasMap[alias] = data
        # Join type of 'alias' changed, so re-examine all aliases that
        # refer to this one.
        aliases.extend(
          join for join in self.aliasMap.keys()
          if (self.aliasMap[join].lhsAlias == alias
            and join not in aliases))

  def demoteJoins(self, aliases):
    """
    Change join type from LOUTER to INNER for all joins in aliases.

    Similarly to promoteJoins(), this method must ensure no join chains
    containing first an outer, then an inner join are generated. If we
    are demoting b->c join in chain a LOUTER b LOUTER c then we must
    demote a->b automatically, or otherwise the demotion of b->c doesn't
    actually change anything in the query results. .
    """
    aliases = list(aliases)
    while aliases:
      alias = aliases.pop(0)
      if self.aliasMap[alias].joinType == self.LOUTER:
        self.aliasMap[alias] = self.aliasMap[alias]._replace(joinType=self.INNER)
        parentAlias = self.aliasMap[alias].lhsAlias
        if self.aliasMap[parentAlias].joinType == self.INNER:
          aliases.append(parentAlias)

  def resetRefcounts(self, toCounts):
    """
    This method will reset reference counts for aliases so that they match
    the value passed in :param toCounts:.
    """
    for alias, curRefcount in self.aliasRefcount.copy().items():
      unrefAmount = curRefcount - toCounts.get(alias, 0)
      self.unrefAlias(alias, unrefAmount)

  def changeAliases(self, changeMap):
    """
    Changes the aliases in changeMap (which maps old-alias -> new-alias),
    relabelling any references to them in select columns and the where
    clause.
    """
    assert set(changeMap.keys()).intersection(set(changeMap.values())) == set()

    def relabelColumn(col):
      if isinstance(col, (list, tuple)):
        oldAlias = col[0]
        return (changeMap.get(oldAlias, oldAlias), col[1])
      else:
        return col.relabeledClone(changeMap)
    # 1. Update references in "select" (normal columns plus aliases),
    # "group by", "where" and "having".
    self.where.relabelAliases(changeMap)
    self.having.relabelAliases(changeMap)
    if self.groupBy:
      self.groupBy = [relabelColumn(col) for col in self.groupBy]
    self.select = [SelectInfo(relabelColumn(s.col), s.field)
            for s in self.select]
    if self._aggregates:
      self._aggregates = OrderedDict(
        (key, relabelColumn(col)) for key, col in self._aggregates.items())

    # 2. Rename the alias in the internal table/alias datastructures.
    for ident, aliases in self.joinMap.items():
      del self.joinMap[ident]
      aliases = tuple(changeMap.get(a, a) for a in aliases)
      ident = (changeMap.get(ident[0], ident[0]),) + ident[1:]
      self.joinMap[ident] = aliases
    for oldAlias, newAlias in six.iteritems(changeMap):
      aliasData = self.aliasMap[oldAlias]
      aliasData = aliasData._replace(rhsAlias=newAlias)
      self.aliasRefcount[newAlias] = self.aliasRefcount[oldAlias]
      del self.aliasRefcount[oldAlias]
      self.aliasMap[newAlias] = aliasData
      del self.aliasMap[oldAlias]

      tableAliases = self.tableMap[aliasData.tableName]
      for pos, alias in enumerate(tableAliases):
        if alias == oldAlias:
          tableAliases[pos] = newAlias
          break
      for pos, alias in enumerate(self.tables):
        if alias == oldAlias:
          self.tables[pos] = newAlias
          break
    for key, alias in self.includedInheritedModels.items():
      if alias in changeMap:
        self.includedInheritedModels[key] = changeMap[alias]

    # 3. Update any joins that refer to the old alias.
    for alias, data in six.iteritems(self.aliasMap):
      lhs = data.lhsAlias
      if lhs in changeMap:
        data = data._replace(lhsAlias=changeMap[lhs])
        self.aliasMap[alias] = data

  def bumpPrefix(self, outerQuery):
    """
    Changes the alias prefix to the next letter in the alphabet in a way
    that the outer query's aliases and this query's aliases will not
    conflict. Even tables that previously had no alias will get an alias
    after this call.
    """
    if self.aliasPrefix != outerQuery.aliasPrefix:
      # No clashes between self and outer query should be possible.
      return
    self.aliasPrefix = chr(ord(self.aliasPrefix) + 1)
    while self.aliasPrefix in self.subqAliases:
      self.aliasPrefix = chr(ord(self.aliasPrefix) + 1)
      assert self.aliasPrefix < 'Z'
    self.subqAliases = self.subqAliases.union([self.aliasPrefix])
    outerQuery.subqAliases = outerQuery.subqAliases.union(self.subqAliases)
    changeMap = OrderedDict()
    for pos, alias in enumerate(self.tables):
      newAlias = '%s%d' % (self.aliasPrefix, pos)
      changeMap[alias] = newAlias
      self.tables[pos] = newAlias
    self.changeAliases(changeMap)

  def getInitialAlias(self):
    """
    Returns the first alias for this query, after increasing its reference
    count.
    """
    if self.tables:
      alias = self.tables[0]
      self.refAlias(alias)
    else:
      alias = self.join((None, self.getMeta().dbTable, None))
    return alias

  def countActiveTables(self):
    """
    Returns the number of tables in this query with a non-zero reference
    count. Note that after execution, the reference counts are zeroed, so
    tables added in compiler will not be seen by this method.
    """
    return len([1 for count in self.aliasRefcount.values() if count])

  def join(self, connection, reuse=None, nullable=False, joinField=None):
    """
    Returns an alias for the join in 'connection', either reusing an
    existing alias for that join or creating a new one. 'connection' is a
    tuple (lhs, table, joinCols) where 'lhs' is either an existing
    table alias or a table name. 'joinCols' is a tuple of tuples containing
    columns to join on ((lId1, rId1), (lId2, rId2)). The join corresponds
    to the SQL equivalent of::

      lhs.lId1 = table.rId1 AND lhs.lId2 = table.rId2

    The 'reuse' parameter can be either None which means all joins
    (matching the connection) are reusable, or it can be a set containing
    the aliases that can be reused.

    A join is always created as LOUTER if the lhs alias is LOUTER to make
    sure we do not generate chains like t1 LOUTER t2 INNER t3. All new
    joins are created as LOUTER if nullable is True.

    If 'nullable' is True, the join can potentially involve NULL values and
    is a candidate for promotion (to "left outer") when combining querysets.

    The 'joinField' is the field we are joining along (if any).
    """
    lhs, table, joinCols = connection
    assert lhs is None or joinField is not None
    existing = self.joinMap.get(connection, ())
    if reuse is None:
      reuse = existing
    else:
      reuse = [a for a in existing if a in reuse]
    for alias in reuse:
      if joinField and self.aliasMap[alias].joinField != joinField:
        # The joinMap doesn't contain joinField (mainly because
        # fields in Query structs are problematic in pickling), so
        # check that the existing join is created using the same
        # joinField used for the under work join.
        continue
      self.refAlias(alias)
      return alias

    # No reuse is possible, so we need a new alias.
    alias, _ = self.tableAlias(table, True)
    if not lhs:
      # Not all tables need to be joined to anything. No join type
      # means the later columns are ignored.
      joinType = None
    elif self.aliasMap[lhs].joinType == self.LOUTER or nullable:
      joinType = self.LOUTER
    else:
      joinType = self.INNER
    join = JoinInfo(table, alias, joinType, lhs, joinCols or ((None, None),), nullable,
            joinField)
    self.aliasMap[alias] = join
    if connection in self.joinMap:
      self.joinMap[connection] += (alias,)
    else:
      self.joinMap[connection] = (alias,)
    return alias

  def setupInheritedModels(self):
    """
    If the modal that is the basis for this QuerySet inherits other model,
    we need to ensure that those other model have their tables included in
    the query.

    We do this as a separate step so that subclasses know which
    tables are going to be active in the query, without needing to compute
    all the select columns (this method is called from preSqlSetup(),
    whereas column determination is a later part, and side-effect, of
    asSql()).
    """
    opts = self.getMeta()
    rootAlias = self.tables[0]
    seen = {None: rootAlias}

    for field, modal in opts.getFieldsWithModel():
      if modal not in seen:
        self.joinParentModel(opts, modal, rootAlias, seen)
    self.includedInheritedModels = seen

  def joinParentModel(self, opts, modal, alias, seen):
    """
    Makes sure the given 'modal' is joined in the query. If 'modal' isn't
    a parent of 'opts' or if it is None this method is a no-op.

    The 'alias' is the root alias for starting the join, 'seen' is a dict
    of modal -> alias of existing joins. It must also contain a mapping
    of None -> some alias. This will be returned in the no-op case.
    """
    if modal in seen:
      return seen[modal]
    chain = opts.getBaseChain(modal)
    if chain is None:
      return alias
    currOpts = opts
    for intModel in chain:
      if intModel in seen:
        return seen[intModel]
      # Proxy modal have elements in base chain
      # with no parents, assign the new options
      # object and skip to the next base in that
      # case
      if not currOpts.parents[intModel]:
        currOpts = intModel._meta
        continue
      linkField = currOpts.getAncestorLink(intModel)
      _, _, _, joins, _ = self.setupJoins(
        [linkField.name], currOpts, alias)
      currOpts = intModel._meta
      alias = seen[intModel] = joins[-1]
    return alias or seen[None]

  def removeInheritedModels(self):
    """
    Undoes the effects of setupInheritedModels(). Should be called
    whenever select columns (self.select) are set explicitly.
    """
    for key, alias in self.includedInheritedModels.items():
      if key:
        self.unrefAlias(alias)
    self.includedInheritedModels = {}

  def addAggregate(self, aggregate, modal, alias, isSummary):
    """
    Adds a single aggregate expression to the Query
    """
    opts = modal._meta
    fieldList = aggregate.lookup.split(LOOKUP_SEP)
    if len(fieldList) == 1 and self._aggregates and aggregate.lookup in self.aggregates:
      # Aggregate is over an annotation
      fieldName = fieldList[0]
      col = fieldName
      source = self.aggregates[fieldName]
      if not isSummary:
        raise FieldError("Cannot compute %s('%s'): '%s' is an aggregate" % (
          aggregate.name, fieldName, fieldName))
    elif ((len(fieldList) > 1) or
        (fieldList[0] not in [i.name for i in opts.fields]) or
        self.groupBy is None or
        not isSummary):
      # If:
      #   - the field descriptor has more than one part (foo__bar), or
      #   - the field descriptor is referencing an m2m/m2o field, or
      #   - this is a reference to a modal field (possibly inherited), or
      #   - this is an annotation over a modal field
      # then we need to explore the joins that are required.

      # Join promotion note - we must not remove any rows here, so use
      # outer join if there isn't any existing join.
      field, sources, opts, joinList, path = self.setupJoins(
        fieldList, opts, self.getInitialAlias())

      # Process the join chain to see if it can be trimmed
      targets, _, joinList = self.trimJoins(sources, joinList, path)

      col = targets[0].column
      source = sources[0]
      col = (joinList[-1], col)
    else:
      # The simplest cases. No joins required -
      # just reference the provided column alias.
      fieldName = fieldList[0]
      source = opts.getField(fieldName)
      col = fieldName
    # We want to have the alias in SELECT clause even if mask is set.
    self.appendAggregateMask([alias])

    # Add the aggregate to the query
    aggregate.addToQuery(self, alias, col=col, source=source, isSummary=isSummary)

  def prepareLookupValue(self, value, lookups, canReuse):
    # Default lookup if none given is exact.
    if len(lookups) == 0:
      lookups = ['exact']
    # Interpret '__exact=None' as the sql 'is NULL'; otherwise, reject all
    # uses of None as a query value.
    if value is None:
      if lookups[-1] not in ('exact', 'iexact'):
        raise ValueError("Cannot use None as a query value")
      lookups[-1] = 'isnull'
      value = True
    elif callable(value):
      warnings.warn(
        "Passing callable arguments to queryset is deprecated.",
        RemovedInTheory19Warning, stacklevel=2)
      value = value()
    elif isinstance(value, ExpressionNode):
      # If value is a query expression, evaluate it
      value = SQLEvaluator(value, self, reuse=canReuse)
    if hasattr(value, 'query') and hasattr(value.query, 'bumpPrefix'):
      value = value._clone()
      value.query.bumpPrefix(self)
    if hasattr(value, 'bumpPrefix'):
      value = value.clone()
      value.bumpPrefix(self)
    # For Oracle '' is equivalent to null. The check needs to be done
    # at this stage because join promotion can't be done at compiler
    # stage. Using DEFAULT_DB_ALIAS isn't nice, but it is the best we
    # can do here. Similar thing is done in isNullable(), too.
    if (connections[DEFAULT_DB_ALIAS].features.interpretsEmptyStringsAsNulls and
        lookups[-1] == 'exact' and value == ''):
      value = True
      lookups[-1] = 'isnull'
    return value, lookups

  def solveLookupType(self, lookup):
    """
    Solve the lookup type from the lookup (eg: 'foobar__id__icontains')
    """
    lookupSplitted = lookup.split(LOOKUP_SEP)
    if self._aggregates:
      aggregate, aggregateLookups = refsAggregate(lookupSplitted, self.aggregates)
      if aggregate:
        return aggregateLookups, (), aggregate
    _, field, _, lookupParts = self.namesToPath(lookupSplitted, self.getMeta())
    fieldParts = lookupSplitted[0:len(lookupSplitted) - len(lookupParts)]
    if len(lookupParts) == 0:
      lookupParts = ['exact']
    elif len(lookupParts) > 1:
      if not fieldParts:
        raise FieldError(
          'Invalid lookup "%s" for modal %s".' %
          (lookup, self.getMeta().modal.__name__))
    return lookupParts, fieldParts, False

  def buildLookup(self, lookups, lhs, rhs):
    lookups = lookups[:]
    while lookups:
      lookup = lookups[0]
      if len(lookups) == 1:
        finalLookup = lhs.getLookup(lookup)
        if finalLookup:
          return finalLookup(lhs, rhs)
        # We didn't find a lookup, so we are going to try getTransform
        # + getLookup('exact').
        lookups.append('exact')
      next = lhs.getTransform(lookup)
      if next:
        lhs = next(lhs, lookups)
      else:
        raise FieldError(
          "Unsupported lookup '%s' for %s or join on the field not "
          "permitted." %
          (lookup, lhs.outputField.__class__.__name__))
      lookups = lookups[1:]

  def buildFilter(self, filterExpr, branchNegated=False, currentNegated=False,
           canReuse=None, connector=AND):
    """
    Builds a WhereNode for a single filter clause, but doesn't add it
    to this Query. Query.addQ() will then add this filter to the where
    or having Node.

    The 'branchNegated' tells us if the current branch contains any
    negations. This will be used to determine if subqueries are needed.

    The 'currentNegated' is used to determine if the current filter is
    negated or not and this will be used to determine if IS NULL filtering
    is needed.

    The difference between currentNetageted and branchNegated is that
    branchNegated is set on first negation, but currentNegated is
    flipped for each negation.

    Note that addFilter will not do any negating itself, that is done
    upper in the code by addQ().

    The 'canReuse' is a set of reusable joins for multijoins.

    The method will create a filter clause that can be added to the current
    query. However, if the filter isn't added to the query then the caller
    is responsible for unreffing the joins used.
    """
    arg, value = filterExpr
    if not arg:
      raise FieldError("Cannot parse keyword query %r" % arg)
    lookups, parts, reffedAggregate = self.solveLookupType(arg)

    # Work out the lookup type and remove it from the end of 'parts',
    # if necessary.
    value, lookups = self.prepareLookupValue(value, lookups, canReuse)
    usedJoins = getattr(value, '_usedJoins', [])

    clause = self.whereClass()
    if reffedAggregate:
      condition = self.buildLookup(lookups, reffedAggregate, value)
      if not condition:
        # Backwards compat for custom lookups
        assert len(lookups) == 1
        condition = (reffedAggregate, lookups[0], value)
      clause.add(condition, AND)
      return clause, []

    opts = self.getMeta()
    alias = self.getInitialAlias()
    allowMany = not branchNegated

    try:
      field, sources, opts, joinList, path = self.setupJoins(
        parts, opts, alias, canReuse, allowMany)
      # splitExclude() needs to know which joins were generated for the
      # lookup parts
      self._lookupJoins = joinList
    except MultiJoin as e:
      return self.splitExclude(filterExpr, LOOKUP_SEP.join(parts[:e.level]),
                   canReuse, e.namesWithPath)

    if canReuse is not None:
      canReuse.update(joinList)
    usedJoins = set(usedJoins).union(set(joinList))

    # Process the join list to see if we can remove any non-needed joins from
    # the far end (fewer tables in a query is better).
    targets, alias, joinList = self.trimJoins(sources, joinList, path)

    if hasattr(field, 'getLookupConstraint'):
      # For now foreign keys get special treatment. This should be
      # refactored when composite fields lands.
      condition = field.getLookupConstraint(self.whereClass, alias, targets, sources,
                          lookups, value)
      lookupType = lookups[-1]
    else:
      assert(len(targets) == 1)
      col = Col(alias, targets[0], field)
      condition = self.buildLookup(lookups, col, value)
      if not condition:
        # Backwards compat for custom lookups
        if lookups[0] not in self.queryTerms:
          raise FieldError(
            "Join on field '%s' not permitted. Did you "
            "misspell '%s' for the lookup type?" %
            (col.outputField.name, lookups[0]))
        if len(lookups) > 1:
          raise FieldError("Nested lookup '%s' not supported." %
                   LOOKUP_SEP.join(lookups))
        condition = (Constraint(alias, targets[0].column, field), lookups[0], value)
        lookupType = lookups[-1]
      else:
        lookupType = condition.lookupName

    clause.add(condition, AND)

    requireOuter = lookupType == 'isnull' and value is True and not currentNegated
    if currentNegated and (lookupType != 'isnull' or value is False):
      requireOuter = True
      if (lookupType != 'isnull' and (
          self.isNullable(targets[0]) or
          self.aliasMap[joinList[-1]].joinType == self.LOUTER)):
        # The condition added here will be SQL like this:
        # NOT (col IS NOT NULL), where the first NOT is added in
        # upper layers of code. The reason for addition is that if col
        # is null, then col != someval will result in SQL "unknown"
        # which isn't the same as in Python. The Python None handling
        # is wanted, and it can be gotten by
        # (col IS NULL OR col != someval)
        #   <=>
        # NOT (col IS NOT NULL AND col = someval).
        lookupClass = targets[0].getLookup('isnull')
        clause.add(lookupClass(Col(alias, targets[0], sources[0]), False), AND)
    return clause, usedJoins if not requireOuter else ()

  def addFilter(self, filterClause):
    self.addQ(Q(**{filterClause[0]: filterClause[1]}))

  def needHaving(self, obj):
    """
    Returns whether or not all elements of this qObject need to be put
    together in the HAVING clause.
    """
    if not self._aggregates:
      return False
    if not isinstance(obj, Node):
      return (refsAggregate(obj[0].split(LOOKUP_SEP), self.aggregates)[0]
          or (hasattr(obj[1], 'containsAggregate')
            and obj[1].containsAggregate(self.aggregates)))
    return any(self.needHaving(c) for c in obj.children)

  def splitHavingParts(self, qObject, negated=False):
    """
    Returns a list of qObjects which need to go into the having clause
    instead of the where clause. Removes the splitted out nodes from the
    given qObject. Note that the qObject is altered, so cloning it is
    needed.
    """
    havingParts = []
    for c in qObject.children[:]:
      # When constructing the having nodes we need to take care to
      # preserve the negation status from the upper parts of the tree
      if isinstance(c, Node):
        # For each negated child, flip the inNegated flag.
        inNegated = c.negated ^ negated
        if c.connector == OR and self.needHaving(c):
          # A subtree starting from OR clause must go into having in
          # whole if any part of that tree references an aggregate.
          qObject.children.remove(c)
          havingParts.append(c)
          c.negated = inNegated
        else:
          havingParts.extend(
            self.splitHavingParts(c, inNegated)[1])
      elif self.needHaving(c):
        qObject.children.remove(c)
        newQ = self.whereClass(children=[c], negated=negated)
        havingParts.append(newQ)
    return qObject, havingParts

  def addQ(self, qObject):
    """
    A preprocessor for the internal _addQ(). Responsible for
    splitting the given qObject into where and having parts and
    setting up some internal variables.
    """
    if not self.needHaving(qObject):
      wherePart, havingParts = qObject, []
    else:
      wherePart, havingParts = self.splitHavingParts(
        qObject.clone(), qObject.negated)
    # For join promotion this case is doing an AND for the added qObject
    # and existing conditions. So, any existing inner join forces the join
    # type to remain inner. Existing outer joins can however be demoted.
    # (Consider case where relA is LOUTER and relA__col=1 is added - if
    # relA doesn't produce any rows, then the whole condition must fail.
    # So, demotion is OK.
    existingInner = set(
      (a for a in self.aliasMap if self.aliasMap[a].joinType == self.INNER))
    clause, requireInner = self._addQ(wherePart, self.usedAliases)
    self.where.add(clause, AND)
    for hp in havingParts:
      clause, _ = self._addQ(hp, self.usedAliases)
      self.having.add(clause, AND)
    self.demoteJoins(existingInner)

  def _addQ(self, qObject, usedAliases, branchNegated=False,
        currentNegated=False):
    """
    Adds a Q-object to the current filter.
    """
    connector = qObject.connector
    currentNegated = currentNegated ^ qObject.negated
    branchNegated = branchNegated or qObject.negated
    targetClause = self.whereClass(connector=connector,
                     negated=qObject.negated)
    joinpromoter = JoinPromoter(qObject.connector, len(qObject.children), currentNegated)
    for child in qObject.children:
      if isinstance(child, Node):
        childClause, neededInner = self._addQ(
          child, usedAliases, branchNegated,
          currentNegated)
        joinpromoter.addVotes(neededInner)
      else:
        childClause, neededInner = self.buildFilter(
          child, canReuse=usedAliases, branchNegated=branchNegated,
          currentNegated=currentNegated, connector=connector)
        joinpromoter.addVotes(neededInner)
      targetClause.add(childClause, connector)
    neededInner = joinpromoter.updateJoinTypes(self)
    return targetClause, neededInner

  def namesToPath(self, names, opts, allowMany=True, failOnMissing=False):
    """
    Walks the names path and turns them PathInfo tuples. Note that a
    single name in 'names' can generate multiple PathInfos (m2m for
    example).

    'names' is the path of names to travel, 'opts' is the modal Options we
    start the name resolving from, 'allowMany' is as for setupJoins().

    Returns a list of PathInfo tuples. In addition returns the final field
    (the last used join field), and target (which is a field guaranteed to
    contain the same value as the final field).
    """
    path, namesWithPath = [], []
    for pos, name in enumerate(names):
      curNamesWithPath = (name, [])
      if name == 'pk':
        name = opts.pk.name
      try:
        field, modal, direct, m2m = opts.getFieldByName(name)
      except FieldDoesNotExist:
        # We didn't found the current field, so move position back
        # one step.
        pos -= 1
        break
      # Check if we need any joins for concrete inheritance cases (the
      # field lives in parent, but we are currently in one of its
      # children)
      if modal:
        # The field lives on a base class of the current modal.
        # Skip the chain of proxy to the concrete proxied modal
        proxiedModel = opts.concreteModel

        for intModel in opts.getBaseChain(modal):
          if intModel is proxiedModel:
            opts = intModel._meta
          else:
            finalField = opts.parents[intModel]
            targets = (finalField.rel.getRelatedField(),)
            opts = intModel._meta
            path.append(PathInfo(finalField.modal._meta, opts, targets, finalField, False, True))
            curNamesWithPath[1].append(PathInfo(finalField.modal._meta, opts, targets, finalField, False, True))
      if hasattr(field, 'getPathInfo'):
        pathinfos = field.getPathInfo()
        if not allowMany:
          for innerPos, p in enumerate(pathinfos):
            if p.m2m:
              curNamesWithPath[1].extend(pathinfos[0:innerPos + 1])
              namesWithPath.append(curNamesWithPath)
              raise MultiJoin(pos + 1, namesWithPath)
        last = pathinfos[-1]
        path.extend(pathinfos)
        finalField = last.joinField
        opts = last.toOpts
        targets = last.targetFields
        curNamesWithPath[1].extend(pathinfos)
        namesWithPath.append(curNamesWithPath)
      else:
        # Local non-relational field.
        finalField = field
        targets = (field,)
        break
    if pos == -1 or (failOnMissing and pos + 1 != len(names)):
      self.raiseFieldError(opts, name)
    return path, finalField, targets, names[pos + 1:]

  def raiseFieldError(self, opts, name):
    available = opts.getAllFieldNames() + list(self.aggregateSelect)
    raise FieldError("Cannot resolve keyword %r into field. "
             "Choices are: %s" % (name, ", ".join(available)))

  def setupJoins(self, names, opts, alias, canReuse=None, allowMany=True):
    """
    Compute the necessary table joins for the passage through the fields
    given in 'names'. 'opts' is the Options class for the current modal
    (which gives the table we are starting from), 'alias' is the alias for
    the table to start the joining from.

    The 'canReuse' defines the reverse foreign key joins we can reuse. It
    can be None in which case all joins are reusable or a set of aliases
    that can be reused. Note that non-reverse foreign keys are always
    reusable when using setupJoins().

    If 'allowMany' is False, then any reverse foreign key seen will
    generate a MultiJoin exception.

    Returns the final field involved in the joins, the target field (used
    for any 'where' constraint), the final 'opts' value, the joins and the
    field path travelled to generate the joins.

    The target field is the field containing the concrete value. Final
    field can be something different, for example foreign key pointing to
    that value. Final field is needed for example in some value
    conversions (convert 'obj' in fk__id=obj to pk val using the foreign
    key field for example).
    """
    joins = [alias]
    # First, generate the path for the names
    path, finalField, targets, rest = self.namesToPath(
      names, opts, allowMany, failOnMissing=True)

    # Then, add the path to the query's joins. Note that we can't trim
    # joins at this stage - we will need the information about join type
    # of the trimmed joins.
    for pos, join in enumerate(path):
      opts = join.toOpts
      if join.direct:
        nullable = self.isNullable(join.joinField)
      else:
        nullable = True
      connection = alias, opts.dbTable, join.joinField.getJoiningColumns()
      reuse = canReuse if join.m2m else None
      alias = self.join(
        connection, reuse=reuse, nullable=nullable, joinField=join.joinField)
      joins.append(alias)
    if hasattr(finalField, 'field'):
      finalField = finalField.field
    return finalField, targets, opts, joins, path

  def trimJoins(self, targets, joins, path):
    """
    The 'target' parameter is the final field being joined to, 'joins'
    is the full list of join aliases. The 'path' contain the PathInfos
    used to create the joins.

    Returns the final target field and table alias and the new active
    joins.

    We will always trim any direct join if we have the target column
    available already in the previous table. Reverse joins can't be
    trimmed as we don't know if there is anything on the other side of
    the join.
    """
    joins = joins[:]
    for pos, info in enumerate(reversed(path)):
      if len(joins) == 1 or not info.direct:
        break
      joinTargets = set(t.column for t in info.joinField.foreignRelatedFields)
      curTargets = set(t.column for t in targets)
      if not curTargets.issubset(joinTargets):
        break
      targets = tuple(r[0] for r in info.joinField.relatedFields if r[1].column in curTargets)
      self.unrefAlias(joins.pop())
    return targets, joins[-1], joins

  def splitExclude(self, filterExpr, prefix, canReuse, namesWithPath):
    """
    When doing an exclude against any kind of N-to-many relation, we need
    to use a subquery. This method constructs the nested query, given the
    original exclude filter (filterExpr) and the portion up to the first
    N-to-many relation field.

    As an example we could have original filter ~Q(child__name='foo').
    We would get here with filterExpr = child__name, prefix = child and
    canReuse is a set of joins usable for filters in the original query.

    We will turn this into equivalent of:
      WHERE NOT (pk IN (SELECT parentId FROM thetable
               WHERE name = 'foo' AND parentId IS NOT NULL))

    It might be worth it to consider using WHERE NOT EXISTS as that has
    saner null handling, and is easier for the backend's optimizer to
    handle.
    """
    # Generate the inner query.
    query = Query(self.modal)
    query.addFilter(filterExpr)
    query.clearOrdering(True)
    # Try to have as simple as possible subquery -> trim leading joins from
    # the subquery.
    trimmedPrefix, containsLouter = query.trimStart(namesWithPath)
    query.removeInheritedModels()

    # Add extra check to make sure the selected field will not be null
    # since we are adding an IN <subquery> clause. This prevents the
    # database from tripping over IN (...,NULL,...) selects and returning
    # nothing
    alias, col = query.select[0].col
    if self.isNullable(query.select[0].field):
      lookupClass = query.select[0].field.getLookup('isnull')
      lookup = lookupClass(Col(alias, query.select[0].field, query.select[0].field), False)
      query.where.add(lookup, AND)
    if alias in canReuse:
      selectField = query.select[0].field
      pk = selectField.modal._meta.pk
      # Need to add a restriction so that outer query's filters are in effect for
      # the subquery, too.
      query.bumpPrefix(self)
      lookupClass = selectField.getLookup('exact')
      lookup = lookupClass(Col(query.select[0].col[0], pk, pk),
                 Col(alias, pk, pk))
      query.where.add(lookup, AND)

    condition, neededInner = self.buildFilter(
      ('%s__in' % trimmedPrefix, query),
      currentNegated=True, branchNegated=True, canReuse=canReuse)
    if containsLouter:
      orNullCondition, _ = self.buildFilter(
        ('%s__isnull' % trimmedPrefix, True),
        currentNegated=True, branchNegated=True, canReuse=canReuse)
      condition.add(orNullCondition, OR)
      # Note that the end result will be:
      # (outercol NOT IN innerq AND outercol IS NOT NULL) OR outercol IS NULL.
      # This might look crazy but due to how IN works, this seems to be
      # correct. If the IS NOT NULL check is removed then outercol NOT
      # IN will return UNKNOWN. If the IS NULL check is removed, then if
      # outercol IS NULL we will not match the row.
    return condition, neededInner

  def setEmpty(self):
    self.where = EmptyWhere()
    self.having = EmptyWhere()

  def isEmpty(self):
    return isinstance(self.where, EmptyWhere) or isinstance(self.having, EmptyWhere)

  def setLimits(self, low=None, high=None):
    """
    Adjusts the limits on the rows retrieved. We use low/high to set these,
    as it makes it more Pythonic to read and write. When the SQL query is
    created, they are converted to the appropriate offset and limit values.

    Any limits passed in here are applied relative to the existing
    constraints. So low is added to the current low value and both will be
    clamped to any existing high value.
    """
    if high is not None:
      if self.highMark is not None:
        self.highMark = min(self.highMark, self.lowMark + high)
      else:
        self.highMark = self.lowMark + high
    if low is not None:
      if self.highMark is not None:
        self.lowMark = min(self.highMark, self.lowMark + low)
      else:
        self.lowMark = self.lowMark + low

  def clearLimits(self):
    """
    Clears any existing limits.
    """
    self.lowMark, self.highMark = 0, None

  def canFilter(self):
    """
    Returns True if adding filters to this instance is still possible.

    Typically, this means no limits or offsets have been put on the results.
    """
    return not self.lowMark and self.highMark is None

  def clearSelectClause(self):
    """
    Removes all fields from SELECT clause.
    """
    self.select = []
    self.defaultCols = False
    self.selectRelated = False
    self.setExtraMask(())
    self.setAggregateMask(())

  def clearSelectFields(self):
    """
    Clears the list of fields to select (but not extraSelect columns).
    Some queryset types completely replace any existing list of select
    columns.
    """
    self.select = []

  def addDistinctFields(self, *fieldNames):
    """
    Adds and resolves the given fields to the query's "distinct on" clause.
    """
    self.distinctFields = fieldNames
    self.distinct = True

  def addFields(self, fieldNames, allowM2m=True):
    """
    Adds the given (modal) fields to the select set. The field names are
    added in the order specified.
    """
    alias = self.getInitialAlias()
    opts = self.getMeta()

    try:
      for name in fieldNames:
        # Join promotion note - we must not remove any rows here, so
        # if there is no existing joins, use outer join.
        field, targets, u2, joins, path = self.setupJoins(
          name.split(LOOKUP_SEP), opts, alias, canReuse=None,
          allowMany=allowM2m)
        targets, finalAlias, joins = self.trimJoins(targets, joins, path)
        for target in targets:
          self.select.append(SelectInfo((finalAlias, target.column), target))
    except MultiJoin:
      raise FieldError("Invalid field name: '%s'" % name)
    except FieldError:
      if LOOKUP_SEP in name:
        # For lookups spanning over relationships, show the error
        # from the modal on which the lookup failed.
        raise
      else:
        names = sorted(opts.getAllFieldNames() + list(self.extra)
                + list(self.aggregateSelect))
        raise FieldError("Cannot resolve keyword %r into field. "
                 "Choices are: %s" % (name, ", ".join(names)))
    self.removeInheritedModels()

  def addOrdering(self, *ordering):
    """
    Adds items from the 'ordering' sequence to the query's "order by"
    clause. These items are either field names (not column names) --
    possibly with a direction prefix ('-' or '?') -- or ordinals,
    corresponding to column positions in the 'select' list.

    If 'ordering' is empty, all ordering is cleared from the query.
    """
    errors = []
    for item in ordering:
      if not ORDER_PATTERN.match(item):
        errors.append(item)
    if errors:
      raise FieldError('Invalid orderBy arguments: %s' % errors)
    if ordering:
      self.orderBy.extend(ordering)
    else:
      self.defaultOrdering = False

  def clearOrdering(self, forceEmpty):
    """
    Removes any ordering settings. If 'forceEmpty' is True, there will be
    no ordering in the resulting query (not even the modal's default).
    """
    self.orderBy = []
    self.extraOrderBy = ()
    if forceEmpty:
      self.defaultOrdering = False

  def setGroupBy(self):
    """
    Expands the GROUP BY clause required by the query.

    This will usually be the set of all non-aggregate fields in the
    return data. If the database backend supports grouping by the
    primary key, and the query would be equivalent, the optimization
    will be made automatically.
    """
    self.groupBy = []

    for col, _ in self.select:
      self.groupBy.append(col)

  def addCountColumn(self):
    """
    Converts the query to do count(...) or count(distinct(pk)) in order to
    get its size.
    """
    if not self.distinct:
      if not self.select:
        count = self.aggregatesModule.Count('*', isSummary=True)
      else:
        assert len(self.select) == 1, \
          "Cannot add count col with multiple cols in 'select': %r" % self.select
        count = self.aggregatesModule.Count(self.select[0].col)
    else:
      opts = self.getMeta()
      if not self.select:
        count = self.aggregatesModule.Count(
          (self.join((None, opts.dbTable, None)), opts.pk.column),
          isSummary=True, distinct=True)
      else:
        # Because of SQL portability issues, multi-column, distinct
        # counts need a sub-query -- see getCount() for details.
        assert len(self.select) == 1, \
          "Cannot add count col with multiple cols in 'select'."

        count = self.aggregatesModule.Count(self.select[0].col, distinct=True)
      # Distinct handling is done in Count(), so don't do it at this
      # level.
      self.distinct = False

    # Set only aggregate to be the count column.
    # Clear out the select cache to reflect the new unmasked aggregates.
    self._aggregates = {None: count}
    self.setAggregateMask(None)
    self.groupBy = None

  def addSelectRelated(self, fields):
    """
    Sets up the selectRelated data structure so that we only select
    certain related model (as opposed to all model, when
    self.selectRelated=True).
    """
    if isinstance(self.selectRelated, bool):
      fieldDict = {}
    else:
      fieldDict = self.selectRelated
    for field in fields:
      d = fieldDict
      for part in field.split(LOOKUP_SEP):
        d = d.setdefault(part, {})
    self.selectRelated = fieldDict
    self.relatedSelectCols = []

  def addExtra(self, select, selectParams, where, params, tables, orderBy):
    """
    Adds data to the various extra_* attributes for user-created additions
    to the query.
    """
    if select:
      # We need to pair any placeholder markers in the 'select'
      # dictionary with their parameters in 'selectParams' so that
      # subsequent updates to the select dictionary also adjust the
      # parameters appropriately.
      selectPairs = OrderedDict()
      if selectParams:
        paramIter = iter(selectParams)
      else:
        paramIter = iter([])
      for name, entry in select.items():
        entry = forceText(entry)
        entryParams = []
        pos = entry.find("%s")
        while pos != -1:
          entryParams.append(next(paramIter))
          pos = entry.find("%s", pos + 2)
        selectPairs[name] = (entry, entryParams)
      # This is order preserving, since self.extraSelect is an OrderedDict.
      self.extra.update(selectPairs)
    if where or params:
      self.where.add(ExtraWhere(where, params), AND)
    if tables:
      self.extraTables += tuple(tables)
    if orderBy:
      self.extraOrderBy = orderBy

  def clearDeferredLoading(self):
    """
    Remove any fields from the deferred loading set.
    """
    self.deferredLoading = (set(), True)

  def addDeferredLoading(self, fieldNames):
    """
    Add the given list of modal field names to the set of fields to
    exclude from loading from the database when automatic column selection
    is done. The new field names are added to any existing field names that
    are deferred (or removed from any existing field names that are marked
    as the only ones for immediate loading).
    """
    # Fields on related model are stored in the literal double-underscore
    # format, so that we can use a set datastructure. We do the foo__bar
    # splitting and handling when computing the SQL column names (as part of
    # getColumns()).
    existing, defer = self.deferredLoading
    if defer:
      # Add to existing deferred names.
      self.deferredLoading = existing.union(fieldNames), True
    else:
      # Remove names from the set of any existing "immediate load" names.
      self.deferredLoading = existing.difference(fieldNames), False

  def addImmediateLoading(self, fieldNames):
    """
    Add the given list of modal field names to the set of fields to
    retrieve when the SQL is executed ("immediate loading" fields). The
    field names replace any existing immediate loading field names. If
    there are field names already specified for deferred loading, those
    names are removed from the new fieldNames before storing the new names
    for immediate loading. (That is, immediate loading overrides any
    existing immediate values, but respects existing deferrals.)
    """
    existing, defer = self.deferredLoading
    fieldNames = set(fieldNames)
    if 'pk' in fieldNames:
      fieldNames.remove('pk')
      fieldNames.add(self.getMeta().pk.name)

    if defer:
      # Remove any existing deferred names from the current set before
      # setting the new names.
      self.deferredLoading = fieldNames.difference(existing), False
    else:
      # Replace any existing "immediate load" field names.
      self.deferredLoading = fieldNames, False

  def getLoadedFieldNames(self):
    """
    If any fields are marked to be deferred, returns a dictionary mapping
    model to a set of names in those fields that will be loaded. If a
    modal is not in the returned dictionary, none of its fields are
    deferred.

    If no fields are marked for deferral, returns an empty dictionary.
    """
    # We cache this because we call this function multiple times
    # (compiler.fillRelatedSelections, query.iterator)
    try:
      return self._loadedFieldNamesCache
    except AttributeError:
      collection = {}
      self.deferredToData(collection, self.getLoadedFieldNamesCb)
      self._loadedFieldNamesCache = collection
      return collection

  def getLoadedFieldNamesCb(self, target, modal, fields):
    """
    Callback used by getDeferredFieldNames().
    """
    target[modal] = set(f.name for f in fields)

  def setAggregateMask(self, names):
    "Set the mask of aggregates that will actually be returned by the SELECT"
    if names is None:
      self.aggregateSelectMask = None
    else:
      self.aggregateSelectMask = set(names)
    self._aggregateSelectCache = None

  def appendAggregateMask(self, names):
    if self.aggregateSelectMask is not None:
      self.setAggregateMask(set(names).union(self.aggregateSelectMask))

  def setExtraMask(self, names):
    """
    Set the mask of extra select items that will be returned by SELECT,
    we don't actually remove them from the Query since they might be used
    later
    """
    if names is None:
      self.extraSelectMask = None
    else:
      self.extraSelectMask = set(names)
    self._extraSelectCache = None

  @property
  def aggregateSelect(self):
    """The OrderedDict of aggregate columns that are not masked, and should
    be used in the SELECT clause.

    This result is cached for optimization purposes.
    """
    if self._aggregateSelectCache is not None:
      return self._aggregateSelectCache
    elif not self._aggregates:
      return {}
    elif self.aggregateSelectMask is not None:
      self._aggregateSelectCache = OrderedDict(
        (k, v) for k, v in self.aggregates.items()
        if k in self.aggregateSelectMask
      )
      return self._aggregateSelectCache
    else:
      return self.aggregates

  @property
  def extraSelect(self):
    if self._extraSelectCache is not None:
      return self._extraSelectCache
    if not self._extra:
      return {}
    elif self.extraSelectMask is not None:
      self._extraSelectCache = OrderedDict(
        (k, v) for k, v in self.extra.items()
        if k in self.extraSelectMask
      )
      return self._extraSelectCache
    else:
      return self.extra

  def trimStart(self, namesWithPath):
    """
    Trims joins from the start of the join path. The candidates for trim
    are the PathInfos in namesWithPath structure that are m2m joins.

    Also sets the select column so the start matches the join.

    This method is meant to be used for generating the subquery joins &
    cols in splitExclude().

    Returns a lookup usable for doing outerq.filter(lookup=self). Returns
    also if the joins in the prefix contain a LEFT OUTER join.
    _"""
    allPaths = []
    for _, paths in namesWithPath:
      allPaths.extend(paths)
    containsLouter = False
    # Trim and operate only on tables that were generated for
    # the lookup part of the query. That is, avoid trimming
    # joins generated for F() expressions.
    lookupTables = [t for t in self.tables if t in self._lookupJoins or t == self.tables[0]]
    for trimmedPaths, path in enumerate(allPaths):
      if path.m2m:
        break
      if self.aliasMap[lookupTables[trimmedPaths + 1]].joinType == self.LOUTER:
        containsLouter = True
      self.unrefAlias(lookupTables[trimmedPaths])
    # The path.joinField is a Rel, lets get the other side's field
    joinField = path.joinField.field
    # Build the filter prefix.
    pathsInPrefix = trimmedPaths
    trimmedPrefix = []
    for name, path in namesWithPath:
      if pathsInPrefix - len(path) < 0:
        break
      trimmedPrefix.append(name)
      pathsInPrefix -= len(path)
    trimmedPrefix.append(
      joinField.foreignRelatedFields[0].name)
    trimmedPrefix = LOOKUP_SEP.join(trimmedPrefix)
    # Lets still see if we can trim the first join from the inner query
    # (that is, self). We can't do this for LEFT JOINs because we would
    # miss those rows that have nothing on the outer side.
    if self.aliasMap[lookupTables[trimmedPaths + 1]].joinType != self.LOUTER:
      selectFields = [r[0] for r in joinField.relatedFields]
      selectAlias = lookupTables[trimmedPaths + 1]
      self.unrefAlias(lookupTables[trimmedPaths])
      extraRestriction = joinField.getExtraRestriction(
        self.whereClass, None, lookupTables[trimmedPaths + 1])
      if extraRestriction:
        self.where.add(extraRestriction, AND)
    else:
      # TODO: It might be possible to trim more joins from the start of the
      # inner query if it happens to have a longer join chain containing the
      # values in selectFields. Lets punt this one for now.
      selectFields = [r[1] for r in joinField.relatedFields]
      selectAlias = lookupTables[trimmedPaths]
    self.select = [SelectInfo((selectAlias, f.column), f) for f in selectFields]
    return trimmedPrefix, containsLouter

  def isNullable(self, field):
    """
    A helper to check if the given field should be treated as nullable.

    Some backends treat '' as null and Theory treats such fields as
    nullable for those backends. In such situations field.null can be
    False even if we should treat the field as nullable.
    """
    # We need to use DEFAULT_DB_ALIAS here, as QuerySet does not have
    # (nor should it have) knowledge of which connection is going to be
    # used. The proper fix would be to defer all decisions where
    # isNullable() is needed to the compiler stage, but that is not easy
    # to do currently.
    if ((connections[DEFAULT_DB_ALIAS].features.interpretsEmptyStringsAsNulls)
        and field.emptyStringsAllowed):
      return True
    else:
      return field.null


def getOrderDir(field, default='ASC'):
  """
  Returns the field name and direction for an order specification. For
  example, '-foo' is returned as ('foo', 'DESC').

  The 'default' param is used to indicate which way no prefix (or a '+'
  prefix) should sort. The '-' prefix always sorts the opposite way.
  """
  dirn = ORDER_DIR[default]
  if field[0] == '-':
    return field[1:], dirn[1]
  return field, dirn[0]


def addToDict(data, key, value):
  """
  A helper function to add "value" to the set of values for "key", whether or
  not "key" already exists.
  """
  if key in data:
    data[key].add(value)
  else:
    data[key] = set([value])


def isReverseO2o(field):
  """
  A little helper to check if the given field is reverse-o2o. The field is
  expected to be some sort of relation field or related object.
  """
  return not hasattr(field, 'rel') and field.field.unique


def aliasDiff(refcountsBefore, refcountsAfter):
  """
  Given the before and after copies of refcounts works out which aliases
  have been added to the after copy.
  """
  # Use -1 as default value so that any join that is created, then trimmed
  # is seen as added.
  return set(t for t in refcountsAfter
        if refcountsAfter[t] > refcountsBefore.get(t, -1))


class JoinPromoter(object):
  """
  A class to abstract away join promotion problems for complex filter
  conditions.
  """

  def __init__(self, connector, numChildren, negated):
    self.connector = connector
    self.negated = negated
    if self.negated:
      if connector == AND:
        self.effectiveConnector = OR
      else:
        self.effectiveConnector = AND
    else:
      self.effectiveConnector = self.connector
    self.numChildren = numChildren
    # Maps of table alias to how many times it is seen as required for
    # inner and/or outer joins.
    self.outerVotes = {}
    self.innerVotes = {}

  def addVotes(self, innerVotes):
    """
    Add single vote per item to self.innerVotes. Parameter can be any
    iterable.
    """
    for voted in innerVotes:
      self.innerVotes[voted] = self.innerVotes.get(voted, 0) + 1

  def updateJoinTypes(self, query):
    """
    Change join types so that the generated query is as efficient as
    possible, but still correct. So, change as many joins as possible
    to INNER, but don't make OUTER joins INNER if that could remove
    results from the query.
    """
    toPromote = set()
    toDemote = set()
    # The effectiveConnector is used so that NOT (a AND b) is treated
    # similarly to (a OR b) for join promotion.
    for table, votes in self.innerVotes.items():
      # We must use outer joins in OR case when the join isn't contained
      # in all of the joins. Otherwise the INNER JOIN itself could remove
      # valid results. Consider the case where a modal with relA and
      # relB relations is queried with relA__col=1 | relB__col=2. Now,
      # if relA join doesn't produce any results is null (for example
      # reverse foreign key or null value in direct foreign key), and
      # there is a matching row in relB with col=2, then an INNER join
      # to relA would remove a valid match from the query. So, we need
      # to promote any existing INNER to LOUTER (it is possible this
      # promotion in turn will be demoted later on).
      if self.effectiveConnector == 'OR' and votes < self.numChildren:
        toPromote.add(table)
      # If connector is AND and there is a filter that can match only
      # when there is a joinable row, then use INNER. For example, in
      # relA__col=1 & relB__col=2, if either of the rels produce NULL
      # as join output, then the col=1 or col=2 can't match (as
      # NULL=anything is always false).
      # For the OR case, if all children voted for a join to be inner,
      # then we can use INNER for the join. For example:
      #     (relA__col__icontains=Alex | relA__col__icontains=Russell)
      # then if relA doesn't produce any rows, the whole condition
      # can't match. Hence we can safely use INNER join.
      if self.effectiveConnector == 'AND' or (
          self.effectiveConnector == 'OR' and votes == self.numChildren):
        toDemote.add(table)
      # Finally, what happens in cases where we have:
      #    (relA__col=1|relB__col=2) & relA__col__gte=0
      # Now, we first generate the OR clause, and promote joins for it
      # in the first if branch above. Both relA and relB are promoted
      # to LOUTER joins. After that we do the AND case. The OR case
      # voted no inner joins but the relA__col__gte=0 votes inner join
      # for relA. We demote it back to INNER join (in AND case a single
      # vote is enough). The demotion is OK, if relA doesn't produce
      # rows, then the relA__col__gte=0 clause can't be true, and thus
      # the whole clause must be false. So, it is safe to use INNER
      # join.
      # Note that in this example we could just as well have the __gte
      # clause and the OR clause swapped. Or we could replace the __gte
      # clause with an OR clause containing relA__col=1|relA__col=2,
      # and again we could safely demote to INNER.
    query.promoteJoins(toPromote)
    query.demoteJoins(toDemote)
    return toDemote
