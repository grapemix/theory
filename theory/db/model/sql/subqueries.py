"""
Query subclasses which provide extra functionality beyond simple data retrieval.
"""

from theory.conf import settings
from theory.core.exceptions import FieldError
from theory.db import connections
from theory.db.model.queryUtils import Q
from theory.db.model.constants import LOOKUP_SEP
from theory.db.model.fields import DateField, DateTimeField, FieldDoesNotExist
from theory.db.model.sql.constants import GET_ITERATOR_CHUNK_SIZE, NO_RESULTS, SelectInfo
from theory.db.model.sql.datastructures import Date, DateTime
from theory.db.model.sql.query import Query
from theory.utils import six
from theory.utils import timezone


__all__ = ['DeleteQuery', 'UpdateQuery', 'InsertQuery', 'DateQuery',
    'DateTimeQuery', 'AggregateQuery']


class DeleteQuery(Query):
  """
  Delete queries are done through this class, since they are more constrained
  than general queries.
  """

  compiler = 'SQLDeleteCompiler'

  def doQuery(self, table, where, using):
    self.tables = [table]
    self.where = where
    self.getCompiler(using).executeSql(NO_RESULTS)

  def deleteBatch(self, pkList, using, field=None):
    """
    Set up and execute delete queries for all the objects in pkList.

    More than one physical query may be executed if there are a
    lot of values in pkList.
    """
    if not field:
      field = self.getMeta().pk
    for offset in range(0, len(pkList), GET_ITERATOR_CHUNK_SIZE):
      self.where = self.whereClass()
      self.addQ(Q(
        **{field.attname + '__in': pkList[offset:offset + GET_ITERATOR_CHUNK_SIZE]}))
      self.doQuery(self.getMeta().dbTable, self.where, using=using)

  def deleteQs(self, query, using):
    """
    Delete the queryset in one SQL query (if possible). For simple queries
    this is done by copying the query.query.where to self.query, for
    complex queries by using subquery.
    """
    innerq = query.query
    # Make sure the inner query has at least one table in use.
    innerq.getInitialAlias()
    # The same for our new query.
    self.getInitialAlias()
    innerqUsedTables = [t for t in innerq.tables
               if innerq.aliasRefcount[t]]
    if ((not innerqUsedTables or innerqUsedTables == self.tables)
        and not len(innerq.having)):
      # There is only the base table in use in the query, and there is
      # no aggregate filtering going on.
      self.where = innerq.where
    else:
      pk = query.modal._meta.pk
      if not connections[using].features.updateCanSelfSelect:
        # We can't do the delete using subquery.
        values = list(query.valuesList('pk', flat=True))
        if not values:
          return
        self.deleteBatch(values, using)
        return
      else:
        innerq.clearSelectClause()
        innerq.select = [
          SelectInfo((self.getInitialAlias(), pk.column), None)
        ]
        values = innerq
      self.where = self.whereClass()
      self.addQ(Q(pk__in=values))
    self.getCompiler(using).executeSql(NO_RESULTS)


class UpdateQuery(Query):
  """
  Represents an "update" SQL query.
  """

  compiler = 'SQLUpdateCompiler'

  def __init__(self, *args, **kwargs):
    super(UpdateQuery, self).__init__(*args, **kwargs)
    self._setupQuery()

  def _setupQuery(self):
    """
    Runs on initialization and after cloning. Any attributes that would
    normally be set in __init__ should go in here, instead, so that they
    are also set up after a clone() call.
    """
    self.values = []
    self.relatedIds = None
    if not hasattr(self, 'relatedUpdates'):
      self.relatedUpdates = {}

  def clone(self, klass=None, **kwargs):
    return super(UpdateQuery, self).clone(klass,
        relatedUpdates=self.relatedUpdates.copy(), **kwargs)

  def updateBatch(self, pkList, values, using):
    self.addUpdateValues(values)
    for offset in range(0, len(pkList), GET_ITERATOR_CHUNK_SIZE):
      self.where = self.whereClass()
      self.addQ(Q(pk__in=pkList[offset: offset + GET_ITERATOR_CHUNK_SIZE]))
      self.getCompiler(using).executeSql(NO_RESULTS)

  def addUpdateValues(self, values):
    """
    Convert a dictionary of field name to value mappings into an update
    query. This is the entry point for the public update() method on
    querysets.
    """
    valuesSeq = []
    for name, val in six.iteritems(values):
      field, modal, direct, m2m = self.getMeta().getFieldByName(name)
      if not direct or m2m:
        raise FieldError('Cannot update modal field %r (only non-relations and foreign keys permitted).' % field)
      if modal:
        self.addRelatedUpdate(modal, field, val)
        continue
      valuesSeq.append((field, modal, val))
    return self.addUpdateFields(valuesSeq)

  def addUpdateFields(self, valuesSeq):
    """
    Turn a sequence of (field, modal, value) triples into an update query.
    Used by addUpdateValues() as well as the "fast" update path when
    saving model.
    """
    self.values.extend(valuesSeq)

  def addRelatedUpdate(self, modal, field, value):
    """
    Adds (name, value) to an update query for an ancestor modal.

    Updates are coalesced so that we only run one update query per ancestor.
    """
    self.relatedUpdates.setdefault(modal, []).append((field, None, value))

  def getRelatedUpdates(self):
    """
    Returns a list of query objects: one for each update required to an
    ancestor modal. Each query will have the same filtering conditions as
    the current query but will only update a single table.
    """
    if not self.relatedUpdates:
      return []
    result = []
    for modal, values in six.iteritems(self.relatedUpdates):
      query = UpdateQuery(modal)
      query.values = values
      if self.relatedIds is not None:
        query.addFilter(('pk__in', self.relatedIds))
      result.append(query)
    return result


class InsertQuery(Query):
  compiler = 'SQLInsertCompiler'

  def __init__(self, *args, **kwargs):
    super(InsertQuery, self).__init__(*args, **kwargs)
    self.fields = []
    self.objs = []

  def clone(self, klass=None, **kwargs):
    extras = {
      'fields': self.fields[:],
      'objs': self.objs[:],
      'raw': self.raw,
    }
    extras.update(kwargs)
    return super(InsertQuery, self).clone(klass, **extras)

  def insertValues(self, fields, objs, raw=False):
    """
    Set up the insert query from the 'insertValues' dictionary. The
    dictionary gives the modal field names and their target values.

    If 'rawValues' is True, the values in the 'insertValues' dictionary
    are inserted directly into the query, rather than passed as SQL
    parameters. This provides a way to insert NULL and DEFAULT keywords
    into the query, for example.
    """
    self.fields = fields
    self.objs = objs
    self.raw = raw


class DateQuery(Query):
  """
  A DateQuery is a normal query, except that it specifically selects a single
  date field. This requires some special handling when converting the results
  back to Python objects, so we put it in a separate class.
  """

  compiler = 'SQLDateCompiler'

  def addSelect(self, fieldName, lookupType, order='ASC'):
    """
    Converts the query into an extraction query.
    """
    try:
      result = self.setupJoins(
        fieldName.split(LOOKUP_SEP),
        self.getMeta(),
        self.getInitialAlias(),
      )
    except FieldError:
      raise FieldDoesNotExist("%s has no field named '%s'" % (
        self.getMeta().objectName, fieldName
      ))
    field = result[0]
    self._checkField(field)                # overridden in DateTimeQuery
    alias = result[3][-1]
    select = self._getSelect((alias, field.column), lookupType)
    self.clearSelectClause()
    self.select = [SelectInfo(select, None)]
    self.distinct = True
    self.orderBy = [1] if order == 'ASC' else [-1]

    if field.null:
      self.addFilter(("%s__isnull" % fieldName, False))

  def _checkField(self, field):
    assert isinstance(field, DateField), \
      "%r isn't a DateField." % field.name
    if settings.USE_TZ:
      assert not isinstance(field, DateTimeField), \
        "%r is a DateTimeField, not a DateField." % field.name

  def _getSelect(self, col, lookupType):
    return Date(col, lookupType)


class DateTimeQuery(DateQuery):
  """
  A DateTimeQuery is like a DateQuery but for a datetime field. If time zone
  support is active, the tzinfo attribute contains the time zone to use for
  converting the values before truncating them. Otherwise it's set to None.
  """

  compiler = 'SQLDateTimeCompiler'

  def clone(self, klass=None, memo=None, **kwargs):
    if 'tzinfo' not in kwargs and hasattr(self, 'tzinfo'):
      kwargs['tzinfo'] = self.tzinfo
    return super(DateTimeQuery, self).clone(klass, memo, **kwargs)

  def _checkField(self, field):
    assert isinstance(field, DateTimeField), \
      "%r isn't a DateTimeField." % field.name

  def _getSelect(self, col, lookupType):
    if self.tzinfo is None:
      tzname = None
    else:
      tzname = timezone._getTimezoneName(self.tzinfo)
    return DateTime(col, lookupType, tzname)


class AggregateQuery(Query):
  """
  An AggregateQuery takes another query as a parameter to the FROM
  clause and only selects the elements in the provided list.
  """

  compiler = 'SQLAggregateCompiler'

  def addSubquery(self, query, using):
    self.subquery, self.subParams = query.getCompiler(using).asSql(withColAliases=True)
