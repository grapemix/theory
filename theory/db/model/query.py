"""
The main QuerySet implementation. This provides the public API for the ORM.
"""

from collections import deque
import copy
import sys

from theory.conf import settings
from theory.core import exceptions
from theory.db import connections, router, transaction, IntegrityError
from theory.db.model.constants import LOOKUP_SEP
from theory.db.model.fields import AutoField, Empty
from theory.db.model.queryUtils import (Q, selectRelatedDescend,
  deferredClassFactory, InvalidQuery)
from theory.db.model.deletion import Collector
from theory.db.model.sql.constants import CURSOR
from theory.db.model import sql
from theory.utils.functional import partition
from theory.utils import six
from theory.utils import timezone

# The maximum number (one less than the max to be precise) of results to fetch
# in a get() query
MAX_GET_RESULTS = 20

# The maximum number of items to display in a QuerySet.__repr__
REPR_OUTPUT_SIZE = 20

# Pull into this namespace for backwards compatibility.
EmptyResultSet = sql.EmptyResultSet


def _pickleQueryset(classBases, classDict):
  """
  Used by `__reduce__` to create the initial version of the `QuerySet` class
  onto which the output of `__getstate__` will be applied.

  See `__reduce__` for more details.
  """
  new = Empty()
  new.__class__ = type(classBases[0].__name__, classBases, classDict)
  return new


class QuerySet(object):
  """
  Represents a lazy database lookup for a set of objects.
  """

  def __init__(self, modal=None, query=None, using=None, hints=None):
    self.modal = modal
    self._db = using
    self._hints = hints or {}
    self.query = query or sql.Query(self.modal)
    self._resultCache = None
    self._stickyFilter = False
    self._forWrite = False
    self._prefetchRelatedLookups = []
    self._prefetchDone = False
    self._knownRelatedObjects = {}        # {relField, {pk: relObj}}

  def asManager(cls):
    # Address the circular dependency between `Queryset` and `Manager`.
    from theory.db.model.manager import Manager
    return Manager.fromQueryset(cls)()
  asManager.querysetOnly = True
  asManager = classmethod(asManager)

  ########################
  # PYTHON MAGIC METHODS #
  ########################

  def __deepcopy__(self, memo):
    """
    Deep copy of a QuerySet doesn't populate the cache
    """
    obj = self.__class__()
    for k, v in self.__dict__.items():
      if k == '_resultCache':
        obj.__dict__[k] = None
      else:
        obj.__dict__[k] = copy.deepcopy(v, memo)
    return obj

  def __getstate__(self):
    """
    Allows the QuerySet to be pickled.
    """
    # Force the cache to be fully populated.
    self._fetchAll()
    objDict = self.__dict__.copy()
    return objDict

  def __reduce__(self):
    """
    Used by pickle to deal with the types that we create dynamically when
    specialized queryset such as `ValuesQuerySet` are used in conjunction
    with querysets that are *subclasses* of `QuerySet`.

    See `_clone` implementation for more details.
    """
    if hasattr(self, '_specializedQuerysetClass'):
      classBases = (
        self._specializedQuerysetClass,
        self._baseQuerysetClass,
      )
      classDict = {
        '_specializedQuerysetClass': self._specializedQuerysetClass,
        '_baseQuerysetClass': self._baseQuerysetClass,
      }
      return _pickleQueryset, (classBases, classDict), self.__getstate__()
    return super(QuerySet, self).__reduce__()

  def __repr__(self):
    data = list(self[:REPR_OUTPUT_SIZE + 1])
    if len(data) > REPR_OUTPUT_SIZE:
      data[-1] = "...(remaining elements truncated)..."
    return repr(data)

  def __len__(self):
    self._fetchAll()
    return len(self._resultCache)

  def __iter__(self):
    """
    The queryset iterator protocol uses three nested iterators in the
    default case:
      1. sql.compiler:executeSql()
        - Returns 100 rows at time (constants.GET_ITERATOR_CHUNK_SIZE)
         using cursor.fetchmany(). This part is responsible for
         doing some column masking, and returning the rows in chunks.
      2. sql/compiler.resultsIter()
        - Returns one row at time. At this point the rows are still just
         tuples. In some cases the return values are converted to
         Python values at this location (see resolveColumns(),
         resolveAggregate()).
      3. self.iterator()
        - Responsible for turning the rows into modal objects.
    """
    self._fetchAll()
    return iter(self._resultCache)

  def __nonzero__(self):
    self._fetchAll()
    return bool(self._resultCache)

  def __getitem__(self, k):
    """
    Retrieves an item or slice from the set of results.
    """
    if not isinstance(k, (slice,) + six.integerTypes):
      raise TypeError
    assert ((not isinstance(k, slice) and (k >= 0)) or
        (isinstance(k, slice) and (k.start is None or k.start >= 0) and
         (k.stop is None or k.stop >= 0))), \
      "Negative indexing is not supported."

    if self._resultCache is not None:
      return self._resultCache[k]

    if isinstance(k, slice):
      qs = self._clone()
      if k.start is not None:
        start = int(k.start)
      else:
        start = None
      if k.stop is not None:
        stop = int(k.stop)
      else:
        stop = None
      qs.query.setLimits(start, stop)
      return list(qs)[::k.step] if k.step else qs

    qs = self._clone()
    qs.query.setLimits(k, k + 1)
    return list(qs)[0]

  def __and__(self, other):
    self._mergeSanityCheck(other)
    if isinstance(other, EmptyQuerySet):
      return other
    if isinstance(self, EmptyQuerySet):
      return self
    combined = self._clone()
    combined._mergeKnownRelatedObjects(other)
    combined.query.combine(other.query, sql.AND)
    return combined

  def __or__(self, other):
    self._mergeSanityCheck(other)
    if isinstance(self, EmptyQuerySet):
      return other
    if isinstance(other, EmptyQuerySet):
      return self
    combined = self._clone()
    combined._mergeKnownRelatedObjects(other)
    combined.query.combine(other.query, sql.OR)
    return combined

  ####################################
  # METHODS THAT DO DATABASE QUERIES #
  ####################################

  def iterator(self):
    """
    An iterator over the results from applying this QuerySet to the
    database.
    """
    fillCache = False
    if connections[self.db].features.supportsSelectRelated:
      fillCache = self.query.selectRelated
    if isinstance(fillCache, dict):
      requested = fillCache
    else:
      requested = None
    maxDepth = self.query.maxDepth

    extraSelect = list(self.query.extraSelect)
    aggregateSelect = list(self.query.aggregateSelect)

    onlyLoad = self.query.getLoadedFieldNames()
    if not fillCache:
      fields = self.modal._meta.concreteFields

    loadFields = []
    # If only/defer clauses have been specified,
    # build the list of fields that are to be loaded.
    if onlyLoad:
      for field, modal in self.modal._meta.getConcreteFieldsWithModel():
        if modal is None:
          modal = self.modal
        try:
          if field.name in onlyLoad[modal]:
            # Add a field that has been explicitly included
            loadFields.append(field.name)
        except KeyError:
          # Model wasn't explicitly listed in the onlyLoad table
          # Therefore, we need to load all fields from this modal
          loadFields.append(field.name)

    indexStart = len(extraSelect)
    aggregateStart = indexStart + len(loadFields or self.modal._meta.concreteFields)

    skip = None
    if loadFields and not fillCache:
      # Some fields have been deferred, so we have to initialize
      # via keyword arguments.
      skip = set()
      initList = []
      for field in fields:
        if field.name not in loadFields:
          skip.add(field.attname)
        else:
          initList.append(field.attname)
      modalCls = deferredClassFactory(self.modal, skip)

    # Cache db and modal outside the loop
    db = self.db
    modal = self.modal
    compiler = self.query.getCompiler(using=db)
    if fillCache:
      klassInfo = getKlassInfo(modal, maxDepth=maxDepth,
                    requested=requested, onlyLoad=onlyLoad)
    for row in compiler.resultsIter():
      if fillCache:
        obj, _ = getCachedRow(row, indexStart, db, klassInfo,
                    offset=len(aggregateSelect))
      else:
        # Omit aggregates in object creation.
        rowData = row[indexStart:aggregateStart]
        if skip:
          obj = modalCls(**dict(zip(initList, rowData)))
        else:
          obj = modal(*rowData)

        # Store the source database of the object
        obj._state.db = db
        # This object came from the database; it's not being added.
        obj._state.adding = False

      if extraSelect:
        for i, k in enumerate(extraSelect):
          setattr(obj, k, row[i])

      # Add the aggregates to the modal
      if aggregateSelect:
        for i, aggregate in enumerate(aggregateSelect):
          setattr(obj, aggregate, row[i + aggregateStart])

      # Add the known related objects to the modal, if there are any
      if self._knownRelatedObjects:
        for field, relObjs in self._knownRelatedObjects.items():
          # Avoid overwriting objects loaded e.g. by selectRelated
          if hasattr(obj, field.getCacheName()):
            continue
          pk = getattr(obj, field.getAttname())
          try:
            relObj = relObjs[pk]
          except KeyError:
            pass               # may happen in qs1 | qs2 scenarios
          else:
            setattr(obj, field.name, relObj)

      yield obj

  def aggregate(self, *args, **kwargs):
    """
    Returns a dictionary containing the calculations (aggregation)
    over the current queryset

    If args is present the expression is passed as a kwarg using
    the Aggregate object's default alias.
    """
    if self.query.distinctFields:
      raise NotImplementedError("aggregate() + distinct(fields) not implemented.")
    for arg in args:
      kwargs[arg.defaultAlias] = arg

    query = self.query.clone()
    forceSubq = query.lowMark != 0 or query.highMark is not None
    for (alias, aggregateExpr) in kwargs.items():
      query.addAggregate(aggregateExpr, self.modal, alias,
                isSummary=True)
    return query.getAggregation(using=self.db, forceSubq=forceSubq)

  def count(self):
    """
    Performs a SELECT COUNT() and returns the number of records as an
    integer.

    If the QuerySet is already fully cached this simply returns the length
    of the cached results set to avoid multiple SELECT COUNT(*) calls.
    """
    if self._resultCache is not None:
      return len(self._resultCache)

    return self.query.getCount(using=self.db)

  def get(self, *args, **kwargs):
    """
    Performs the query and returns a single object matching the given
    keyword arguments.
    """
    clone = self.filter(*args, **kwargs)
    if self.query.canFilter():
      clone = clone.orderBy()
    if (not clone.query.selectForUpdate or
        connections[self.db].features.supportsSelectForUpdateWithLimit):
      clone = clone[:MAX_GET_RESULTS + 1]
    num = len(clone)
    if num == 1:
      return clone._resultCache[0]
    if not num:
      raise self.modal.DoesNotExist(
        "%s matching query does not exist." %
        self.modal._meta.objectName)
    raise self.modal.MultipleObjectsReturned(
      "get() returned more than one %s -- it returned %s!" % (
        self.modal._meta.objectName,
        num if num <= MAX_GET_RESULTS else 'more than %s' % MAX_GET_RESULTS
      )
    )

  def create(self, **kwargs):
    """
    Creates a new object with the given kwargs, saving it to the database
    and returning the created object.
    """
    obj = self.modal(**kwargs)
    self._forWrite = True
    obj.save(forceInsert=True, using=self.db)
    return obj

  def bulkCreate(self, objs, batchSize=None):
    """
    Inserts each of the instances into the database. This does *not* call
    save() on each of the instances, does not send any pre/post save
    signals, and does not set the primary key attribute if it is an
    autoincrement field.
    """
    # So this case is fun. When you bulk insert you don't get the primary
    # keys back (if it's an autoincrement), so you can't insert into the
    # child tables which references this. There are two workarounds, 1)
    # this could be implemented if you didn't have an autoincrement pk,
    # and 2) you could do it by doing O(n) normal inserts into the parent
    # tables to get the primary keys back, and then doing a single bulk
    # insert into the childmost table. Some databases might allow doing
    # this by using RETURNING clause for the insert query. We're punting
    # on these for now because they are relatively rare cases.
    assert batchSize is None or batchSize > 0
    if self.modal._meta.parents:
      raise ValueError("Can't bulk create an inherited modal")
    if not objs:
      return objs
    self._forWrite = True
    connection = connections[self.db]
    fields = self.modal._meta.localConcreteFields
    with transaction.commitOnSuccessUnlessManaged(using=self.db):
      if (connection.features.canCombineInsertsWithAndWithoutAutoIncrementPk
          and self.modal._meta.hasAutoField):
        self._batchedInsert(objs, fields, batchSize)
      else:
        objsWithPk, objsWithoutPk = partition(lambda o: o.pk is None, objs)
        if objsWithPk:
          self._batchedInsert(objsWithPk, fields, batchSize)
        if objsWithoutPk:
          fields = [f for f in fields if not isinstance(f, AutoField)]
          self._batchedInsert(objsWithoutPk, fields, batchSize)

    return objs

  def getOrCreate(self, defaults=None, **kwargs):
    """
    Looks up an object with the given kwargs, creating one if necessary.
    Returns a tuple of (object, created), where created is a boolean
    specifying whether an object was created.
    """
    lookup, params = self._extractModelParams(defaults, **kwargs)
    self._forWrite = True
    try:
      return self.get(**lookup), False
    except self.modal.DoesNotExist:
      return self._createObjectFromParams(lookup, params)

  def updateOrCreate(self, defaults=None, **kwargs):
    """
    Looks up an object with the given kwargs, updating one with defaults
    if it exists, otherwise creates a new one.
    Returns a tuple (object, created), where created is a boolean
    specifying whether an object was created.
    """
    defaults = defaults or {}
    lookup, params = self._extractModelParams(defaults, **kwargs)
    self._forWrite = True
    try:
      obj = self.get(**lookup)
    except self.modal.DoesNotExist:
      obj, created = self._createObjectFromParams(lookup, params)
      if created:
        return obj, created
    for k, v in six.iteritems(defaults):
      setattr(obj, k, v)

    with transaction.atomic(using=self.db):
      obj.save(using=self.db)
    return obj, False

  def _createObjectFromParams(self, lookup, params):
    """
    Tries to create an object using passed params.
    Used by getOrCreate and updateOrCreate
    """
    obj = self.modal(**params)
    try:
      with transaction.atomic(using=self.db):
        obj.save(forceInsert=True, using=self.db)
      return obj, True
    except IntegrityError:
      excInfo = sys.excInfo()
      try:
        return self.get(**lookup), False
      except self.modal.DoesNotExist:
        pass
      six.reraise(*excInfo)

  def _extractModelParams(self, defaults, **kwargs):
    """
    Prepares `lookup` (kwargs that are valid modal attributes), `params`
    (for creating a modal instance) based on given kwargs; for use by
    getOrCreate and updateOrCreate.
    """
    defaults = defaults or {}
    lookup = kwargs.copy()
    for f in self.modal._meta.fields:
      if f.attname in lookup:
        lookup[f.name] = lookup.pop(f.attname)
    params = dict((k, v) for k, v in kwargs.items() if LOOKUP_SEP not in k)
    params.update(defaults)
    return lookup, params

  def _earliestOrLatest(self, fieldName=None, direction="-"):
    """
    Returns the latest object, according to the modal's
    'getLatestBy' option or optional given fieldName.
    """
    orderBy = fieldName or getattr(self.modal._meta, 'getLatestBy')
    assert bool(orderBy), "earliest() and latest() require either a "\
      "fieldName parameter or 'getLatestBy' in the modal"
    assert self.query.canFilter(), \
      "Cannot change a query once a slice has been taken."
    obj = self._clone()
    obj.query.setLimits(high=1)
    obj.query.clearOrdering(forceEmpty=True)
    obj.query.addOrdering('%s%s' % (direction, orderBy))
    return obj.get()

  def earliest(self, fieldName=None):
    return self._earliestOrLatest(fieldName=fieldName, direction="")

  def latest(self, fieldName=None):
    return self._earliestOrLatest(fieldName=fieldName, direction="-")

  def first(self):
    """
    Returns the first object of a query, returns None if no match is found.
    """
    qs = self if self.ordered else self.orderBy('pk')
    try:
      return qs[0]
    except IndexError:
      return None

  def last(self):
    """
    Returns the last object of a query, returns None if no match is found.
    """
    qs = self.reverse() if self.ordered else self.orderBy('-pk')
    try:
      return qs[0]
    except IndexError:
      return None

  def inBulk(self, idList):
    """
    Returns a dictionary mapping each of the given IDs to the object with
    that ID.
    """
    assert self.query.canFilter(), \
      "Cannot use 'limit' or 'offset' with inBulk"
    if not idList:
      return {}
    qs = self.filter(pk__in=idList).orderBy()
    return dict((obj._getPkVal(), obj) for obj in qs)

  def delete(self):
    """
    Deletes the records in the current QuerySet.
    """
    assert self.query.canFilter(), \
      "Cannot use 'limit' or 'offset' with delete."

    delQuery = self._clone()

    # The delete is actually 2 queries - one to find related objects,
    # and one to delete. Make sure that the discovery of related
    # objects is performed on the same database as the deletion.
    delQuery._forWrite = True

    # Disable non-supported fields.
    delQuery.query.selectForUpdate = False
    delQuery.query.selectRelated = False
    delQuery.query.clearOrdering(forceEmpty=True)

    collector = Collector(using=delQuery.db)
    collector.collect(delQuery)
    collector.delete()

    # Clear the result cache, in case this QuerySet gets reused.
    self._resultCache = None
  delete.altersData = True
  delete.querysetOnly = True

  def _rawDelete(self, using):
    """
    Deletes objects found from the given queryset in single direct SQL
    query. No signals are sent, and there is no protection for cascades.
    """
    sql.DeleteQuery(self.modal).deleteQs(self, using)
  _rawDelete.altersData = True

  def update(self, **kwargs):
    """
    Updates all elements in the current QuerySet, setting all the given
    fields to the appropriate values.
    """
    assert self.query.canFilter(), \
      "Cannot update a query once a slice has been taken."
    self._forWrite = True
    query = self.query.clone(sql.UpdateQuery)
    query.addUpdateValues(kwargs)
    with transaction.commitOnSuccessUnlessManaged(using=self.db):
      rows = query.getCompiler(self.db).executeSql(CURSOR)
    self._resultCache = None
    return rows
  update.altersData = True

  def _update(self, values):
    """
    A version of update that accepts field objects instead of field names.
    Used primarily for modal saving and not intended for use by general
    code (it requires too much poking around at modal internals to be
    useful at that level).
    """
    assert self.query.canFilter(), \
      "Cannot update a query once a slice has been taken."
    query = self.query.clone(sql.UpdateQuery)
    query.addUpdateFields(values)
    self._resultCache = None
    return query.getCompiler(self.db).executeSql(CURSOR)
  _update.altersData = True
  _update.querysetOnly = False

  def exists(self):
    if self._resultCache is None:
      return self.query.hasResults(using=self.db)
    return bool(self._resultCache)

  def _prefetchRelatedObjects(self):
    # This method can only be called once the result cache has been filled.
    prefetchRelatedObjects(self._resultCache, self._prefetchRelatedLookups)
    self._prefetchDone = True

  ##################################################
  # PUBLIC METHODS THAT RETURN A QUERYSET SUBCLASS #
  ##################################################

  def raw(self, rawQuery, params=None, translations=None, using=None):
    if using is None:
      using = self.db
    return RawQuerySet(rawQuery, modal=self.modal,
        params=params, translations=translations,
        using=using)

  def values(self, *fields):
    return self._clone(klass=ValuesQuerySet, setup=True, _fields=fields)

  def valuesList(self, *fields, **kwargs):
    flat = kwargs.pop('flat', False)
    if kwargs:
      raise TypeError('Unexpected keyword arguments to valuesList: %s'
          % (list(kwargs),))
    if flat and len(fields) > 1:
      raise TypeError("'flat' is not valid when valuesList is called with more than one field.")
    return self._clone(klass=ValuesListQuerySet, setup=True, flat=flat,
        _fields=fields)

  def dates(self, fieldName, kind, order='ASC'):
    """
    Returns a list of date objects representing all available dates for
    the given fieldName, scoped to 'kind'.
    """
    assert kind in ("year", "month", "day"), \
      "'kind' must be one of 'year', 'month' or 'day'."
    assert order in ('ASC', 'DESC'), \
      "'order' must be either 'ASC' or 'DESC'."
    return self._clone(klass=DateQuerySet, setup=True,
       _fieldName=fieldName, _kind=kind, _order=order)

  def datetimes(self, fieldName, kind, order='ASC', tzinfo=None):
    """
    Returns a list of datetime objects representing all available
    datetimes for the given fieldName, scoped to 'kind'.
    """
    assert kind in ("year", "month", "day", "hour", "minute", "second"), \
      "'kind' must be one of 'year', 'month', 'day', 'hour', 'minute' or 'second'."
    assert order in ('ASC', 'DESC'), \
      "'order' must be either 'ASC' or 'DESC'."
    if settings.USE_TZ:
      if tzinfo is None:
        tzinfo = timezone.getCurrentTimezone()
    else:
      tzinfo = None
    return self._clone(klass=DateTimeQuerySet, setup=True,
        _fieldName=fieldName, _kind=kind, _order=order, _tzinfo=tzinfo)

  def none(self):
    """
    Returns an empty QuerySet.
    """
    clone = self._clone()
    clone.query.setEmpty()
    return clone

  ##################################################################
  # PUBLIC METHODS THAT ALTER ATTRIBUTES AND RETURN A NEW QUERYSET #
  ##################################################################

  def all(self):
    """
    Returns a new QuerySet that is a copy of the current one. This allows a
    QuerySet to proxy for a modal manager in some cases.
    """
    return self._clone()

  def filter(self, *args, **kwargs):
    """
    Returns a new QuerySet instance with the args ANDed to the existing
    set.
    """
    return self._filterOrExclude(False, *args, **kwargs)

  def exclude(self, *args, **kwargs):
    """
    Returns a new QuerySet instance with NOT (args) ANDed to the existing
    set.
    """
    return self._filterOrExclude(True, *args, **kwargs)

  def _filterOrExclude(self, negate, *args, **kwargs):
    if args or kwargs:
      assert self.query.canFilter(), \
        "Cannot filter a query once a slice has been taken."

    clone = self._clone()
    if negate:
      clone.query.addQ(~Q(*args, **kwargs))
    else:
      clone.query.addQ(Q(*args, **kwargs))
    return clone

  def complexFilter(self, filterObj):
    """
    Returns a new QuerySet instance with filterObj added to the filters.

    filterObj can be a Q object (or anything with an addToQuery()
    method) or a dictionary of keyword lookup arguments.

    This exists to support framework features such as 'limitChoicesTo',
    and usually it will be more natural to use other methods.
    """
    if isinstance(filterObj, Q) or hasattr(filterObj, 'addToQuery'):
      clone = self._clone()
      clone.query.addQ(filterObj)
      return clone
    else:
      return self._filterOrExclude(None, **filterObj)

  def selectForUpdate(self, nowait=False):
    """
    Returns a new QuerySet instance that will select objects with a
    FOR UPDATE lock.
    """
    obj = self._clone()
    obj._forWrite = True
    obj.query.selectForUpdate = True
    obj.query.selectForUpdateNowait = nowait
    return obj

  def selectRelated(self, *fields):
    """
    Returns a new QuerySet instance that will select related objects.

    If fields are specified, they must be ForeignKey fields and only those
    related objects are included in the selection.

    If selectRelated(None) is called, the list is cleared.
    """
    obj = self._clone()
    if fields == (None,):
      obj.query.selectRelated = False
    elif fields:
      obj.query.addSelectRelated(fields)
    else:
      obj.query.selectRelated = True
    return obj

  def prefetchRelated(self, *lookups):
    """
    Returns a new QuerySet instance that will prefetch the specified
    Many-To-One and Many-To-Many related objects when the QuerySet is
    evaluated.

    When prefetchRelated() is called more than once, the list of lookups to
    prefetch is appended to. If prefetchRelated(None) is called, the list
    is cleared.
    """
    clone = self._clone()
    if lookups == (None,):
      clone._prefetchRelatedLookups = []
    else:
      clone._prefetchRelatedLookups.extend(lookups)
    return clone

  def annotate(self, *args, **kwargs):
    """
    Return a query set in which the returned objects have been annotated
    with data aggregated from related fields.
    """
    for arg in args:
      if arg.defaultAlias in kwargs:
        raise ValueError("The named annotation '%s' conflicts with the "
                 "default name for another annotation."
                 % arg.defaultAlias)
      kwargs[arg.defaultAlias] = arg

    names = getattr(self, '_fields', None)
    if names is None:
      names = set(self.modal._meta.getAllFieldNames())
    for aggregate in kwargs:
      if aggregate in names:
        raise ValueError("The annotation '%s' conflicts with a field on "
          "the modal." % aggregate)

    obj = self._clone()

    obj._setupAggregateQuery(list(kwargs))

    # Add the aggregates to the query
    for (alias, aggregateExpr) in kwargs.items():
      obj.query.addAggregate(aggregateExpr, self.modal, alias,
        isSummary=False)

    return obj

  def orderBy(self, *fieldNames):
    """
    Returns a new QuerySet instance with the ordering changed.
    """
    assert self.query.canFilter(), \
      "Cannot reorder a query once a slice has been taken."
    obj = self._clone()
    obj.query.clearOrdering(forceEmpty=False)
    obj.query.addOrdering(*fieldNames)
    return obj

  def distinct(self, *fieldNames):
    """
    Returns a new QuerySet instance that will select only distinct results.
    """
    assert self.query.canFilter(), \
      "Cannot create distinct fields once a slice has been taken."
    obj = self._clone()
    obj.query.addDistinctFields(*fieldNames)
    return obj

  def extra(self, select=None, where=None, params=None, tables=None,
       orderBy=None, selectParams=None):
    """
    Adds extra SQL fragments to the query.
    """
    assert self.query.canFilter(), \
      "Cannot change a query once a slice has been taken"
    clone = self._clone()
    clone.query.addExtra(select, selectParams, where, params, tables, orderBy)
    return clone

  def reverse(self):
    """
    Reverses the ordering of the QuerySet.
    """
    clone = self._clone()
    clone.query.standardOrdering = not clone.query.standardOrdering
    return clone

  def defer(self, *fields):
    """
    Defers the loading of data for certain fields until they are accessed.
    The set of fields to defer is added to any existing set of deferred
    fields. The only exception to this is if None is passed in as the only
    parameter, in which case all deferrals are removed (None acts as a
    reset option).
    """
    clone = self._clone()
    if fields == (None,):
      clone.query.clearDeferredLoading()
    else:
      clone.query.addDeferredLoading(fields)
    return clone

  def only(self, *fields):
    """
    Essentially, the opposite of defer. Only the fields passed into this
    method and that are not already specified as deferred are loaded
    immediately when the queryset is evaluated.
    """
    if fields == (None,):
      # Can only pass None to defer(), not only(), as the rest option.
      # That won't stop people trying to do this, so let's be explicit.
      raise TypeError("Cannot pass None as an argument to only().")
    clone = self._clone()
    clone.query.addImmediateLoading(fields)
    return clone

  def using(self, alias):
    """
    Selects which database this QuerySet should execute its query against.
    """
    clone = self._clone()
    clone._db = alias
    return clone

  ###################################
  # PUBLIC INTROSPECTION ATTRIBUTES #
  ###################################

  def ordered(self):
    """
    Returns True if the QuerySet is ordered -- i.e. has an orderBy()
    clause or a default ordering on the modal.
    """
    if self.query.extraOrderBy or self.query.orderBy:
      return True
    elif self.query.defaultOrdering and self.query.getMeta().ordering:
      return True
    else:
      return False
  ordered = property(ordered)

  @property
  def db(self):
    "Return the database that will be used if this query is executed now"
    if self._forWrite:
      return self._db or router.dbForWrite(self.modal, **self._hints)
    return self._db or router.dbForRead(self.modal, **self._hints)

  ###################
  # PRIVATE METHODS #
  ###################

  def _insert(self, objs, fields, returnId=False, raw=False, using=None):
    """
    Inserts a new record for the given modal. This provides an interface to
    the InsertQuery class and is how Model.save() is implemented.
    """
    self._forWrite = True
    if using is None:
      using = self.db
    query = sql.InsertQuery(self.modal)
    query.insertValues(fields, objs, raw=raw)
    return query.getCompiler(using=using).executeSql(returnId)
  _insert.altersData = True
  _insert.querysetOnly = False

  def _batchedInsert(self, objs, fields, batchSize):
    """
    A little helper method for bulkInsert to insert the bulk one batch
    at a time. Inserts recursively a batch from the front of the bulk and
    then _batchedInsert() the remaining objects again.
    """
    if not objs:
      return
    ops = connections[self.db].ops
    batchSize = (batchSize or max(ops.bulkBatchSize(fields, objs), 1))
    for batch in [objs[i:i + batchSize]
           for i in range(0, len(objs), batchSize)]:
      self.modal._baseManager._insert(batch, fields=fields,
                       using=self.db)

  def _clone(self, klass=None, setup=False, **kwargs):
    if klass is None:
      klass = self.__class__
    elif not issubclass(self.__class__, klass):
      baseQuerysetClass = getattr(self, '_baseQuerysetClass', self.__class__)
      classBases = (klass, baseQuerysetClass)
      classDict = {
        '_baseQuerysetClass': baseQuerysetClass,
        '_specializedQuerysetClass': klass,
      }
      klass = type(klass.__name__, classBases, classDict)

    query = self.query.clone()
    if self._stickyFilter:
      query.filterIsSticky = True
    c = klass(modal=self.modal, query=query, using=self._db, hints=self._hints)
    c._forWrite = self._forWrite
    c._prefetchRelatedLookups = self._prefetchRelatedLookups[:]
    c._knownRelatedObjects = self._knownRelatedObjects
    c.__dict__.update(kwargs)
    if setup and hasattr(c, '_setupQuery'):
      c._setupQuery()
    return c

  def _fetchAll(self):
    if self._resultCache is None:
      self._resultCache = list(self.iterator())
    if self._prefetchRelatedLookups and not self._prefetchDone:
      self._prefetchRelatedObjects()

  def _nextIsSticky(self):
    """
    Indicates that the next filter call and the one following that should
    be treated as a single filter. This is only important when it comes to
    determining when to reuse tables for many-to-many filters. Required so
    that we can filter naturally on the results of related managers.

    This doesn't return a clone of the current QuerySet (it returns
    "self"). The method is only used internally and should be immediately
    followed by a filter() that does create a clone.
    """
    self._stickyFilter = True
    return self

  def _mergeSanityCheck(self, other):
    """
    Checks that we are merging two comparable QuerySet classes. By default
    this does nothing, but see the ValuesQuerySet for an example of where
    it's useful.
    """
    pass

  def _mergeKnownRelatedObjects(self, other):
    """
    Keep track of all known related objects from either QuerySet instance.
    """
    for field, objects in other._knownRelatedObjects.items():
      self._knownRelatedObjects.setdefault(field, {}).update(objects)

  def _setupAggregateQuery(self, aggregates):
    """
    Prepare the query for computing a result that contains aggregate annotations.
    """
    opts = self.modal._meta
    if self.query.groupBy is None:
      fieldNames = [f.attname for f in opts.concreteFields]
      self.query.addFields(fieldNames, False)
      self.query.setGroupBy()

  def _prepare(self):
    return self

  def _asSql(self, connection):
    """
    Returns the internal query's SQL and parameters (as a tuple).
    """
    obj = self.values("pk")
    if obj._db is None or connection == connections[obj._db]:
      return obj.query.getCompiler(connection=connection).asNestedSql()
    raise ValueError("Can't do subqueries with queries on different DBs.")

  # When used as part of a nested query, a queryset will never be an "always
  # empty" result.
  valueAnnotation = True

  def _addHints(self, **hints):
    """
    Update hinting information for later use by Routers
    """
    # If there is any hinting information, add it to what we already know.
    # If we have a new hint for an existing key, overwrite with the new value.
    self._hints.update(hints)

  def _hasFilters(self):
    """
    Checks if this QuerySet has any filtering going on. Note that this
    isn't equivalent for checking if all objects are present in results,
    for example qs[1:]._hasFilters() -> False.
    """
    return self.query.hasFilters()


class InstanceCheckMeta(type):
  def __instancecheck__(self, instance):
    return instance.query.isEmpty()


class EmptyQuerySet(six.withMetaclass(InstanceCheckMeta)):
  """
  Marker class usable for checking if a queryset is empty by .none():
    isinstance(qs.none(), EmptyQuerySet) -> True
  """

  def __init__(self, *args, **kwargs):
    raise TypeError("EmptyQuerySet can't be instantiated")


class ValuesQuerySet(QuerySet):
  def __init__(self, *args, **kwargs):
    super(ValuesQuerySet, self).__init__(*args, **kwargs)
    # selectRelated isn't supported in values(). (FIXME -#3358)
    self.query.selectRelated = False

    # QuerySet.clone() will also set up the _fields attribute with the
    # names of the modal fields to select.

  def only(self, *fields):
    raise NotImplementedError("ValuesQuerySet does not implement only()")

  def defer(self, *fields):
    raise NotImplementedError("ValuesQuerySet does not implement defer()")

  def iterator(self):
    # Purge any extra columns that haven't been explicitly asked for
    extraNames = list(self.query.extraSelect)
    fieldNames = self.fieldNames
    aggregateNames = list(self.query.aggregateSelect)

    names = extraNames + fieldNames + aggregateNames

    for row in self.query.getCompiler(self.db).resultsIter():
      yield dict(zip(names, row))

  def delete(self):
    # values().delete() doesn't work currently - make sure it raises an
    # user friendly error.
    raise TypeError("Queries with .values() or .valuesList() applied "
            "can't be deleted")

  def _setupQuery(self):
    """
    Constructs the fieldNames list that the values query will be
    retrieving.

    Called by the _clone() method after initializing the rest of the
    instance.
    """
    self.query.clearDeferredLoading()
    self.query.clearSelectFields()

    if self._fields:
      self.extraNames = []
      self.aggregateNames = []
      if not self.query._extra and not self.query._aggregates:
        # Short cut - if there are no extra or aggregates, then
        # the values() clause must be just field names.
        self.fieldNames = list(self._fields)
      else:
        self.query.defaultCols = False
        self.fieldNames = []
        for f in self._fields:
          # we inspect the full extraSelect list since we might
          # be adding back an extra select item that we hadn't
          # had selected previously.
          if self.query._extra and f in self.query._extra:
            self.extraNames.append(f)
          elif f in self.query.aggregateSelect:
            self.aggregateNames.append(f)
          else:
            self.fieldNames.append(f)
    else:
      # Default to all fields.
      self.extraNames = None
      self.fieldNames = [f.attname for f in self.modal._meta.concreteFields]
      self.aggregateNames = None

    self.query.select = []
    if self.extraNames is not None:
      self.query.setExtraMask(self.extraNames)
    self.query.addFields(self.fieldNames, True)
    if self.aggregateNames is not None:
      self.query.setAggregateMask(self.aggregateNames)

  def _clone(self, klass=None, setup=False, **kwargs):
    """
    Cloning a ValuesQuerySet preserves the current fields.
    """
    c = super(ValuesQuerySet, self)._clone(klass, **kwargs)
    if not hasattr(c, '_fields'):
      # Only clone self._fields if _fields wasn't passed into the cloning
      # call directly.
      c._fields = self._fields[:]
    c.fieldNames = self.fieldNames
    c.extraNames = self.extraNames
    c.aggregateNames = self.aggregateNames
    if setup and hasattr(c, '_setupQuery'):
      c._setupQuery()
    return c

  def _mergeSanityCheck(self, other):
    super(ValuesQuerySet, self)._mergeSanityCheck(other)
    if (set(self.extraNames) != set(other.extraNames) or
        set(self.fieldNames) != set(other.fieldNames) or
        self.aggregateNames != other.aggregateNames):
      raise TypeError("Merging '%s' classes must involve the same values in each case."
          % self.__class__.__name__)

  def _setupAggregateQuery(self, aggregates):
    """
    Prepare the query for computing a result that contains aggregate annotations.
    """
    self.query.setGroupBy()

    if self.aggregateNames is not None:
      self.aggregateNames.extend(aggregates)
      self.query.setAggregateMask(self.aggregateNames)

    super(ValuesQuerySet, self)._setupAggregateQuery(aggregates)

  def _asSql(self, connection):
    """
    For ValuesQuerySet (and subclasses like ValuesListQuerySet), they can
    only be used as nested queries if they're already set up to select only
    a single field (in which case, that is the field column that is
    returned). This differs from QuerySet.asSql(), where the column to
    select is set up by Theory.
    """
    if ((self._fields and len(self._fields) > 1) or
        (not self._fields and len(self.modal._meta.fields) > 1)):
      raise TypeError('Cannot use a multi-field %s as a filter value.'
          % self.__class__.__name__)

    obj = self._clone()
    if obj._db is None or connection == connections[obj._db]:
      return obj.query.getCompiler(connection=connection).asNestedSql()
    raise ValueError("Can't do subqueries with queries on different DBs.")

  def _prepare(self):
    """
    Validates that we aren't trying to do a query like
    value__in=qs.values('value1', 'value2'), which isn't valid.
    """
    if ((self._fields and len(self._fields) > 1) or
        (not self._fields and len(self.modal._meta.fields) > 1)):
      raise TypeError('Cannot use a multi-field %s as a filter value.'
          % self.__class__.__name__)
    return self


class ValuesListQuerySet(ValuesQuerySet):
  def iterator(self):
    if self.flat and len(self._fields) == 1:
      for row in self.query.getCompiler(self.db).resultsIter():
        yield row[0]
    elif not self.query.extraSelect and not self.query.aggregateSelect:
      for row in self.query.getCompiler(self.db).resultsIter():
        yield tuple(row)
    else:
      # When extra(select=...) or an annotation is involved, the extra
      # cols are always at the start of the row, and we need to reorder
      # the fields to match the order in self._fields.
      extraNames = list(self.query.extraSelect)
      fieldNames = self.fieldNames
      aggregateNames = list(self.query.aggregateSelect)

      names = extraNames + fieldNames + aggregateNames

      # If a field list has been specified, use it. Otherwise, use the
      # full list of fields, including extras and aggregates.
      if self._fields:
        fields = list(self._fields) + [f for f in aggregateNames if f not in self._fields]
      else:
        fields = names

      for row in self.query.getCompiler(self.db).resultsIter():
        data = dict(zip(names, row))
        yield tuple(data[f] for f in fields)

  def _clone(self, *args, **kwargs):
    clone = super(ValuesListQuerySet, self)._clone(*args, **kwargs)
    if not hasattr(clone, "flat"):
      # Only assign flat if the clone didn't already get it from kwargs
      clone.flat = self.flat
    return clone


class DateQuerySet(QuerySet):
  def iterator(self):
    return self.query.getCompiler(self.db).resultsIter()

  def _setupQuery(self):
    """
    Sets up any special features of the query attribute.

    Called by the _clone() method after initializing the rest of the
    instance.
    """
    self.query.clearDeferredLoading()
    self.query = self.query.clone(klass=sql.DateQuery, setup=True)
    self.query.select = []
    self.query.addSelect(self._fieldName, self._kind, self._order)

  def _clone(self, klass=None, setup=False, **kwargs):
    c = super(DateQuerySet, self)._clone(klass, False, **kwargs)
    c._fieldName = self._fieldName
    c._kind = self._kind
    if setup and hasattr(c, '_setupQuery'):
      c._setupQuery()
    return c


class DateTimeQuerySet(QuerySet):
  def iterator(self):
    return self.query.getCompiler(self.db).resultsIter()

  def _setupQuery(self):
    """
    Sets up any special features of the query attribute.

    Called by the _clone() method after initializing the rest of the
    instance.
    """
    self.query.clearDeferredLoading()
    self.query = self.query.clone(klass=sql.DateTimeQuery, setup=True, tzinfo=self._tzinfo)
    self.query.select = []
    self.query.addSelect(self._fieldName, self._kind, self._order)

  def _clone(self, klass=None, setup=False, **kwargs):
    c = super(DateTimeQuerySet, self)._clone(klass, False, **kwargs)
    c._fieldName = self._fieldName
    c._kind = self._kind
    c._tzinfo = self._tzinfo
    if setup and hasattr(c, '_setupQuery'):
      c._setupQuery()
    return c


def getKlassInfo(klass, maxDepth=0, curDepth=0, requested=None,
          onlyLoad=None, fromParent=None):
  """
  Helper function that recursively returns an information for a klass, to be
  used in getCachedRow.  It exists just to compute this information only
  once for entire queryset. Otherwise it would be computed for each row, which
  leads to poor performance on large querysets.

  Arguments:
   * klass - the class to retrieve (and instantiate)
   * maxDepth - the maximum depth to which a selectRelated()
    relationship should be explored.
   * curDepth - the current depth in the selectRelated() tree.
    Used in recursive calls to determine if we should dig deeper.
   * requested - A dictionary describing the selectRelated() tree
    that is to be retrieved. keys are field names; values are
    dictionaries describing the keys on that related object that
    are themselves to be selectRelated().
   * onlyLoad - if the query has had only() or defer() applied,
    this is the list of field names that will be returned. If None,
    the full field list for `klass` can be assumed.
   * fromParent - the parent modal used to get to this modal

  Note that when travelling from parent to child, we will only load child
  fields which aren't in the parent.
  """
  if maxDepth and requested is None and curDepth > maxDepth:
    # We've recursed deeply enough; stop now.
    return None

  if onlyLoad:
    loadFields = onlyLoad.get(klass) or set()
    # When we create the object, we will also be creating populating
    # all the parent classes, so traverse the parent classes looking
    # for fields that must be included on load.
    for parent in klass._meta.getParentList():
      fields = onlyLoad.get(parent)
      if fields:
        loadFields.update(fields)
  else:
    loadFields = None

  if loadFields:
    # Handle deferred fields.
    skip = set()
    initList = []
    # Build the list of fields that *haven't* been requested
    for field, modal in klass._meta.getConcreteFieldsWithModel():
      if field.name not in loadFields:
        skip.add(field.attname)
      elif fromParent and issubclass(fromParent, modal.__class__):
        # Avoid loading fields already loaded for parent modal for
        # child model.
        continue
      else:
        initList.append(field.attname)
    # Retrieve all the requested fields
    fieldCount = len(initList)
    if skip:
      klass = deferredClassFactory(klass, skip)
      fieldNames = initList
    else:
      fieldNames = ()
  else:
    # Load all fields on klass

    fieldCount = len(klass._meta.concreteFields)
    # Check if we need to skip some parent fields.
    if fromParent and len(klass._meta.localConcreteFields) != len(klass._meta.concreteFields):
      # Only load those fields which haven't been already loaded into
      # 'fromParent'.
      nonSeenModels = [p for p in klass._meta.getParentList()
                if not issubclass(fromParent, p)]
      # Load local fields, too...
      nonSeenModels.append(klass)
      fieldNames = [f.attname for f in klass._meta.concreteFields
              if f.modal in nonSeenModels]
      fieldCount = len(fieldNames)
    # Try to avoid populating fieldNames variable for performance reasons.
    # If fieldNames variable is set, we use **kwargs based modal init
    # which is slower than normal init.
    if fieldCount == len(klass._meta.concreteFields):
      fieldNames = ()

  restricted = requested is not None

  relatedFields = []
  for f in klass._meta.fields:
    if selectRelatedDescend(f, restricted, requested, loadFields):
      if restricted:
        next = requested[f.name]
      else:
        next = None
      klassInfo = getKlassInfo(f.rel.to, maxDepth=maxDepth, curDepth=curDepth + 1,
                    requested=next, onlyLoad=onlyLoad)
      relatedFields.append((f, klassInfo))

  reverseRelatedFields = []
  if restricted:
    for o in klass._meta.getAllRelatedObjects():
      if o.field.unique and selectRelatedDescend(o.field, restricted, requested,
                             onlyLoad.get(o.modal), reverse=True):
        next = requested[o.field.relatedQueryName()]
        parent = klass if issubclass(o.modal, klass) else None
        klassInfo = getKlassInfo(o.modal, maxDepth=maxDepth, curDepth=curDepth + 1,
                      requested=next, onlyLoad=onlyLoad, fromParent=parent)
        reverseRelatedFields.append((o.field, klassInfo))
  if fieldNames:
    pkIdx = fieldNames.index(klass._meta.pk.attname)
  else:
    pkIdx = klass._meta.pkIndex()

  return klass, fieldNames, fieldCount, relatedFields, reverseRelatedFields, pkIdx


def getCachedRow(row, indexStart, using, klassInfo, offset=0,
          parentData=()):
  """
  Helper function that recursively returns an object with the specified
  related attributes already populated.

  This method may be called recursively to populate deep selectRelated()
  clauses.

  Arguments:
     * row - the row of data returned by the database cursor
     * indexStart - the index of the row at which data for this
      object is known to start
     * offset - the number of additional fields that are known to
      exist in row for `klass`. This usually means the number of
      annotated results on `klass`.
     * using - the database alias on which the query is being executed.
     * klassInfo - result of the getKlassInfo function
     * parentData - parent modal data in format (field, value). Used
      to populate the non-local fields of child model.
  """
  if klassInfo is None:
    return None
  klass, fieldNames, fieldCount, relatedFields, reverseRelatedFields, pkIdx = klassInfo

  fields = row[indexStart:indexStart + fieldCount]
  # If the pk column is None (or the equivalent '' in the case the
  # connection interprets empty strings as nulls), then the related
  # object must be non-existent - set the relation to None.
  if (fields[pkIdx] is None or
    (connections[using].features.interpretsEmptyStringsAsNulls and
     fields[pkIdx] == '')):
    obj = None
  elif fieldNames:
    fields = list(fields)
    for relField, value in parentData:
      fieldNames.append(relField.attname)
      fields.append(value)
    obj = klass(**dict(zip(fieldNames, fields)))
  else:
    obj = klass(*fields)
  # If an object was retrieved, set the database state.
  if obj:
    obj._state.db = using
    obj._state.adding = False

  # Instantiate related fields
  indexEnd = indexStart + fieldCount + offset
  # Iterate over each related object, populating any
  # selectRelated() fields
  for f, klassInfo in relatedFields:
    # Recursively retrieve the data for the related object
    cachedRow = getCachedRow(row, indexEnd, using, klassInfo)
    # If the recursive descent found an object, populate the
    # descriptor caches relevant to the object
    if cachedRow:
      relObj, indexEnd = cachedRow
      if obj is not None:
        # If the base object exists, populate the
        # descriptor cache
        setattr(obj, f.getCacheName(), relObj)
      if f.unique and relObj is not None:
        # If the field is unique, populate the
        # reverse descriptor cache on the related object
        setattr(relObj, f.related.getCacheName(), obj)

  # Now do the same, but for reverse related objects.
  # Only handle the restricted case - i.e., don't do a depth
  # descent into reverse relations unless explicitly requested
  for f, klassInfo in reverseRelatedFields:
    # Transfer data from this object to childs.
    parentData = []
    for relField, relModel in klassInfo[0]._meta.getFieldsWithModel():
      if relModel is not None and isinstance(obj, relModel):
        parentData.append((relField, getattr(obj, relField.attname)))
    # Recursively retrieve the data for the related object
    cachedRow = getCachedRow(row, indexEnd, using, klassInfo,
                  parentData=parentData)
    # If the recursive descent found an object, populate the
    # descriptor caches relevant to the object
    if cachedRow:
      relObj, indexEnd = cachedRow
      if obj is not None:
        # populate the reverse descriptor cache
        setattr(obj, f.related.getCacheName(), relObj)
      if relObj is not None:
        # If the related object exists, populate
        # the descriptor cache.
        setattr(relObj, f.getCacheName(), obj)
        # Populate related object caches using parent data.
        for relField, _ in parentData:
          if relField.rel:
            setattr(relObj, relField.attname, getattr(obj, relField.attname))
            try:
              cachedObj = getattr(obj, relField.getCacheName())
              setattr(relObj, relField.getCacheName(), cachedObj)
            except AttributeError:
              # Related object hasn't been cached yet
              pass
  return obj, indexEnd


class RawQuerySet(object):
  """
  Provides an iterator which converts the results of raw SQL queries into
  annotated modal instances.
  """
  def __init__(self, rawQuery, modal=None, query=None, params=None,
      translations=None, using=None, hints=None):
    self.rawQuery = rawQuery
    self.modal = modal
    self._db = using
    self._hints = hints or {}
    self.query = query or sql.RawQuery(sql=rawQuery, using=self.db, params=params)
    self.params = params or ()
    self.translations = translations or {}

  def __iter__(self):
    # Mapping of attrnames to row column positions. Used for constructing
    # the modal using kwargs, needed when not all modal's fields are present
    # in the query.
    modalInitFieldNames = {}
    # A list of tuples of (column name, column position). Used for
    # annotation fields.
    annotationFields = []

    # Cache some things for performance reasons outside the loop.
    db = self.db
    compiler = connections[db].ops.compiler('SQLCompiler')(
      self.query, connections[db], db
    )
    needResolvColumns = hasattr(compiler, 'resolveColumns')

    query = iter(self.query)

    try:
      # Find out which columns are modal's fields, and which ones should be
      # annotated to the modal.
      for pos, column in enumerate(self.columns):
        if column in self.modalFields:
          modalInitFieldNames[self.modalFields[column].attname] = pos
        else:
          annotationFields.append((column, pos))

      # Find out which modal's fields are not present in the query.
      skip = set()
      for field in self.modal._meta.fields:
        if field.attname not in modalInitFieldNames:
          skip.add(field.attname)
      if skip:
        if self.modal._meta.pk.attname in skip:
          raise InvalidQuery('Raw query must include the primary key')
        modalCls = deferredClassFactory(self.modal, skip)
      else:
        modalCls = self.modal
        # All modal's fields are present in the query. So, it is possible
        # to use *args based modal instantiation. For each field of the modal,
        # record the query column position matching that field.
        modalInitFieldPos = []
        for field in self.modal._meta.fields:
          modalInitFieldPos.append(modalInitFieldNames[field.attname])
      if needResolvColumns:
        fields = [self.modalFields.get(c, None) for c in self.columns]
      # Begin looping through the query values.
      for values in query:
        if needResolvColumns:
          values = compiler.resolveColumns(values, fields)
        # Associate fields to values
        if skip:
          modalInitKwargs = {}
          for attname, pos in six.iteritems(modalInitFieldNames):
            modalInitKwargs[attname] = values[pos]
          instance = modalCls(**modalInitKwargs)
        else:
          modalInitArgs = [values[pos] for pos in modalInitFieldPos]
          instance = modalCls(*modalInitArgs)
        if annotationFields:
          for column, pos in annotationFields:
            setattr(instance, column, values[pos])

        instance._state.db = db
        instance._state.adding = False

        yield instance
    finally:
      # Done iterating the Query. If it has its own cursor, close it.
      if hasattr(self.query, 'cursor') and self.query.cursor:
        self.query.cursor.close()

  def __repr__(self):
    text = self.rawQuery
    if self.params:
      text = text % (self.params if hasattr(self.params, 'keys') else tuple(self.params))
    return "<RawQuerySet: %r>" % text

  def __getitem__(self, k):
    return list(self)[k]

  @property
  def db(self):
    "Return the database that will be used if this query is executed now"
    return self._db or router.dbForRead(self.modal, **self._hints)

  def using(self, alias):
    """
    Selects which database this Raw QuerySet should execute its query against.
    """
    return RawQuerySet(self.rawQuery, modal=self.modal,
        query=self.query.clone(using=alias),
        params=self.params, translations=self.translations,
        using=alias)

  @property
  def columns(self):
    """
    A list of modal field names in the order they'll appear in the
    query results.
    """
    if not hasattr(self, '_columns'):
      self._columns = self.query.getColumns()

      # Adjust any column names which don't match field names
      for (queryName, modelName) in self.translations.items():
        try:
          index = self._columns.index(queryName)
          self._columns[index] = modelName
        except ValueError:
          # Ignore translations for non-existent column names
          pass

    return self._columns

  @property
  def modalFields(self):
    """
    A dict mapping column names to modal field names.
    """
    if not hasattr(self, '_modalFields'):
      converter = connections[self.db].introspection.tableNameConverter
      self._modalFields = {}
      for field in self.modal._meta.fields:
        name, column = field.getAttnameColumn()
        self._modalFields[converter(column)] = field
    return self._modalFields


class Prefetch(object):
  def __init__(self, lookup, queryset=None, toAttr=None):
    # `prefetchThrough` is the path we traverse to perform the prefetch.
    self.prefetchThrough = lookup
    # `prefetchTo` is the path to the attribute that stores the result.
    self.prefetchTo = lookup
    if toAttr:
      self.prefetchTo = LOOKUP_SEP.join(lookup.split(LOOKUP_SEP)[:-1] + [toAttr])

    self.queryset = queryset
    self.toAttr = toAttr

  def addPrefix(self, prefix):
    self.prefetchThrough = LOOKUP_SEP.join([prefix, self.prefetchThrough])
    self.prefetchTo = LOOKUP_SEP.join([prefix, self.prefetchTo])

  def getCurrentPrefetchThrough(self, level):
    return LOOKUP_SEP.join(self.prefetchThrough.split(LOOKUP_SEP)[:level + 1])

  def getCurrentPrefetchTo(self, level):
    return LOOKUP_SEP.join(self.prefetchTo.split(LOOKUP_SEP)[:level + 1])

  def getCurrentToAttr(self, level):
    parts = self.prefetchTo.split(LOOKUP_SEP)
    toAttr = parts[level]
    asAttr = self.toAttr and level == len(parts) - 1
    return toAttr, asAttr

  def getCurrentQueryset(self, level):
    if self.getCurrentPrefetchTo(level) == self.prefetchTo:
      return self.queryset
    return None

  def __eq__(self, other):
    if isinstance(other, Prefetch):
      return self.prefetchTo == other.prefetchTo
    return False

  def __hash__(self):
    return hash(self.__class__) ^ hash(self.prefetchTo)


def normalizePrefetchLookups(lookups, prefix=None):
  """
  Helper function that normalize lookups into Prefetch objects.
  """
  ret = []
  for lookup in lookups:
    if not isinstance(lookup, Prefetch):
      lookup = Prefetch(lookup)
    if prefix:
      lookup.addPrefix(prefix)
    ret.append(lookup)
  return ret


def prefetchRelatedObjects(resultCache, relatedLookups):
  """
  Helper function for prefetchRelated functionality

  Populates prefetched objects caches for a list of results
  from a QuerySet
  """

  if len(resultCache) == 0:
    return  # nothing to do

  relatedLookups = normalizePrefetchLookups(relatedLookups)

  # We need to be able to dynamically add to the list of prefetchRelated
  # lookups that we look up (see below).  So we need some book keeping to
  # ensure we don't do duplicate work.
  doneQueries = {}    # dictionary of things like 'foo__bar': [results]

  autoLookups = set()  # we add to this as we go through.
  followedDescriptors = set()  # recursion protection

  allLookups = deque(relatedLookups)
  while allLookups:
    lookup = allLookups.popleft()
    if lookup.prefetchTo in doneQueries:
      if lookup.queryset:
        raise ValueError("'%s' lookup was already seen with a different queryset. "
                 "You may need to adjust the ordering of your lookups." % lookup.prefetchTo)

      continue

    # Top level, the list of objects to decorate is the result cache
    # from the primary QuerySet. It won't be for deeper levels.
    objList = resultCache

    throughAttrs = lookup.prefetchThrough.split(LOOKUP_SEP)
    for level, throughAttr in enumerate(throughAttrs):
      # Prepare main instances
      if len(objList) == 0:
        break

      prefetchTo = lookup.getCurrentPrefetchTo(level)
      if prefetchTo in doneQueries:
        # Skip any prefetching, and any object preparation
        objList = doneQueries[prefetchTo]
        continue

      # Prepare objects:
      goodObjects = True
      for obj in objList:
        # Since prefetching can re-use instances, it is possible to have
        # the same instance multiple times in objList, so obj might
        # already be prepared.
        if not hasattr(obj, '_prefetchedObjectsCache'):
          try:
            obj._prefetchedObjectsCache = {}
          except AttributeError:
            # Must be in a QuerySet subclass that is not returning
            # Model instances, either in Theory or 3rd
            # party. prefetchRelated() doesn't make sense, so quit
            # now.
            goodObjects = False
            break
      if not goodObjects:
        break

      # Descend down tree

      # We assume that objects retrieved are homogeneous (which is the premise
      # of prefetchRelated), so what applies to first object applies to all.
      firstObj = objList[0]
      prefetcher, descriptor, attrFound, isFetched = getPrefetcher(firstObj, throughAttr)

      if not attrFound:
        raise AttributeError("Cannot find '%s' on %s object, '%s' is an invalid "
                   "parameter to prefetchRelated()" %
                   (throughAttr, firstObj.__class__.__name__, lookup.prefetchThrough))

      if level == len(throughAttrs) - 1 and prefetcher is None:
        # Last one, this *must* resolve to something that supports
        # prefetching, otherwise there is no point adding it and the
        # developer asking for it has made a mistake.
        raise ValueError("'%s' does not resolve to an item that supports "
                 "prefetching - this is an invalid parameter to "
                 "prefetchRelated()." % lookup.prefetchThrough)

      if prefetcher is not None and not isFetched:
        objList, additionalLookups = prefetchOneLevel(objList, prefetcher, lookup, level)
        # We need to ensure we don't keep adding lookups from the
        # same relationships to stop infinite recursion. So, if we
        # are already on an automatically added lookup, don't add
        # the new lookups from relationships we've seen already.
        if not (lookup in autoLookups and descriptor in followedDescriptors):
          doneQueries[prefetchTo] = objList
          newLookups = normalizePrefetchLookups(additionalLookups, prefetchTo)
          autoLookups.update(newLookups)
          allLookups.extendleft(newLookups)
        followedDescriptors.add(descriptor)
      else:
        # Either a singly related object that has already been fetched
        # (e.g. via selectRelated), or hopefully some other property
        # that doesn't support prefetching but needs to be traversed.

        # We replace the current list of parent objects with the list
        # of related objects, filtering out empty or missing values so
        # that we can continue with nullable or reverse relations.
        newObjList = []
        for obj in objList:
          try:
            newObj = getattr(obj, throughAttr)
          except exceptions.ObjectDoesNotExist:
            continue
          if newObj is None:
            continue
          # We special-case `list` rather than something more generic
          # like `Iterable` because we don't want to accidentally match
          # user model that define __iter__.
          if isinstance(newObj, list):
            newObjList.extend(newObj)
          else:
            newObjList.append(newObj)
        objList = newObjList


def getPrefetcher(instance, attr):
  """
  For the attribute 'attr' on the given instance, finds
  an object that has a getPrefetchQueryset().
  Returns a 4 tuple containing:
  (the object with getPrefetchQueryset (or None),
   the descriptor object representing this relationship (or None),
   a boolean that is False if the attribute was not found at all,
   a boolean that is True if the attribute has already been fetched)
  """
  prefetcher = None
  isFetched = False

  # For singly related objects, we have to avoid getting the attribute
  # from the object, as this will trigger the query. So we first try
  # on the class, in order to get the descriptor object.
  relObjDescriptor = getattr(instance.__class__, attr, None)
  if relObjDescriptor is None:
    attrFound = hasattr(instance, attr)
  else:
    attrFound = True
    if relObjDescriptor:
      # singly related object, descriptor object has the
      # getPrefetchQueryset() method.
      if hasattr(relObjDescriptor, 'getPrefetchQueryset'):
        prefetcher = relObjDescriptor
        if relObjDescriptor.isCached(instance):
          isFetched = True
      else:
        # descriptor doesn't support prefetching, so we go ahead and get
        # the attribute on the instance rather than the class to
        # support many related managers
        relObj = getattr(instance, attr)
        if hasattr(relObj, 'getPrefetchQueryset'):
          prefetcher = relObj
  return prefetcher, relObjDescriptor, attrFound, isFetched


def prefetchOneLevel(instances, prefetcher, lookup, level):
  """
  Helper function for prefetchRelatedObjects

  Runs prefetches on all instances using the prefetcher object,
  assigning results to relevant caches in instance.

  The prefetched objects are returned, along with any additional
  prefetches that must be done due to prefetchRelated lookups
  found from default managers.
  """
  # prefetcher must have a method getPrefetchQueryset() which takes a list
  # of instances, and returns a tuple:

  # (queryset of instances of self.modal that are related to passed in instances,
  #  callable that gets value to be matched for returned instances,
  #  callable that gets value to be matched for passed in instances,
  #  boolean that is True for singly related objects,
  #  cache name to assign to).

  # The 'values to be matched' must be hashable as they will be used
  # in a dictionary.

  relQs, relObjAttr, instanceAttr, single, cacheName = (
    prefetcher.getPrefetchQueryset(instances, lookup.getCurrentQueryset(level)))
  # We have to handle the possibility that the QuerySet we just got back
  # contains some prefetchRelated lookups. We don't want to trigger the
  # prefetchRelated functionality by evaluating the query. Rather, we need
  # to merge in the prefetchRelated lookups.
  additionalLookups = getattr(relQs, '_prefetchRelatedLookups', [])
  if additionalLookups:
    # Don't need to clone because the manager should have given us a fresh
    # instance, so we access an internal instead of using public interface
    # for performance reasons.
    relQs._prefetchRelatedLookups = []

  allRelatedObjects = list(relQs)

  relObjCache = {}
  for relObj in allRelatedObjects:
    relAttrVal = relObjAttr(relObj)
    relObjCache.setdefault(relAttrVal, []).append(relObj)

  for obj in instances:
    instanceAttrVal = instanceAttr(obj)
    vals = relObjCache.get(instanceAttrVal, [])
    toAttr, asAttr = lookup.getCurrentToAttr(level)
    if single:
      val = vals[0] if vals else None
      toAttr = toAttr if asAttr else cacheName
      setattr(obj, toAttr, val)
    else:
      if asAttr:
        setattr(obj, toAttr, vals)
      else:
        # Cache in the QuerySet.all().
        qs = getattr(obj, toAttr).all()
        qs._resultCache = vals
        # We don't want the individual qs doing prefetchRelated now,
        # since we have merged this into the current work.
        qs._prefetchDone = True
        obj._prefetchedObjectsCache[cacheName] = qs
  return allRelatedObjects, additionalLookups
