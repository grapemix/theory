from collections import OrderedDict
from operator import attrgetter

from theory.db import connections, transaction, IntegrityError
from theory.db.model import signals, sql
from theory.utils import six


class ProtectedError(IntegrityError):
  def __init__(self, msg, protectedObjects):
    self.protectedObjects = protectedObjects
    super(ProtectedError, self).__init__(msg, protectedObjects)


def CASCADE(collector, field, subObjs, using):
  collector.collect(subObjs, source=field.rel.to,
           sourceAttr=field.name, nullable=field.null)
  if field.null and not connections[using].features.canDeferConstraintChecks:
    collector.addFieldUpdate(field, None, subObjs)


def PROTECT(collector, field, subObjs, using):
  raise ProtectedError("Cannot delete some instances of modal '%s' because "
    "they are referenced through a protected foreign key: '%s.%s'" % (
      field.rel.to.__name__, subObjs[0].__class__.__name__, field.name
    ),
    subObjs
  )


def SET(value):
  if callable(value):
    def setOnDelete(collector, field, subObjs, using):
      collector.addFieldUpdate(field, value(), subObjs)
  else:
    def setOnDelete(collector, field, subObjs, using):
      collector.addFieldUpdate(field, value, subObjs)
  setOnDelete.deconstruct = lambda: ('theory.db.model.SET', (value,), {})
  return setOnDelete


def SET_NULL(collector, field, subObjs, using):
  collector.addFieldUpdate(field, None, subObjs)


def SET_DEFAULT(collector, field, subObjs, using):
  collector.addFieldUpdate(field, field.getDefault(), subObjs)


def DO_NOTHING(collector, field, subObjs, using):
  pass


class Collector(object):
  def __init__(self, using):
    self.using = using
    # Initially, {modal: set([instances])}, later values become lists.
    self.data = {}
    self.fieldUpdates = {}  # {modal: {(field, value): set([instances])}}
    # fastDeletes is a list of queryset-likes that can be deleted without
    # fetching the objects into memory.
    self.fastDeletes = []

    # Tracks deletion-order dependency for databases without transactions
    # or ability to defer constraint checks. Only concrete modal classes
    # should be included, as the dependencies exist only between actual
    # database tables; proxy model are represented here by their concrete
    # parent.
    self.dependencies = {}  # {modal: set([model])}

  def add(self, objs, source=None, nullable=False, reverseDependency=False):
    """
    Adds 'objs' to the collection of objects to be deleted.  If the call is
    the result of a cascade, 'source' should be the modal that caused it,
    and 'nullable' should be set to True if the relation can be null.

    Returns a list of all objects that were not already collected.
    """
    if not objs:
      return []
    newObjs = []
    modal = objs[0].__class__
    instances = self.data.setdefault(modal, set())
    for obj in objs:
      if obj not in instances:
        newObjs.append(obj)
    instances.update(newObjs)
    # Nullable relationships can be ignored -- they are nulled out before
    # deleting, and therefore do not affect the order in which objects have
    # to be deleted.
    if source is not None and not nullable:
      if reverseDependency:
        source, modal = modal, source
      self.dependencies.setdefault(
        source._meta.concreteModel, set()).add(modal._meta.concreteModel)
    return newObjs

  def addFieldUpdate(self, field, value, objs):
    """
    Schedules a field update. 'objs' must be a homogeneous iterable
    collection of modal instances (e.g. a QuerySet).
    """
    if not objs:
      return
    modal = objs[0].__class__
    self.fieldUpdates.setdefault(
      modal, {}).setdefault(
      (field, value), set()).update(objs)

  def canFastDelete(self, objs, fromField=None):
    """
    Determines if the objects in the given queryset-like can be
    fast-deleted. This can be done if there are no cascades, no
    parents and no signal listeners for the object class.

    The 'fromField' tells where we are coming from - we need this to
    determine if the objects are in fact to be deleted. Allows also
    skipping parent -> child -> parent chain preventing fast delete of
    the child.
    """
    if fromField and fromField.rel.onDelete is not CASCADE:
      return False
    if not (hasattr(objs, 'modal') and hasattr(objs, '_rawDelete')):
      return False
    modal = objs.modal
    if (signals.preDelete.hasListeners(modal)
        or signals.postDelete.hasListeners(modal)
        or signals.m2mChanged.hasListeners(modal)):
      return False
    # The use of fromField comes from the need to avoid cascade back to
    # parent when parent delete is cascading to child.
    opts = modal._meta
    if any(link != fromField for link in opts.concreteModel._meta.parents.values()):
      return False
    # Foreign keys pointing to this modal, both from m2m and other
    # model.
    for related in opts.getAllRelatedObjects(
        includeHidden=True, includeProxyEq=True):
      if related.field.rel.onDelete is not DO_NOTHING:
        return False
    for field in modal._meta.virtualFields:
      if hasattr(field, 'bulkRelatedObjects'):
        # It's something like generic foreign key.
        return False
    return True

  def collect(self, objs, source=None, nullable=False, collectRelated=True,
      sourceAttr=None, reverseDependency=False):
    """
    Adds 'objs' to the collection of objects to be deleted as well as all
    parent instances.  'objs' must be a homogeneous iterable collection of
    modal instances (e.g. a QuerySet).  If 'collectRelated' is True,
    related objects will be handled by their respective onDelete handler.

    If the call is the result of a cascade, 'source' should be the modal
    that caused it and 'nullable' should be set to True, if the relation
    can be null.

    If 'reverseDependency' is True, 'source' will be deleted before the
    current modal, rather than after. (Needed for cascading to parent
    model, the one case in which the cascade follows the forwards
    direction of an FK rather than the reverse direction.)
    """
    if self.canFastDelete(objs):
      self.fastDeletes.append(objs)
      return
    newObjs = self.add(objs, source, nullable,
              reverseDependency=reverseDependency)
    if not newObjs:
      return

    modal = newObjs[0].__class__

    # Recursively collect concrete modal's parent model, but not their
    # related objects. These will be found by meta.getAllRelatedObjects()
    concreteModel = modal._meta.concreteModel
    for ptr in six.itervalues(concreteModel._meta.parents):
      if ptr:
        # FIXME: This seems to be buggy and execute a query for each
        # parent object fetch. We have the parent data in the obj,
        # but we don't have a nice way to turn that data into parent
        # object instance.
        parentObjs = [getattr(obj, ptr.name) for obj in newObjs]
        self.collect(parentObjs, source=modal,
               sourceAttr=ptr.rel.relatedName,
               collectRelated=False,
               reverseDependency=True)

    if collectRelated:
      for related in modal._meta.getAllRelatedObjects(
          includeHidden=True, includeProxyEq=True):
        field = related.field
        if field.rel.onDelete == DO_NOTHING:
          continue
        subObjs = self.relatedObjects(related, newObjs)
        if self.canFastDelete(subObjs, fromField=field):
          self.fastDeletes.append(subObjs)
        elif subObjs:
          field.rel.onDelete(self, field, subObjs, self.using)
      for field in modal._meta.virtualFields:
        if hasattr(field, 'bulkRelatedObjects'):
          # Its something like generic foreign key.
          subObjs = field.bulkRelatedObjects(newObjs, self.using)
          self.collect(subObjs,
                 source=modal,
                 sourceAttr=field.rel.relatedName,
                 nullable=True)

  def relatedObjects(self, related, objs):
    """
    Gets a QuerySet of objects related to ``objs`` via the relation ``related``.

    """
    return related.modal._baseManager.using(self.using).filter(
      **{"%s__in" % related.field.name: objs}
    )

  def instancesWithModel(self):
    for modal, instances in six.iteritems(self.data):
      for obj in instances:
        yield modal, obj

  def sort(self):
    sortedModels = []
    concreteModels = set()
    model = list(self.data)
    while len(sortedModels) < len(model):
      found = False
      for modal in model:
        if modal in sortedModels:
          continue
        dependencies = self.dependencies.get(modal._meta.concreteModel)
        if not (dependencies and dependencies.difference(concreteModels)):
          sortedModels.append(modal)
          concreteModels.add(modal._meta.concreteModel)
          found = True
      if not found:
        return
    self.data = OrderedDict((modal, self.data[modal])
                for modal in sortedModels)

  def delete(self):
    # sort instance collections
    for modal, instances in self.data.items():
      self.data[modal] = sorted(instances, key=attrgetter("pk"))

    # if possible, bring the model in an order suitable for databases that
    # don't support transactions or cannot defer constraint checks until the
    # end of a transaction.
    self.sort()

    with transaction.commitOnSuccessUnlessManaged(using=self.using):
      # send preDelete signals
      for modal, obj in self.instancesWithModel():
        if not modal._meta.autoCreated:
          signals.preDelete.send(
            sender=modal, instance=obj, using=self.using
          )

      # fast deletes
      for qs in self.fastDeletes:
        qs._rawDelete(using=self.using)

      # update fields
      for modal, instancesForFieldvalues in six.iteritems(self.fieldUpdates):
        query = sql.UpdateQuery(modal)
        for (field, value), instances in six.iteritems(instancesForFieldvalues):
          query.updateBatch([obj.pk for obj in instances],
                    {field.name: value}, self.using)

      # reverse instance collections
      for instances in six.itervalues(self.data):
        instances.reverse()

      # delete instances
      for modal, instances in six.iteritems(self.data):
        query = sql.DeleteQuery(modal)
        pkList = [obj.pk for obj in instances]
        query.deleteBatch(pkList, self.using)

        if not modal._meta.autoCreated:
          for obj in instances:
            signals.postDelete.send(
              sender=modal, instance=obj, using=self.using
            )

    # update collected instances
    for modal, instancesForFieldvalues in six.iteritems(self.fieldUpdates):
      for (field, value), instances in six.iteritems(instancesForFieldvalues):
        for obj in instances:
          setattr(obj, field.attname, value)
    for modal, instances in six.iteritems(self.data):
      for instance in instances:
        setattr(instance, modal._meta.pk.attname, None)
