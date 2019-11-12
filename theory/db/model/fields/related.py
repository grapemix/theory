from __future__ import unicode_literals

from operator import attrgetter

from theory.apps import apps
from theory.core import checks
from theory.db import connection, connections, router, transaction
from theory.db.backends import utils
from theory.db.model import signals, Q
from theory.db.model.deletion import SET_NULL, SET_DEFAULT, CASCADE
from theory.db.model.fields import (AutoField, Field, IntegerField,
  PositiveIntegerField, PositiveSmallIntegerField, FieldDoesNotExist)
from theory.db.model.lookups import IsNull
from theory.db.model.related import RelatedObject, PathInfo
from theory.db.model.query import QuerySet
from theory.db.model.sql.datastructures import Col
from theory.utils.encoding import smartText
from theory.utils import six
from theory.utils.deprecation import RenameMethodsBase, RemovedInTheory20Warning
from theory.utils.translation import ugettextLazy as _
from theory.utils.functional import curry, cachedProperty
from theory.core import exceptions
from theory.gui.common.modelField import ModelChoiceField, ModelMultipleChoiceField

RECURSIVE_RELATIONSHIP_CONSTANT = 'self'


def addLazyRelation(cls, field, relation, operation):
  """
  Adds a lookup on ``cls`` when a related field is defined using a string,
  i.e.::

    class MyModel(Model):
      fk = ForeignKey("AnotherModel")

  This string can be:

    * RECURSIVE_RELATIONSHIP_CONSTANT (i.e. "self") to indicate a recursive
     relation.

    * The name of a modal (i.e "AnotherModel") to indicate another modal in
     the same app.

    * An app-label and modal name (i.e. "someapp.AnotherModel") to indicate
     another modal in a different app.

  If the other modal hasn't yet been loaded -- almost a given if you're using
  lazy relationships -- then the relation won't be set up until the
  classPrepared signal fires at the end of modal initialization.

  operation is the work that must be performed once the relation can be resolved.
  """
  # Check for recursive relations
  if relation == RECURSIVE_RELATIONSHIP_CONSTANT:
    appLabel = cls._meta.appLabel
    modelName = cls.__name__

  else:
    # Look for an "app.Model" relation

    if isinstance(relation, six.stringTypes):
      try:
        appLabel, modelName = relation.split(".")
      except ValueError:
        # If we can't split, assume a modal in current app
        appLabel = cls._meta.appLabel
        modelName = relation
    else:
      # it's actually a modal class
      appLabel = relation._meta.appLabel
      modelName = relation._meta.objectName

  # Try to look up the related modal, and if it's already loaded resolve the
  # string right away. If getModel returns None, it means that the related
  # modal isn't loaded yet, so we need to pend the relation until the class
  # is prepared.
  try:
    modal = cls._meta.apps.getRegisteredModel(appLabel, modelName)
  except LookupError:
    key = (appLabel, modelName)
    value = (cls, field, operation)
    cls._meta.apps._pendingLookups.setdefault(key, []).append(value)
  else:
    operation(field, modal, cls)


def doPendingLookups(sender, **kwargs):
  """
  Handle any pending relations to the sending modal. Sent from classPrepared.
  """
  key = (sender._meta.appLabel, sender.__name__)
  for cls, field, operation in sender._meta.apps._pendingLookups.pop(key, []):
    operation(field, sender, cls)

signals.classPrepared.connect(doPendingLookups)


class RelatedField(Field):
  def check(self, **kwargs):
    errors = super(RelatedField, self).check(**kwargs)
    errors.extend(self._checkRelationModelExists())
    errors.extend(self._checkReferencingToSwappedModel())
    errors.extend(self._checkClashes())
    return errors

  def _checkRelationModelExists(self):
    relIsMissing = self.rel.to not in apps.getModels()
    relIsString = isinstance(self.rel.to, six.stringTypes)
    modelName = self.rel.to if relIsString else self.rel.to._meta.objectName
    if relIsMissing and (relIsString or not self.rel.to._meta.swapped):
      return [
        checks.Error(
          ("Field defines a relation with modal '%s', which "
           "is either not installed, or is abstract.") % modelName,
          hint=None,
          obj=self,
          id='fields.E300',
        )
      ]
    return []

  def _checkReferencingToSwappedModel(self):
    if (self.rel.to not in apps.getModels() and
        not isinstance(self.rel.to, six.stringTypes) and
        self.rel.to._meta.swapped):
      modal = "%s.%s" % (
        self.rel.to._meta.appLabel,
        self.rel.to._meta.objectName
      )
      return [
        checks.Error(
          ("Field defines a relation with the modal '%s', "
           "which has been swapped out.") % modal,
          hint="Update the relation to point at 'settings.%s'." % self.rel.to._meta.swappable,
          obj=self,
          id='fields.E301',
        )
      ]
    return []

  def _checkClashes(self):
    """ Check accessor and reverse query name clashes. """

    from theory.db.model.base import ModelBase

    errors = []
    opts = self.modal._meta

    # `f.rel.to` may be a string instead of a modal. Skip if modal name is
    # not resolved.
    if not isinstance(self.rel.to, ModelBase):
      return []

    # If the field doesn't install backward relation on the target modal (so
    # `isHidden` returns True), then there are no clashes to check and we
    # can skip these fields.
    if self.rel.isHidden():
      return []

    try:
      self.related
    except AttributeError:
      return []

    # Consider that we are checking field `Model.foreign` and the model
    # are:
    #
    #     class Target(model.Model):
    #         modal = model.IntegerField()
    #         modalSet = model.IntegerField()
    #
    #     class Model(model.Model):
    #         foreign = model.ForeignKey(Target)
    #         m2m = model.ManyToManyField(Target)

    relOpts = self.rel.to._meta
    # relOpts.objectName == "Target"
    relName = self.related.getAccessorName()  # i. e. "modalSet"
    relQueryName = self.relatedQueryName()  # i. e. "modal"
    fieldName = "%s.%s" % (opts.objectName,
      self.name)  # i. e. "Model.field"

    # Check clashes between accessor or reverse query name of `field`
    # and any other field name -- i. e. accessor for Model.foreign is
    # modalSet and it clashes with Target.modalSet.
    potentialClashes = relOpts.fields + relOpts.manyToMany
    for clashField in potentialClashes:
      clashName = "%s.%s" % (relOpts.objectName,
        clashField.name)  # i. e. "Target.modalSet"
      if clashField.name == relName:
        errors.append(
          checks.Error(
            "Reverse accessor for '%s' clashes with field name '%s'." % (fieldName, clashName),
            hint=("Rename field '%s', or add/change a relatedName "
               "argument to the definition for field '%s'.") % (clashName, fieldName),
            obj=self,
            id='fields.E302',
          )
        )

      if clashField.name == relQueryName:
        errors.append(
          checks.Error(
            "Reverse query name for '%s' clashes with field name '%s'." % (fieldName, clashName),
            hint=("Rename field '%s', or add/change a relatedName "
               "argument to the definition for field '%s'.") % (clashName, fieldName),
            obj=self,
            id='fields.E303',
          )
        )

    # Check clashes between accessors/reverse query names of `field` and
    # any other field accessor -- i. e. Model.foreign accessor clashes with
    # Model.m2m accessor.
    potentialClashes = relOpts.getAllRelatedManyToManyObjects()
    potentialClashes += relOpts.getAllRelatedObjects()
    potentialClashes = (r for r in potentialClashes
      if r.field is not self)
    for clashField in potentialClashes:
      clashName = "%s.%s" % (  # i. e. "Model.m2m"
        clashField.modal._meta.objectName,
        clashField.field.name)
      if clashField.getAccessorName() == relName:
        errors.append(
          checks.Error(
            "Reverse accessor for '%s' clashes with reverse accessor for '%s'." % (fieldName, clashName),
            hint=("Add or change a relatedName argument "
               "to the definition for '%s' or '%s'.") % (fieldName, clashName),
            obj=self,
            id='fields.E304',
          )
        )

      if clashField.getAccessorName() == relQueryName:
        errors.append(
          checks.Error(
            "Reverse query name for '%s' clashes with reverse query name for '%s'." % (fieldName, clashName),
            hint=("Add or change a relatedName argument "
               "to the definition for '%s' or '%s'.") % (fieldName, clashName),
            obj=self,
            id='fields.E305',
          )
        )

    return errors

  def dbType(self, connection):
    '''By default related field will not have a column
      as it relates columns to another table'''
    return None

  def contributeToClass(self, cls, name, virtualOnly=False):
    sup = super(RelatedField, self)

    # Store the opts for relatedQueryName()
    self.opts = cls._meta

    if hasattr(sup, 'contributeToClass'):
      sup.contributeToClass(cls, name, virtualOnly=virtualOnly)

    if not cls._meta.abstract and self.rel.relatedName:
      relatedName = self.rel.relatedName % {
        'class': cls.__name__.lower(),
        'appLabel': cls._meta.appLabel.lower()
      }
      self.rel.relatedName = relatedName
    other = self.rel.to
    if isinstance(other, six.stringTypes) or other._meta.pk is None:
      def resolveRelatedClass(field, modal, cls):
        field.rel.to = modal
        field.doRelatedClass(modal, cls)
      addLazyRelation(cls, self, other, resolveRelatedClass)
    else:
      self.doRelatedClass(other, cls)

  @property
  def swappableSetting(self):
    """
    Gets the setting that this is powered from for swapping, or None
    if it's not swapped in / marked with swappable=False.
    """
    if self.swappable:
      # Work out string form of "to"
      if isinstance(self.rel.to, six.stringTypes):
        toString = self.rel.to
      else:
        toString = "%s.%s" % (
          self.rel.to._meta.appLabel,
          self.rel.to._meta.objectName,
        )
      # See if anything swapped/swappable matches
      for modal in apps.getModels(includeSwapped=True):
        if modal._meta.swapped:
          if modal._meta.swapped == toString:
            return modal._meta.swappable
        if ("%s.%s" % (modal._meta.appLabel, modal._meta.objectName)) == toString and modal._meta.swappable:
          return modal._meta.swappable
    return None

  def setAttributesFromRel(self):
    self.name = self.name or (self.rel.to._meta.modelName + '_' + self.rel.to._meta.pk.name)
    if self.verboseName is None:
      self.verboseName = self.rel.to._meta.verboseName
    self.rel.setFieldName()

  def doRelatedClass(self, other, cls):
    self.setAttributesFromRel()
    self.related = RelatedObject(other, cls, self)
    if not cls._meta.abstract:
      self.contributeToRelatedClass(other, self.related)

  def getLimitChoicesTo(self):
    """Returns 'limitChoicesTo' for this modal field.

    If it is a callable, it will be invoked and the result will be
    returned.
    """
    if callable(self.rel.limitChoicesTo):
      return self.rel.limitChoicesTo()
    return self.rel.limitChoicesTo

  def formfield(self, **kwargs):
    """Passes ``limitChoicesTo`` to field being constructed.

    Only passes it if there is a type that supports related fields.
    This is a similar strategy used to pass the ``queryset`` to the field
    being constructed.
    """
    defaults = {}
    if hasattr(self.rel, 'getRelatedField'):
      # If this is a callable, do not invoke it here. Just pass
      # it in the defaults for when the form class will later be
      # instantiated.
      limitChoicesTo = self.rel.limitChoicesTo
      defaults.update({
        'limitChoicesTo': limitChoicesTo,
      })
    defaults.update(kwargs)
    return super(RelatedField, self).formfield(**defaults)

  def relatedQueryName(self):
    # This method defines the name that can be used to identify this
    # related object in a table-spanning query. It uses the lower-cased
    # objectName by default, but this can be overridden with the
    # "relatedName" option.
    return self.rel.relatedQueryName or self.rel.relatedName or self.opts.modelName


class RenameRelatedObjectDescriptorMethods(RenameMethodsBase):
  renamedMethods = (
    ('getQuerySet', 'getQueryset', RemovedInTheory20Warning),
    ('getPrefetchQuerySet', 'getPrefetchQueryset', RemovedInTheory20Warning),
  )


class SingleRelatedObjectDescriptor(six.withMetaclass(RenameRelatedObjectDescriptorMethods)):
  # This class provides the functionality that makes the related-object
  # managers available as attributes on a modal class, for fields that have
  # a single "remote" value, on the class pointed to by a related field.
  # In the example "place.restaurant", the restaurant attribute is a
  # SingleRelatedObjectDescriptor instance.
  def __init__(self, related):
    self.related = related
    self.cacheName = related.getCacheName()

  @cachedProperty
  def RelatedObjectDoesNotExist(self):
    # The exception isn't created at initialization time for the sake of
    # consistency with `ReverseSingleRelatedObjectDescriptor`.
    return type(
      str('RelatedObjectDoesNotExist'),
      (self.related.modal.DoesNotExist, AttributeError),
      {}
    )

  def isCached(self, instance):
    return hasattr(instance, self.cacheName)

  def getQueryset(self, **hints):
    # Gotcha: we return a `Manager` instance (i.e. not a `QuerySet`)!
    return self.related.modal._baseManager.dbManager(hints=hints)

  def getPrefetchQueryset(self, instances, queryset=None):
    if queryset is None:
      # Despite its name `getQueryset()` returns an instance of
      # `Manager`, therefore we call `all()` to normalize to `QuerySet`.
      queryset = self.getQueryset().all()
    queryset._addHints(instance=instances[0])

    relObjAttr = attrgetter(self.related.field.attname)
    instanceAttr = lambda obj: obj._getPkVal()
    instancesDict = dict((instanceAttr(inst), inst) for inst in instances)
    query = {'%s__in' % self.related.field.name: instances}
    queryset = queryset.filter(**query)

    # Since we're going to assign directly in the cache,
    # we must manage the reverse relation cache manually.
    relObjCacheName = self.related.field.getCacheName()
    for relObj in queryset:
      instance = instancesDict[relObjAttr(relObj)]
      setattr(relObj, relObjCacheName, instance)
    return queryset, relObjAttr, instanceAttr, True, self.cacheName

  def __get__(self, instance, instanceType=None):
    if instance is None:
      return self
    try:
      relObj = getattr(instance, self.cacheName)
    except AttributeError:
      relatedPk = instance._getPkVal()
      if relatedPk is None:
        relObj = None
      else:
        params = {}
        for lhField, rhField in self.related.field.relatedFields:
          params['%s__%s' % (self.related.field.name, rhField.name)] = getattr(instance, rhField.attname)
        try:
          relObj = self.getQueryset(instance=instance).get(**params)
        except self.related.modal.DoesNotExist:
          relObj = None
        else:
          setattr(relObj, self.related.field.getCacheName(), instance)
      setattr(instance, self.cacheName, relObj)
    if relObj is None:
      raise self.RelatedObjectDoesNotExist(
        "%s has no %s." % (
          instance.__class__.__name__,
          self.related.getAccessorName()
        )
      )
    else:
      return relObj

  def __set__(self, instance, value):
    # The similarity of the code below to the code in
    # ReverseSingleRelatedObjectDescriptor is annoying, but there's a bunch
    # of small differences that would make a common base class convoluted.

    # If null=True, we can assign null here, but otherwise the value needs
    # to be an instance of the related class.
    if value is None and self.related.field.null is False:
      raise ValueError(
        'Cannot assign None: "%s.%s" does not allow null values.' % (
          instance._meta.objectName,
          self.related.getAccessorName(),
        )
      )
    elif value is not None and not isinstance(value, self.related.modal):
      raise ValueError(
        'Cannot assign "%r": "%s.%s" must be a "%s" instance.' % (
          value,
          instance._meta.objectName,
          self.related.getAccessorName(),
          self.related.opts.objectName,
        )
      )
    elif value is not None:
      if instance._state.db is None:
        instance._state.db = router.dbForWrite(instance.__class__, instance=value)
      elif value._state.db is None:
        value._state.db = router.dbForWrite(value.__class__, instance=instance)
      elif value._state.db is not None and instance._state.db is not None:
        if not router.allowRelation(value, instance):
          raise ValueError('Cannot assign "%r": the current database router prevents this relation.' % value)

    relatedPk = tuple(getattr(instance, field.attname) for field in self.related.field.foreignRelatedFields)
    if None in relatedPk:
      raise ValueError(
        'Cannot assign "%r": "%s" instance isn\'t saved in the database.' %
        (value, instance._meta.objectName)
      )

    # Set the value of the related field to the value of the related object's related field
    for index, field in enumerate(self.related.field.localRelatedFields):
      setattr(value, field.attname, relatedPk[index])

    # Since we already know what the related object is, seed the related
    # object caches now, too. This avoids another db hit if you get the
    # object you just set.
    setattr(instance, self.cacheName, value)
    setattr(value, self.related.field.getCacheName(), instance)


class ReverseSingleRelatedObjectDescriptor(six.withMetaclass(RenameRelatedObjectDescriptorMethods)):
  # This class provides the functionality that makes the related-object
  # managers available as attributes on a modal class, for fields that have
  # a single "remote" value, on the class that defines the related field.
  # In the example "choice.poll", the poll attribute is a
  # ReverseSingleRelatedObjectDescriptor instance.
  def __init__(self, fieldWithRel):
    self.field = fieldWithRel
    self.cacheName = self.field.getCacheName()

  @cachedProperty
  def RelatedObjectDoesNotExist(self):
    # The exception can't be created at initialization time since the
    # related modal might not be resolved yet; `rel.to` might still be
    # a string modal reference.
    return type(
      str('RelatedObjectDoesNotExist'),
      (self.field.rel.to.DoesNotExist, AttributeError),
      {}
    )

  def isCached(self, instance):
    return hasattr(instance, self.cacheName)

  def getQueryset(self, **hints):
    relMgr = self.field.rel.to._defaultManager.dbManager(hints=hints)
    # If the related manager indicates that it should be used for
    # related fields, respect that.
    if getattr(relMgr, 'useForRelatedFields', False):
      # Gotcha: we return a `Manager` instance (i.e. not a `QuerySet`)!
      return relMgr
    else:
      return QuerySet(self.field.rel.to, hints=hints)

  def getPrefetchQueryset(self, instances, queryset=None):
    if queryset is None:
      # Despite its name `getQueryset()` may return an instance of
      # `Manager`, therefore we call `all()` to normalize to `QuerySet`.
      queryset = self.getQueryset().all()
    queryset._addHints(instance=instances[0])

    relObjAttr = self.field.getForeignRelatedValue
    instanceAttr = self.field.getLocalRelatedValue
    instancesDict = dict((instanceAttr(inst), inst) for inst in instances)
    relatedField = self.field.foreignRelatedFields[0]

    # FIXME: This will need to be revisited when we introduce support for
    # composite fields. In the meantime we take this practical approach to
    # solve a regression on 1.6 when the reverse manager in hidden
    # (relatedName ends with a '+'). Refs #21410.
    # The check for len(...) == 1 is a special case that allows the query
    # to be join-less and smaller. Refs #21760.
    if self.field.rel.isHidden() or len(self.field.foreignRelatedFields) == 1:
      query = {'%s__in' % relatedField.name: set(instanceAttr(inst)[0] for inst in instances)}
    else:
      query = {'%s__in' % self.field.relatedQueryName(): instances}
    queryset = queryset.filter(**query)

    # Since we're going to assign directly in the cache,
    # we must manage the reverse relation cache manually.
    if not self.field.rel.multiple:
      relObjCacheName = self.field.related.getCacheName()
      for relObj in queryset:
        instance = instancesDict[relObjAttr(relObj)]
        setattr(relObj, relObjCacheName, instance)
    return queryset, relObjAttr, instanceAttr, True, self.cacheName

  def __get__(self, instance, instanceType=None):
    if instance is None:
      return self
    try:
      relObj = getattr(instance, self.cacheName)
    except AttributeError:
      val = self.field.getLocalRelatedValue(instance)
      if None in val:
        relObj = None
      else:
        params = dict(
          (rhField.attname, getattr(instance, lhField.attname))
          for lhField, rhField in self.field.relatedFields)
        qs = self.getQueryset(instance=instance)
        extraFilter = self.field.getExtraDescriptorFilter(instance)
        if isinstance(extraFilter, dict):
          params.update(extraFilter)
          qs = qs.filter(**params)
        else:
          qs = qs.filter(extraFilter, **params)
        # Assuming the database enforces foreign keys, this won't fail.
        relObj = qs.get()
        if not self.field.rel.multiple:
          setattr(relObj, self.field.related.getCacheName(), instance)
      setattr(instance, self.cacheName, relObj)
    if relObj is None and not self.field.null:
      raise self.RelatedObjectDoesNotExist(
        "%s has no %s." % (self.field.modal.__name__, self.field.name)
      )
    else:
      return relObj

  def __set__(self, instance, value):
    # If null=True, we can assign null here, but otherwise the value needs
    # to be an instance of the related class.
    if value is None and self.field.null is False:
      raise ValueError(
        'Cannot assign None: "%s.%s" does not allow null values.' %
        (instance._meta.objectName, self.field.name)
      )
    elif value is not None and not isinstance(value, self.field.rel.to):
      raise ValueError(
        'Cannot assign "%r": "%s.%s" must be a "%s" instance.' % (
          value,
          instance._meta.objectName,
          self.field.name,
          self.field.rel.to._meta.objectName,
        )
      )
    elif value is not None:
      if instance._state.db is None:
        instance._state.db = router.dbForWrite(instance.__class__, instance=value)
      elif value._state.db is None:
        value._state.db = router.dbForWrite(value.__class__, instance=instance)
      elif value._state.db is not None and instance._state.db is not None:
        if not router.allowRelation(value, instance):
          raise ValueError('Cannot assign "%r": the current database router prevents this relation.' % value)

    # If we're setting the value of a OneToOneField to None, we need to clear
    # out the cache on any old related object. Otherwise, deleting the
    # previously-related object will also cause this object to be deleted,
    # which is wrong.
    if value is None:
      # Look up the previously-related object, which may still be available
      # since we've not yet cleared out the related field.
      # Use the cache directly, instead of the accessor; if we haven't
      # populated the cache, then we don't care - we're only accessing
      # the object to invalidate the accessor cache, so there's no
      # need to populate the cache just to expire it again.
      related = getattr(instance, self.cacheName, None)

      # If we've got an old related object, we need to clear out its
      # cache. This cache also might not exist if the related object
      # hasn't been accessed yet.
      if related is not None:
        setattr(related, self.field.related.getCacheName(), None)

    # Set the value of the related field
    for lhField, rhField in self.field.relatedFields:
      try:
        setattr(instance, lhField.attname, getattr(value, rhField.attname))
      except AttributeError:
        setattr(instance, lhField.attname, None)

    # Since we already know what the related object is, seed the related
    # object caches now, too. This avoids another db hit if you get the
    # object you just set.
    setattr(instance, self.cacheName, value)
    if value is not None and not self.field.rel.multiple:
      setattr(value, self.field.related.getCacheName(), instance)


def createForeignRelatedManager(superclass, relField, relModel):
  class RelatedManager(superclass):
    def __init__(self, instance):
      super(RelatedManager, self).__init__()
      self.instance = instance
      self.coreFilters = {'%s__exact' % relField.name: instance}
      self.modal = relModel

    def __call__(self, **kwargs):
      # We use **kwargs rather than a kwarg argument to enforce the
      # `manager='managerName'` syntax.
      manager = getattr(self.modal, kwargs.pop('manager'))
      managerClass = createForeignRelatedManager(manager.__class__, relField, relModel)
      return managerClass(self.instance)
    doNotCallInTemplates = True

    def getQueryset(self):
      try:
        return self.instance._prefetchedObjectsCache[relField.relatedQueryName()]
      except (AttributeError, KeyError):
        db = self._db or router.dbForRead(self.modal, instance=self.instance)
        emptyStringsAsNull = connections[db].features.interpretsEmptyStringsAsNulls
        qs = super(RelatedManager, self).getQueryset()
        qs._addHints(instance=self.instance)
        if self._db:
          qs = qs.using(self._db)
        qs = qs.filter(**self.coreFilters)
        for field in relField.foreignRelatedFields:
          val = getattr(self.instance, field.attname)
          if val is None or (val == '' and emptyStringsAsNull):
            return qs.none()
        qs._knownRelatedObjects = {relField: {self.instance.pk: self.instance}}
        return qs

    def getPrefetchQueryset(self, instances, queryset=None):
      if queryset is None:
        queryset = super(RelatedManager, self).getQueryset()

      queryset._addHints(instance=instances[0])
      queryset = queryset.using(queryset._db or self._db)

      relObjAttr = relField.getLocalRelatedValue
      instanceAttr = relField.getForeignRelatedValue
      instancesDict = dict((instanceAttr(inst), inst) for inst in instances)
      query = {'%s__in' % relField.name: instances}
      queryset = queryset.filter(**query)

      # Since we just bypassed this class' getQueryset(), we must manage
      # the reverse relation manually.
      for relObj in queryset:
        instance = instancesDict[relObjAttr(relObj)]
        setattr(relObj, relField.name, instance)
      cacheName = relField.relatedQueryName()
      return queryset, relObjAttr, instanceAttr, False, cacheName

    def add(self, *objs):
      objs = list(objs)
      db = router.dbForWrite(self.modal, instance=self.instance)
      with transaction.commitOnSuccessUnlessManaged(
          using=db, savepoint=False):
        for obj in objs:
          if not isinstance(obj, self.modal):
            raise TypeError("'%s' instance expected, got %r" %
                    (self.modal._meta.objectName, obj))
          setattr(obj, relField.name, self.instance)
          obj.save()
    add.altersData = True

    def create(self, **kwargs):
      kwargs[relField.name] = self.instance
      db = router.dbForWrite(self.modal, instance=self.instance)
      return super(RelatedManager, self.dbManager(db)).create(**kwargs)
    create.altersData = True

    def getOrCreate(self, **kwargs):
      # Update kwargs with the related object that this
      # ForeignRelatedObjectsDescriptor knows about.
      kwargs[relField.name] = self.instance
      db = router.dbForWrite(self.modal, instance=self.instance)
      return super(RelatedManager, self.dbManager(db)).getOrCreate(**kwargs)
    getOrCreate.altersData = True

    # remove() and clear() are only provided if the ForeignKey can have a value of null.
    if relField.null:
      def remove(self, *objs, **kwargs):
        if not objs:
          return
        bulk = kwargs.pop('bulk', True)
        val = relField.getForeignRelatedValue(self.instance)
        oldIds = set()
        for obj in objs:
          # Is obj actually part of this descriptor set?
          if relField.getLocalRelatedValue(obj) == val:
            oldIds.add(obj.pk)
          else:
            raise relField.rel.to.DoesNotExist("%r is not related to %r." % (obj, self.instance))
        self._clear(self.filter(pk__in=oldIds), bulk)
      remove.altersData = True

      def clear(self, **kwargs):
        bulk = kwargs.pop('bulk', True)
        self._clear(self, bulk)
      clear.altersData = True

      def _clear(self, queryset, bulk):
        db = router.dbForWrite(self.modal, instance=self.instance)
        queryset = queryset.using(db)
        if bulk:
          queryset.update(**{relField.name: None})
        else:
          with transaction.commitOnSuccessUnlessManaged(using=db, savepoint=False):
            for obj in queryset:
              setattr(obj, relField.name, None)
              obj.save(updateFields=[relField.name])
      _clear.altersData = True

  return RelatedManager


class ForeignRelatedObjectsDescriptor(object):
  # This class provides the functionality that makes the related-object
  # managers available as attributes on a modal class, for fields that have
  # multiple "remote" values and have a ForeignKey pointed at them by
  # some other modal. In the example "poll.choiceSet", the choiceSet
  # attribute is a ForeignRelatedObjectsDescriptor instance.
  def __init__(self, related):
    self.related = related   # RelatedObject instance

  def __get__(self, instance, instanceType=None):
    if instance is None:
      return self

    return self.relatedManagerCls(instance)

  def __set__(self, instance, value):
    manager = self.__get__(instance)
    # If the foreign key can support nulls, then completely clear the related set.
    # Otherwise, just move the named objects into the set.
    if self.related.field.null:
      manager.clear()
    manager.add(*value)

  @cachedProperty
  def relatedManagerCls(self):
    # Dynamically create a class that subclasses the related modal's default
    # manager.
    return createForeignRelatedManager(
      self.related.modal._defaultManager.__class__,
      self.related.field,
      self.related.modal,
    )


def createManyRelatedManager(superclass, rel):
  """Creates a manager that subclasses 'superclass' (which is a Manager)
  and adds behavior for many-to-many related objects."""
  class ManyRelatedManager(superclass):
    def __init__(self, modal=None, queryFieldName=None, instance=None, symmetrical=None,
           sourceFieldName=None, targetFieldName=None, reverse=False,
           through=None, prefetchCacheName=None):
      super(ManyRelatedManager, self).__init__()
      self.modal = modal
      self.queryFieldName = queryFieldName

      sourceField = through._meta.getField(sourceFieldName)
      sourceRelatedFields = sourceField.relatedFields

      self.coreFilters = {}
      for lhField, rhField in sourceRelatedFields:
        self.coreFilters['%s__%s' % (queryFieldName, rhField.name)] = getattr(instance, rhField.attname)

      self.instance = instance
      self.symmetrical = symmetrical
      self.sourceField = sourceField
      self.targetField = through._meta.getField(targetFieldName)
      self.sourceFieldName = sourceFieldName
      self.targetFieldName = targetFieldName
      self.reverse = reverse
      self.through = through
      self.prefetchCacheName = prefetchCacheName
      self.relatedVal = sourceField.getForeignRelatedValue(instance)
      if None in self.relatedVal:
        raise ValueError('"%r" needs to have a value for field "%s" before '
                 'this many-to-many relationship can be used.' %
                 (instance, sourceFieldName))
      # Even if this relation is not to pk, we require still pk value.
      # The wish is that the instance has been already saved to DB,
      # although having a pk value isn't a guarantee of that.
      if instance.pk is None:
        raise ValueError("%r instance needs to have a primary key value before "
                 "a many-to-many relationship can be used." %
                 instance.__class__.__name__)

    def __call__(self, **kwargs):
      # We use **kwargs rather than a kwarg argument to enforce the
      # `manager='managerName'` syntax.
      manager = getattr(self.modal, kwargs.pop('manager'))
      managerClass = createManyRelatedManager(manager.__class__, rel)
      return managerClass(
        modal=self.modal,
        queryFieldName=self.queryFieldName,
        instance=self.instance,
        symmetrical=self.symmetrical,
        sourceFieldName=self.sourceFieldName,
        targetFieldName=self.targetFieldName,
        reverse=self.reverse,
        through=self.through,
        prefetchCacheName=self.prefetchCacheName,
      )
    doNotCallInTemplates = True

    def _buildRemoveFilters(self, removedVals):
      filters = Q(**{self.sourceFieldName: self.relatedVal})
      # No need to add a subquery condition if removedVals is a QuerySet without
      # filters.
      removedValsFilters = (not isinstance(removedVals, QuerySet) or
                  removedVals._hasFilters())
      if removedValsFilters:
        filters &= Q(**{'%s__in' % self.targetFieldName: removedVals})
      if self.symmetrical:
        symmetricalFilters = Q(**{self.targetFieldName: self.relatedVal})
        if removedValsFilters:
          symmetricalFilters &= Q(
            **{'%s__in' % self.sourceFieldName: removedVals})
        filters |= symmetricalFilters
      return filters

    def getQueryset(self):
      try:
        return self.instance._prefetchedObjectsCache[self.prefetchCacheName]
      except (AttributeError, KeyError):
        qs = super(ManyRelatedManager, self).getQueryset()
        qs._addHints(instance=self.instance)
        if self._db:
          qs = qs.using(self._db)
        return qs._nextIsSticky().filter(**self.coreFilters)

    def getPrefetchQueryset(self, instances, queryset=None):
      if queryset is None:
        queryset = super(ManyRelatedManager, self).getQueryset()

      queryset._addHints(instance=instances[0])
      queryset = queryset.using(queryset._db or self._db)

      query = {'%s__in' % self.queryFieldName: instances}
      queryset = queryset._nextIsSticky().filter(**query)

      # M2M: need to annotate the query in order to get the primary modal
      # that the secondary modal was actually related to. We know that
      # there will already be a join on the join table, so we can just add
      # the select.

      # For non-autocreated 'through' model, can't assume we are
      # dealing with PK values.
      fk = self.through._meta.getField(self.sourceFieldName)
      joinTable = self.through._meta.dbTable
      connection = connections[queryset.db]
      qn = connection.ops.quoteName
      queryset = queryset.extra(select=dict(
        ('_prefetchRelatedVal_%s' % f.attname,
        '%s.%s' % (qn(joinTable), qn(f.column))) for f in fk.localRelatedFields))
      return (queryset,
          lambda result: tuple(getattr(result, '_prefetchRelatedVal_%s' % f.attname) for f in fk.localRelatedFields),
          lambda inst: tuple(getattr(inst, f.attname) for f in fk.foreignRelatedFields),
          False,
          self.prefetchCacheName)

    def add(self, *objs):
      if not rel.through._meta.autoCreated:
        opts = self.through._meta
        raise AttributeError(
          "Cannot use add() on a ManyToManyField which specifies an intermediary modal. Use %s.%s's Manager instead." %
          (opts.appLabel, opts.objectName)
        )
      self._addItems(self.sourceFieldName, self.targetFieldName, *objs)

      # If this is a symmetrical m2m relation to self, add the mirror entry in the m2m table
      if self.symmetrical:
        self._addItems(self.targetFieldName, self.sourceFieldName, *objs)
    add.altersData = True

    def remove(self, *objs):
      if not rel.through._meta.autoCreated:
        opts = self.through._meta
        raise AttributeError(
          "Cannot use remove() on a ManyToManyField which specifies an intermediary modal. Use %s.%s's Manager instead." %
          (opts.appLabel, opts.objectName)
        )
      self._removeItems(self.sourceFieldName, self.targetFieldName, *objs)
    remove.altersData = True

    def clear(self):
      db = router.dbForWrite(self.through, instance=self.instance)

      signals.m2mChanged.send(sender=self.through, action="preClear",
        instance=self.instance, reverse=self.reverse,
        modal=self.modal, pkSet=None, using=db)

      filters = self._buildRemoveFilters(super(ManyRelatedManager, self).getQueryset().using(db))
      self.through._defaultManager.using(db).filter(filters).delete()

      signals.m2mChanged.send(sender=self.through, action="postClear",
        instance=self.instance, reverse=self.reverse,
        modal=self.modal, pkSet=None, using=db)
    clear.altersData = True

    def create(self, **kwargs):
      # This check needs to be done here, since we can't later remove this
      # from the method lookup table, as we do with add and remove.
      if not self.through._meta.autoCreated:
        opts = self.through._meta
        raise AttributeError(
          "Cannot use create() on a ManyToManyField which specifies an intermediary modal. Use %s.%s's Manager instead." %
          (opts.appLabel, opts.objectName)
        )
      db = router.dbForWrite(self.instance.__class__, instance=self.instance)
      newObj = super(ManyRelatedManager, self.dbManager(db)).create(**kwargs)
      self.add(newObj)
      return newObj
    create.altersData = True

    def getOrCreate(self, **kwargs):
      db = router.dbForWrite(self.instance.__class__, instance=self.instance)
      obj, created = \
        super(ManyRelatedManager, self.dbManager(db)).getOrCreate(**kwargs)
      # We only need to add() if created because if we got an object back
      # from get() then the relationship already exists.
      if created:
        self.add(obj)
      return obj, created
    getOrCreate.altersData = True

    def _addItems(self, sourceFieldName, targetFieldName, *objs):
      # sourceFieldName: the PK fieldname in join table for the source object
      # targetFieldName: the PK fieldname in join table for the target object
      # *objs - objects to add. Either object instances, or primary keys of object instances.

      # If there aren't any objects, there is nothing to do.
      from theory.db.model import Model
      if objs:
        newIds = set()
        for obj in objs:
          if isinstance(obj, self.modal):
            if not router.allowRelation(obj, self.instance):
              raise ValueError(
                'Cannot add "%r": instance is on database "%s", value is on database "%s"' %
                (obj, self.instance._state.db, obj._state.db)
              )
            fkVal = self.through._meta.getField(
              targetFieldName).getForeignRelatedValue(obj)[0]
            if fkVal is None:
              raise ValueError(
                'Cannot add "%r": the value for field "%s" is None' %
                (obj, targetFieldName)
              )
            newIds.add(fkVal)
          elif isinstance(obj, Model):
            raise TypeError(
              "'%s' instance expected, got %r" %
              (self.modal._meta.objectName, obj)
            )
          else:
            newIds.add(obj)
        db = router.dbForWrite(self.through, instance=self.instance)
        vals = self.through._defaultManager.using(db).valuesList(targetFieldName, flat=True)
        vals = vals.filter(**{
          sourceFieldName: self.relatedVal[0],
          '%s__in' % targetFieldName: newIds,
        })
        newIds = newIds - set(vals)

        if self.reverse or sourceFieldName == self.sourceFieldName:
          # Don't send the signal when we are inserting the
          # duplicate data row for symmetrical reverse entries.
          signals.m2mChanged.send(sender=self.through, action='preAdd',
            instance=self.instance, reverse=self.reverse,
            modal=self.modal, pkSet=newIds, using=db)
        # Add the ones that aren't there already
        self.through._defaultManager.using(db).bulkCreate([
          self.through(**{
            '%sId' % sourceFieldName: self.relatedVal[0],
            '%sId' % targetFieldName: objId,
          })
          for objId in newIds
        ])

        if self.reverse or sourceFieldName == self.sourceFieldName:
          # Don't send the signal when we are inserting the
          # duplicate data row for symmetrical reverse entries.
          signals.m2mChanged.send(sender=self.through, action='postAdd',
            instance=self.instance, reverse=self.reverse,
            modal=self.modal, pkSet=newIds, using=db)

    def _removeItems(self, sourceFieldName, targetFieldName, *objs):
      # sourceFieldName: the PK colname in join table for the source object
      # targetFieldName: the PK colname in join table for the target object
      # *objs - objects to remove
      if not objs:
        return

      # Check that all the objects are of the right type
      oldIds = set()
      for obj in objs:
        if isinstance(obj, self.modal):
          fkVal = self.targetField.getForeignRelatedValue(obj)[0]
          oldIds.add(fkVal)
        else:
          oldIds.add(obj)

      db = router.dbForWrite(self.through, instance=self.instance)

      # Send a signal to the other end if need be.
      signals.m2mChanged.send(sender=self.through, action="preRemove",
        instance=self.instance, reverse=self.reverse,
        modal=self.modal, pkSet=oldIds, using=db)
      targetModelQs = super(ManyRelatedManager, self).getQueryset()
      if targetModelQs._hasFilters():
        oldVals = targetModelQs.using(db).filter(**{
          '%s__in' % self.targetField.relatedField.attname: oldIds})
      else:
        oldVals = oldIds
      filters = self._buildRemoveFilters(oldVals)
      self.through._defaultManager.using(db).filter(filters).delete()

      signals.m2mChanged.send(sender=self.through, action="postRemove",
        instance=self.instance, reverse=self.reverse,
        modal=self.modal, pkSet=oldIds, using=db)

  return ManyRelatedManager


class ManyRelatedObjectsDescriptor(object):
  # This class provides the functionality that makes the related-object
  # managers available as attributes on a modal class, for fields that have
  # multiple "remote" values and have a ManyToManyField pointed at them by
  # some other modal (rather than having a ManyToManyField themselves).
  # In the example "publication.articleSet", the articleSet attribute is a
  # ManyRelatedObjectsDescriptor instance.
  def __init__(self, related):
    self.related = related   # RelatedObject instance

  @cachedProperty
  def relatedManagerCls(self):
    # Dynamically create a class that subclasses the related
    # modal's default manager.
    return createManyRelatedManager(
      self.related.modal._defaultManager.__class__,
      self.related.field.rel
    )

  def __get__(self, instance, instanceType=None):
    if instance is None:
      return self

    relModel = self.related.modal

    manager = self.relatedManagerCls(
      modal=relModel,
      queryFieldName=self.related.field.name,
      prefetchCacheName=self.related.field.relatedQueryName(),
      instance=instance,
      symmetrical=False,
      sourceFieldName=self.related.field.m2mReverseFieldName(),
      targetFieldName=self.related.field.m2mFieldName(),
      reverse=True,
      through=self.related.field.rel.through,
    )

    return manager

  def __set__(self, instance, value):
    if not self.related.field.rel.through._meta.autoCreated:
      opts = self.related.field.rel.through._meta
      raise AttributeError("Cannot set values on a ManyToManyField which specifies an intermediary modal. Use %s.%s's Manager instead." % (opts.appLabel, opts.objectName))

    manager = self.__get__(instance)
    manager.clear()
    manager.add(*value)


class ReverseManyRelatedObjectsDescriptor(object):
  # This class provides the functionality that makes the related-object
  # managers available as attributes on a modal class, for fields that have
  # multiple "remote" values and have a ManyToManyField defined in their
  # modal (rather than having another modal pointed *at* them).
  # In the example "article.publications", the publications attribute is a
  # ReverseManyRelatedObjectsDescriptor instance.
  def __init__(self, m2mField):
    self.field = m2mField

  @property
  def through(self):
    # through is provided so that you have easy access to the through
    # modal (Book.authors.through) for inlines, etc. This is done as
    # a property to ensure that the fully resolved value is returned.
    return self.field.rel.through

  @cachedProperty
  def relatedManagerCls(self):
    # Dynamically create a class that subclasses the related modal's
    # default manager.
    return createManyRelatedManager(
      self.field.rel.to._defaultManager.__class__,
      self.field.rel
    )

  def __get__(self, instance, instanceType=None):
    if instance is None:
      return self

    manager = self.relatedManagerCls(
      modal=self.field.rel.to,
      queryFieldName=self.field.relatedQueryName(),
      prefetchCacheName=self.field.name,
      instance=instance,
      symmetrical=self.field.rel.symmetrical,
      sourceFieldName=self.field.m2mFieldName(),
      targetFieldName=self.field.m2mReverseFieldName(),
      reverse=False,
      through=self.field.rel.through,
    )

    return manager

  def __set__(self, instance, value):
    if not self.field.rel.through._meta.autoCreated:
      opts = self.field.rel.through._meta
      raise AttributeError("Cannot set values on a ManyToManyField which specifies an intermediary modal.  Use %s.%s's Manager instead." % (opts.appLabel, opts.objectName))

    manager = self.__get__(instance)
    # clear() can change expected output of 'value' queryset, we force evaluation
    # of queryset before clear; ticket #19816
    value = tuple(value)
    manager.clear()
    manager.add(*value)


class ForeignObjectRel(object):
  def __init__(self, field, to, relatedName=None, limitChoicesTo=None,
         parentLink=False, onDelete=None, relatedQueryName=None):
    try:
      to._meta
    except AttributeError:  # to._meta doesn't exist, so it must be RECURSIVE_RELATIONSHIP_CONSTANT
      assert isinstance(to, six.stringTypes), "'to' must be either a modal, a modal name or the string %r" % RECURSIVE_RELATIONSHIP_CONSTANT

    self.field = field
    self.to = to
    self.relatedName = relatedName
    self.relatedQueryName = relatedQueryName
    self.limitChoicesTo = {} if limitChoicesTo is None else limitChoicesTo
    self.multiple = True
    self.parentLink = parentLink
    self.onDelete = onDelete

  def isHidden(self):
    "Should the related object be hidden?"
    return self.relatedName and self.relatedName[-1] == '+'

  def getJoiningColumns(self):
    return self.field.getReverseJoiningColumns()

  def getExtraRestriction(self, whereClass, alias, relatedAlias):
    return self.field.getExtraRestriction(whereClass, relatedAlias, alias)

  def setFieldName(self):
    """
    Sets the related field's name, this is not available until later stages
    of app loading, so setFieldName is called from
    setAttributesFromRel()
    """
    # By default foreign object doesn't relate to any remote field (for
    # example custom multicolumn joins currently have no remote field).
    self.fieldName = None

  def getLookupConstraint(self, constraintClass, alias, targets, sources, lookupType,
               rawValue):
    return self.field.getLookupConstraint(constraintClass, alias, targets, sources,
                        lookupType, rawValue)


class ManyToOneRel(ForeignObjectRel):
  def __init__(self, field, to, fieldName, relatedName=None, limitChoicesTo=None,
         parentLink=False, onDelete=None, relatedQueryName=None):
    super(ManyToOneRel, self).__init__(
      field, to, relatedName=relatedName, limitChoicesTo=limitChoicesTo,
      parentLink=parentLink, onDelete=onDelete, relatedQueryName=relatedQueryName)
    self.fieldName = fieldName

  def getRelatedField(self):
    """
    Returns the Field in the 'to' object to which this relationship is
    tied.
    """
    data = self.to._meta.getFieldByName(self.fieldName)
    if not data[2]:
      raise FieldDoesNotExist("No related field named '%s'" %
          self.fieldName)
    return data[0]

  def setFieldName(self):
    self.fieldName = self.fieldName or self.to._meta.pk.name


class OneToOneRel(ManyToOneRel):
  def __init__(self, field, to, fieldName, relatedName=None, limitChoicesTo=None,
         parentLink=False, onDelete=None, relatedQueryName=None):
    super(OneToOneRel, self).__init__(field, to, fieldName,
        relatedName=relatedName, limitChoicesTo=limitChoicesTo,
        parentLink=parentLink, onDelete=onDelete, relatedQueryName=relatedQueryName)
    self.multiple = False


class ManyToManyRel(object):
  def __init__(self, to, relatedName=None, limitChoicesTo=None,
         symmetrical=True, through=None, throughFields=None,
         dbConstraint=True, relatedQueryName=None):
    if through and not dbConstraint:
      raise ValueError("Can't supply a through modal and dbConstraint=False")
    if throughFields and not through:
      raise ValueError("Cannot specify throughFields without a through modal")
    self.to = to
    self.relatedName = relatedName
    self.relatedQueryName = relatedQueryName
    if limitChoicesTo is None:
      limitChoicesTo = {}
    self.limitChoicesTo = limitChoicesTo
    self.symmetrical = symmetrical
    self.multiple = True
    self.through = through
    self.throughFields = throughFields
    self.dbConstraint = dbConstraint

  def isHidden(self):
    "Should the related object be hidden?"
    return self.relatedName and self.relatedName[-1] == '+'

  def getRelatedField(self):
    """
    Returns the field in the to' object to which this relationship is tied
    (this is always the primary key on the target modal). Provided for
    symmetry with ManyToOneRel.
    """
    return self.to._meta.pk


class ForeignObject(RelatedField):
  requiresUniqueTarget = True
  generateReverseRelation = True
  relatedAccessorClass = ForeignRelatedObjectsDescriptor

  def __init__(self, to, fromFields, toFields, swappable=True, **kwargs):
    self.fromFields = fromFields
    self.toFields = toFields
    self.swappable = swappable

    if 'rel' not in kwargs:
      kwargs['rel'] = ForeignObjectRel(
        self, to,
        relatedName=kwargs.pop('relatedName', None),
        relatedQueryName=kwargs.pop('relatedQueryName', None),
        limitChoicesTo=kwargs.pop('limitChoicesTo', None),
        parentLink=kwargs.pop('parentLink', False),
        onDelete=kwargs.pop('onDelete', CASCADE),
      )
    kwargs['verboseName'] = kwargs.get('verboseName', None)

    super(ForeignObject, self).__init__(**kwargs)

  def check(self, **kwargs):
    errors = super(ForeignObject, self).check(**kwargs)
    errors.extend(self._checkUniqueTarget())
    return errors

  def _checkUniqueTarget(self):
    relIsString = isinstance(self.rel.to, six.stringTypes)
    if relIsString or not self.requiresUniqueTarget:
      return []

    # Skip if the
    try:
      self.foreignRelatedFields
    except FieldDoesNotExist:
      return []

    try:
      self.related
    except AttributeError:
      return []

    hasUniqueField = any(relField.unique
      for relField in self.foreignRelatedFields)
    if not hasUniqueField and len(self.foreignRelatedFields) > 1:
      fieldCombination = ', '.join("'%s'" % relField.name
        for relField in self.foreignRelatedFields)
      modelName = self.rel.to.__name__
      return [
        checks.Error(
          "None of the fields %s on modal '%s' have a unique=True constraint." % (fieldCombination, modelName),
          hint=None,
          obj=self,
          id='fields.E310',
        )
      ]
    elif not hasUniqueField:
      fieldName = self.foreignRelatedFields[0].name
      modelName = self.rel.to.__name__
      return [
        checks.Error(
          ("'%s.%s' must set unique=True "
           "because it is referenced by a foreign key.") % (modelName, fieldName),
          hint=None,
          obj=self,
          id='fields.E311',
        )
      ]
    else:
      return []

  def deconstruct(self):
    name, path, args, kwargs = super(ForeignObject, self).deconstruct()
    kwargs['fromFields'] = self.fromFields
    kwargs['toFields'] = self.toFields
    if self.rel.relatedName is not None:
      kwargs['relatedName'] = self.rel.relatedName
    if self.rel.relatedQueryName is not None:
      kwargs['relatedQueryName'] = self.rel.relatedQueryName
    if self.rel.onDelete != CASCADE:
      kwargs['onDelete'] = self.rel.onDelete
    if self.rel.parentLink:
      kwargs['parentLink'] = self.rel.parentLink
    # Work out string form of "to"
    if isinstance(self.rel.to, six.stringTypes):
      kwargs['to'] = self.rel.to
    else:
      kwargs['to'] = "%s.%s" % (self.rel.to._meta.appLabel, self.rel.to._meta.objectName)
    # If swappable is True, then see if we're actually pointing to the target
    # of a swap.
    swappableSetting = self.swappableSetting
    if swappableSetting is not None:
      # If it's already a settings reference, error
      if hasattr(kwargs['to'], "settingName"):
        if kwargs['to'].settingName != swappableSetting:
          raise ValueError("Cannot deconstruct a ForeignKey pointing to a modal that is swapped in place of more than one modal (%s and %s)" % (kwargs['to'].settingName, swappableSetting))
      # Set it
      from theory.db.migrations.writer import SettingsReference
      kwargs['to'] = SettingsReference(
        kwargs['to'],
        swappableSetting,
      )
    return name, path, args, kwargs

  def resolveRelatedFields(self):
    if len(self.fromFields) < 1 or len(self.fromFields) != len(self.toFields):
      raise ValueError('Foreign Object from and to fields must be the same non-zero length')
    if isinstance(self.rel.to, six.stringTypes):
      raise ValueError('Related modal %r cannot be resolved' % self.rel.to)
    relatedFields = []
    for index in range(len(self.fromFields)):
      fromFieldName = self.fromFields[index]
      toFieldName = self.toFields[index]
      fromField = (self if fromFieldName == 'self'
             else self.opts.getFieldByName(fromFieldName)[0])
      toField = (self.rel.to._meta.pk if toFieldName is None
            else self.rel.to._meta.getFieldByName(toFieldName)[0])
      relatedFields.append((fromField, toField))
    return relatedFields

  @property
  def relatedFields(self):
    if not hasattr(self, '_relatedFields'):
      self._relatedFields = self.resolveRelatedFields()
    return self._relatedFields

  @property
  def reverseRelatedFields(self):
    return [(rhsField, lhsField) for lhsField, rhsField in self.relatedFields]

  @property
  def localRelatedFields(self):
    return tuple(lhsField for lhsField, rhsField in self.relatedFields)

  @property
  def foreignRelatedFields(self):
    return tuple(rhsField for lhsField, rhsField in self.relatedFields)

  def getLocalRelatedValue(self, instance):
    return self.getInstanceValueForFields(instance, self.localRelatedFields)

  def getForeignRelatedValue(self, instance):
    return self.getInstanceValueForFields(instance, self.foreignRelatedFields)

  @staticmethod
  def getInstanceValueForFields(instance, fields):
    ret = []
    opts = instance._meta
    for field in fields:
      # Gotcha: in some cases (like fixture loading) a modal can have
      # different values in parentPtrId and parent's id. So, use
      # instance.pk (that is, parentPtrId) when asked for instance.id.
      if field.primaryKey:
        possibleParentLink = opts.getAncestorLink(field.modal)
        if (not possibleParentLink or
            possibleParentLink.primaryKey or
            possibleParentLink.modal._meta.abstract):
          ret.append(instance.pk)
          continue
      ret.append(getattr(instance, field.attname))
    return tuple(ret)

  def getAttnameColumn(self):
    attname, column = super(ForeignObject, self).getAttnameColumn()
    return attname, None

  def getJoiningColumns(self, reverseJoin=False):
    source = self.reverseRelatedFields if reverseJoin else self.relatedFields
    return tuple((lhsField.column, rhsField.column) for lhsField, rhsField in source)

  def getReverseJoiningColumns(self):
    return self.getJoiningColumns(reverseJoin=True)

  def getExtraDescriptorFilter(self, instance):
    """
    Returns an extra filter condition for related object fetching when
    user does 'instance.fieldname', that is the extra filter is used in
    the descriptor of the field.

    The filter should be either a dict usable in .filter(**kwargs) call or
    a Q-object. The condition will be ANDed together with the relation's
    joining columns.

    A parallel method is getExtraRestriction() which is used in
    JOIN and subquery conditions.
    """
    return {}

  def getExtraRestriction(self, whereClass, alias, relatedAlias):
    """
    Returns a pair condition used for joining and subquery pushdown. The
    condition is something that responds to asSql(qn, connection) method.

    Note that currently referring both the 'alias' and 'relatedAlias'
    will not work in some conditions, like subquery pushdown.

    A parallel method is getExtraDescriptorFilter() which is used in
    instance.fieldname related object fetching.
    """
    return None

  def getPathInfo(self):
    """
    Get path from this field to the related modal.
    """
    opts = self.rel.to._meta
    fromOpts = self.modal._meta
    return [PathInfo(fromOpts, opts, self.foreignRelatedFields, self, False, True)]

  def getReversePathInfo(self):
    """
    Get path from the related modal to this field's modal.
    """
    opts = self.modal._meta
    fromOpts = self.rel.to._meta
    pathinfos = [PathInfo(fromOpts, opts, (opts.pk,), self.rel, not self.unique, False)]
    return pathinfos

  def getLookupConstraint(self, constraintClass, alias, targets, sources, lookups,
               rawValue):
    from theory.db.model.sql.where import SubqueryConstraint, AND, OR
    rootConstraint = constraintClass()
    assert len(targets) == len(sources)
    if len(lookups) > 1:
      raise exceptions.FieldError('Relation fields do not support nested lookups')
    lookupType = lookups[0]

    def getNormalizedValue(value):
      from theory.db.model import Model
      if isinstance(value, Model):
        valueList = []
        for source in sources:
          # Account for one-to-one relations when sent a different modal
          while not isinstance(value, source.modal) and source.rel:
            source = source.rel.to._meta.getField(source.rel.fieldName)
          valueList.append(getattr(value, source.attname))
        return tuple(valueList)
      elif not isinstance(value, tuple):
        return (value,)
      return value

    isMulticolumn = len(self.relatedFields) > 1
    if (hasattr(rawValue, '_asSql') or
        hasattr(rawValue, 'getCompiler')):
      rootConstraint.add(SubqueryConstraint(alias, [target.column for target in targets],
                          [source.name for source in sources], rawValue),
                AND)
    elif lookupType == 'isnull':
      rootConstraint.add(IsNull(Col(alias, targets[0], sources[0]), rawValue), AND)
    elif (lookupType == 'exact' or (lookupType in ['gt', 'lt', 'gte', 'lte']
                     and not isMulticolumn)):
      value = getNormalizedValue(rawValue)
      for target, source, val in zip(targets, sources, value):
        lookupClass = target.getLookup(lookupType)
        rootConstraint.add(
          lookupClass(Col(alias, target, source), val), AND)
    elif lookupType in ['range', 'in'] and not isMulticolumn:
      values = [getNormalizedValue(value) for value in rawValue]
      value = [val[0] for val in values]
      lookupClass = targets[0].getLookup(lookupType)
      rootConstraint.add(lookupClass(Col(alias, targets[0], sources[0]), value), AND)
    elif lookupType == 'in':
      values = [getNormalizedValue(value) for value in rawValue]
      for value in values:
        valueConstraint = constraintClass()
        for source, target, val in zip(sources, targets, value):
          lookupClass = target.getLookup('exact')
          lookup = lookupClass(Col(alias, target, source), val)
          valueConstraint.add(lookup, AND)
        rootConstraint.add(valueConstraint, OR)
    else:
      raise TypeError('Related Field got invalid lookup: %s' % lookupType)
    return rootConstraint

  @property
  def attnames(self):
    return tuple(field.attname for field in self.localRelatedFields)

  def getDefaults(self):
    return tuple(field.getDefault() for field in self.localRelatedFields)

  def contributeToClass(self, cls, name, virtualOnly=False):
    super(ForeignObject, self).contributeToClass(cls, name, virtualOnly=virtualOnly)
    setattr(cls, self.name, ReverseSingleRelatedObjectDescriptor(self))

  def contributeToRelatedClass(self, cls, related):
    # Internal FK's - i.e., those with a related name ending with '+' -
    # and swapped model don't get a related descriptor.
    if not self.rel.isHidden() and not related.modal._meta.swapped:
      setattr(cls, related.getAccessorName(), self.relatedAccessorClass(related))
      # While 'limitChoicesTo' might be a callable, simply pass
      # it along for later - this is too early because it's still
      # modal load time.
      if self.rel.limitChoicesTo:
        cls._meta.relatedFkeyLookups.append(self.rel.limitChoicesTo)


class ForeignKey(ForeignObject):
  emptyStringsAllowed = False
  defaultErrorMessages = {
    'invalid': _('%(modal)s instance with pk %(pk)r does not exist.')
  }
  description = _("Foreign Key (type determined by related field)")

  def __init__(self, to, toField=None, relClass=ManyToOneRel,
         dbConstraint=True, **kwargs):
    try:
      to._meta.modelName
    except AttributeError:  # to._meta doesn't exist, so it must be RECURSIVE_RELATIONSHIP_CONSTANT
      assert isinstance(to, six.stringTypes), "%s(%r) is invalid. First parameter to ForeignKey must be either a modal, a modal name, or the string %r" % (self.__class__.__name__, to, RECURSIVE_RELATIONSHIP_CONSTANT)
    else:
      # For backwards compatibility purposes, we need to *try* and set
      # the toField during FK construction. It won't be guaranteed to
      # be correct until contributeToClass is called. Refs #12190.
      toField = toField or (to._meta.pk and to._meta.pk.name)

    if 'dbIndex' not in kwargs:
      kwargs['dbIndex'] = True

    self.dbConstraint = dbConstraint

    kwargs['rel'] = relClass(
      self, to, toField,
      relatedName=kwargs.pop('relatedName', None),
      relatedQueryName=kwargs.pop('relatedQueryName', None),
      limitChoicesTo=kwargs.pop('limitChoicesTo', None),
      parentLink=kwargs.pop('parentLink', False),
      onDelete=kwargs.pop('onDelete', CASCADE),
    )
    super(ForeignKey, self).__init__(to, ['self'], [toField], **kwargs)

  def check(self, **kwargs):
    errors = super(ForeignKey, self).check(**kwargs)
    errors.extend(self._checkOnDelete())
    return errors

  def _checkOnDelete(self):
    onDelete = getattr(self.rel, 'onDelete', None)
    if onDelete == SET_NULL and not self.null:
      return [
        checks.Error(
          'Field specifies onDelete=SET_NULL, but cannot be null.',
          hint='Set null=True argument on the field, or change the onDelete rule.',
          obj=self,
          id='fields.E320',
        )
      ]
    elif onDelete == SET_DEFAULT and not self.hasDefault():
      return [
        checks.Error(
          'Field specifies onDelete=SET_DEFAULT, but has no default value.',
          hint='Set a default value, or change the onDelete rule.',
          obj=self,
          id='fields.E321',
        )
      ]
    else:
      return []

  def deconstruct(self):
    name, path, args, kwargs = super(ForeignKey, self).deconstruct()
    del kwargs['toFields']
    del kwargs['fromFields']
    # Handle the simpler arguments
    if self.dbIndex:
      del kwargs['dbIndex']
    else:
      kwargs['dbIndex'] = False
    if self.dbConstraint is not True:
      kwargs['dbConstraint'] = self.dbConstraint
    # Rel needs more work.
    toMeta = getattr(self.rel.to, "_meta", None)
    if self.rel.fieldName and (not toMeta or (toMeta.pk and self.rel.fieldName != toMeta.pk.name)):
      kwargs['toField'] = self.rel.fieldName
    return name, path, args, kwargs

  @property
  def relatedField(self):
    return self.foreignRelatedFields[0]

  def getReversePathInfo(self):
    """
    Get path from the related modal to this field's modal.
    """
    opts = self.modal._meta
    fromOpts = self.rel.to._meta
    pathinfos = [PathInfo(fromOpts, opts, (opts.pk,), self.rel, not self.unique, False)]
    return pathinfos

  def validate(self, value, modalInstance):
    if self.rel.parentLink:
      return
    super(ForeignKey, self).validate(value, modalInstance)
    if value is None:
      return

    using = router.dbForRead(modalInstance.__class__, instance=modalInstance)
    qs = self.rel.to._defaultManager.using(using).filter(
      **{self.rel.fieldName: value}
    )
    qs = qs.complexFilter(self.getLimitChoicesTo())
    if not qs.exists():
      raise exceptions.ValidationError(
        self.errorMessages['invalid'],
        code='invalid',
        params={'modal': self.rel.to._meta.verboseName, 'pk': value},
      )

  def getAttname(self):
    return '%sId' % self.name

  def getAttnameColumn(self):
    attname = self.getAttname()
    column = self.dbColumn or attname
    return attname, column

  def getValidatorUniqueLookupType(self):
    return '%s__%s__exact' % (self.name, self.relatedField.name)

  def getDefault(self):
    "Here we check if the default value is an object and return the toField if so."
    fieldDefault = super(ForeignKey, self).getDefault()
    if isinstance(fieldDefault, self.rel.to):
      return getattr(fieldDefault, self.relatedField.attname)
    return fieldDefault

  def getDbPrepSave(self, value, connection):
    if value is None or (value == '' and
               (not self.relatedField.emptyStringsAllowed or
               connection.features.interpretsEmptyStringsAsNulls)):
      return None
    else:
      return self.relatedField.getDbPrepSave(value, connection=connection)

  def valueToString(self, obj):
    if not obj:
      # In required many-to-one fields with only one available choice,
      # select that one available choice. Note: For SelectFields
      # we have to check that the length of choices is *2*, not 1,
      # because SelectFields always have an initial "blank" value.
      if not self.blank and self.choices:
        choiceList = self.getChoicesDefault()
        if len(choiceList) == 2:
          return smartText(choiceList[1][0])
    return super(ForeignKey, self).valueToString(obj)

  def contributeToRelatedClass(self, cls, related):
    super(ForeignKey, self).contributeToRelatedClass(cls, related)
    if self.rel.fieldName is None:
      self.rel.fieldName = cls._meta.pk.name

  def formfield(self, **kwargs):
    db = kwargs.pop('using', None)
    if isinstance(self.rel.to, six.stringTypes):
      raise ValueError("Cannot create form field for %r yet, because "
               "its related modal %r has not been loaded yet" %
               (self.name, self.rel.to))
    defaults = {
      'formClass': ModelChoiceField,
      'queryset': self.rel.to._defaultManager.using(db),
      'toFieldName': self.rel.fieldName,
    }
    defaults.update(kwargs)
    return super(ForeignKey, self).formfield(**defaults)

  def dbType(self, connection):
    # The database column type of a ForeignKey is the column type
    # of the field to which it points. An exception is if the ForeignKey
    # points to an AutoField/PositiveIntegerField/PositiveSmallIntegerField,
    # in which case the column type is simply that of an IntegerField.
    # If the database needs similar types for key fields however, the only
    # thing we can do is making AutoField an IntegerField.
    relField = self.relatedField
    if (isinstance(relField, AutoField) or
        (not connection.features.relatedFieldsMatchType and
        isinstance(relField, (PositiveIntegerField,
                    PositiveSmallIntegerField)))):
      return IntegerField().dbType(connection=connection)
    return relField.dbType(connection=connection)

  def dbParameters(self, connection):
    return {"type": self.dbType(connection), "check": []}


class OneToOneField(ForeignKey):
  """
  A OneToOneField is essentially the same as a ForeignKey, with the exception
  that always carries a "unique" constraint with it and the reverse relation
  always returns the object pointed to (since there will only ever be one),
  rather than returning a list.
  """
  relatedAccessorClass = SingleRelatedObjectDescriptor
  description = _("One-to-one relationship")

  def __init__(self, to, toField=None, **kwargs):
    kwargs['unique'] = True
    super(OneToOneField, self).__init__(to, toField, OneToOneRel, **kwargs)

  def deconstruct(self):
    name, path, args, kwargs = super(OneToOneField, self).deconstruct()
    if "unique" in kwargs:
      del kwargs['unique']
    return name, path, args, kwargs

  def formfield(self, **kwargs):
    if self.rel.parentLink:
      return None
    return super(OneToOneField, self).formfield(**kwargs)

  def saveFormData(self, instance, data):
    if isinstance(data, self.rel.to):
      setattr(instance, self.name, data)
    else:
      setattr(instance, self.attname, data)


def createManyToManyIntermediaryModel(field, klass):
  from theory.db import model
  managed = True
  if isinstance(field.rel.to, six.stringTypes) and field.rel.to != RECURSIVE_RELATIONSHIP_CONSTANT:
    toModel = field.rel.to
    to = toModel.split('.')[-1]

    def setManaged(field, modal, cls):
      field.rel.through._meta.managed = modal._meta.managed or cls._meta.managed
    addLazyRelation(klass, field, toModel, setManaged)
  elif isinstance(field.rel.to, six.stringTypes):
    to = klass._meta.objectName
    toModel = klass
    managed = klass._meta.managed
  else:
    to = field.rel.to._meta.objectName
    toModel = field.rel.to
    managed = klass._meta.managed or toModel._meta.managed
  name = '%s_%s' % (klass._meta.objectName, field.name)
  if field.rel.to == RECURSIVE_RELATIONSHIP_CONSTANT or to == klass._meta.objectName:
    from_ = 'from_%s' % to.lower()
    to = 'to_%s' % to.lower()
  else:
    from_ = klass._meta.modelName
    to = to.lower()
  meta = type(str('Meta'), (object,), {
    'dbTable': field._getM2mDbTable(klass._meta),
    'managed': managed,
    'autoCreated': klass,
    'appLabel': klass._meta.appLabel,
    'dbTablespace': klass._meta.dbTablespace,
    'uniqueTogether': (from_, to),
    'verboseName': '%(from)s-%(to)s relationship' % {'from': from_, 'to': to},
    'verboseNamePlural': '%(from)s-%(to)s relationships' % {'from': from_, 'to': to},
    'apps': field.modal._meta.apps,
  })
  # Construct and return the new class.
  return type(str(name), (model.Model,), {
    'Meta': meta,
    '__module__': klass.__module__,
    from_: model.ForeignKey(klass, relatedName='%s+' % name, dbTablespace=field.dbTablespace, dbConstraint=field.rel.dbConstraint),
    to: model.ForeignKey(toModel, relatedName='%s+' % name, dbTablespace=field.dbTablespace, dbConstraint=field.rel.dbConstraint)
  })


class ManyToManyField(RelatedField):
  description = _("Many-to-many relationship")

  def __init__(self, to, dbConstraint=True, swappable=True, **kwargs):
    try:
      to._meta
    except AttributeError:  # to._meta doesn't exist, so it must be RECURSIVE_RELATIONSHIP_CONSTANT
      assert isinstance(to, six.stringTypes), "%s(%r) is invalid. First parameter to ManyToManyField must be either a modal, a modal name, or the string %r" % (self.__class__.__name__, to, RECURSIVE_RELATIONSHIP_CONSTANT)
      # Class names must be ASCII in Python 2.x, so we forcibly coerce it here to break early if there's a problem.
      to = str(to)

    kwargs['verboseName'] = kwargs.get('verboseName', None)
    kwargs['rel'] = ManyToManyRel(to,
      relatedName=kwargs.pop('relatedName', None),
      relatedQueryName=kwargs.pop('relatedQueryName', None),
      limitChoicesTo=kwargs.pop('limitChoicesTo', None),
      symmetrical=kwargs.pop('symmetrical', to == RECURSIVE_RELATIONSHIP_CONSTANT),
      through=kwargs.pop('through', None),
      throughFields=kwargs.pop('throughFields', None),
      dbConstraint=dbConstraint,
    )

    self.swappable = swappable
    self.dbTable = kwargs.pop('dbTable', None)
    if kwargs['rel'].through is not None:
      assert self.dbTable is None, "Cannot specify a dbTable if an intermediary modal is used."

    super(ManyToManyField, self).__init__(**kwargs)

  def check(self, **kwargs):
    errors = super(ManyToManyField, self).check(**kwargs)
    errors.extend(self._checkUnique(**kwargs))
    errors.extend(self._checkRelationshipModel(**kwargs))
    return errors

  def _checkUnique(self, **kwargs):
    if self.unique:
      return [
        checks.Error(
          'ManyToManyFields cannot be unique.',
          hint=None,
          obj=self,
          id='fields.E330',
        )
      ]
    return []

  def _checkRelationshipModel(self, fromModel=None, **kwargs):
    if hasattr(self.rel.through, '_meta'):
      qualifiedModelName = "%s.%s" % (
        self.rel.through._meta.appLabel, self.rel.through.__name__)
    else:
      qualifiedModelName = self.rel.through

    errors = []

    if self.rel.through not in apps.getModels(includeAutoCreated=True):
      # The relationship modal is not installed.
      errors.append(
        checks.Error(
          ("Field specifies a many-to-many relation through modal "
           "'%s', which has not been installed.") %
          qualifiedModelName,
          hint=None,
          obj=self,
          id='fields.E331',
        )
      )

    else:

      assert fromModel is not None, \
        "ManyToManyField with intermediate " \
        "tables cannot be checked if you don't pass the modal " \
        "where the field is attached to."

      # Set some useful local variables
      toModel = self.rel.to
      fromModelName = fromModel._meta.objectName
      if isinstance(toModel, six.stringTypes):
        toModelName = toModel
      else:
        toModelName = toModel._meta.objectName
      relationshipModelName = self.rel.through._meta.objectName
      selfReferential = fromModel == toModel

      # Check symmetrical attribute.
      if (selfReferential and self.rel.symmetrical and
          not self.rel.through._meta.autoCreated):
        errors.append(
          checks.Error(
            'Many-to-many fields with intermediate tables must not be symmetrical.',
            hint=None,
            obj=self,
            id='fields.E332',
          )
        )

      # Count foreign keys in intermediate modal
      if selfReferential:
        seenSelf = sum(fromModel == getattr(field.rel, 'to', None)
          for field in self.rel.through._meta.fields)

        if seenSelf > 2 and not self.rel.throughFields:
          errors.append(
            checks.Error(
              ("The modal is used as an intermediate modal by "
               "'%s', but it has more than two foreign keys "
               "to '%s', which is ambiguous. You must specify "
               "which two foreign keys Theory should use via the "
               "throughFields keyword argument.") % (self, fromModelName),
              hint=("Use throughFields to specify which two "
                 "foreign keys Theory should use."),
              obj=self.rel.through,
              id='fields.E333',
            )
          )

      else:
        # Count foreign keys in relationship modal
        seenFrom = sum(fromModel == getattr(field.rel, 'to', None)
          for field in self.rel.through._meta.fields)
        seenTo = sum(toModel == getattr(field.rel, 'to', None)
          for field in self.rel.through._meta.fields)

        if seenFrom > 1 and not self.rel.throughFields:
          errors.append(
            checks.Error(
              ("The modal is used as an intermediate modal by "
               "'%s', but it has more than one foreign key "
               "from '%s', which is ambiguous. You must specify "
               "which foreign key Theory should use via the "
               "throughFields keyword argument.") % (self, fromModelName),
              hint=('If you want to create a recursive relationship, '
                 'use ForeignKey("self", symmetrical=False, '
                 'through="%s").') % relationshipModelName,
              obj=self,
              id='fields.E334',
            )
          )

        if seenTo > 1 and not self.rel.throughFields:
          errors.append(
            checks.Error(
              ("The modal is used as an intermediate modal by "
               "'%s', but it has more than one foreign key "
               "to '%s', which is ambiguous. You must specify "
               "which foreign key Theory should use via the "
               "throughFields keyword argument.") % (self, toModelName),
              hint=('If you want to create a recursive '
                 'relationship, use ForeignKey("self", '
                 'symmetrical=False, through="%s").') % relationshipModelName,
              obj=self,
              id='fields.E335',
            )
          )

        if seenFrom == 0 or seenTo == 0:
          errors.append(
            checks.Error(
              ("The modal is used as an intermediate modal by "
               "'%s', but it does not have a foreign key to '%s' or '%s'.") % (
                self, fromModelName, toModelName
              ),
              hint=None,
              obj=self.rel.through,
              id='fields.E336',
            )
          )

    # Validate `throughFields`
    if self.rel.throughFields is not None:
      # Validate that we're given an iterable of at least two items
      # and that none of them is "falsy"
      if not (len(self.rel.throughFields) >= 2 and
          self.rel.throughFields[0] and self.rel.throughFields[1]):
        errors.append(
          checks.Error(
            ("Field specifies 'throughFields' but does not "
             "provide the names of the two link fields that should be "
             "used for the relation through modal "
             "'%s'.") % qualifiedModelName,
            hint=("Make sure you specify 'throughFields' as "
               "throughFields=('field1', 'field2')"),
            obj=self,
            id='fields.E337',
          )
        )

      # Validate the given through fields -- they should be actual
      # fields on the through modal, and also be foreign keys to the
      # expected model
      else:
        assert fromModel is not None, \
          "ManyToManyField with intermediate " \
          "tables cannot be checked if you don't pass the modal " \
          "where the field is attached to."

        source, through, target = fromModel, self.rel.through, self.rel.to
        sourceFieldName, targetFieldName = self.rel.throughFields[:2]

        for fieldName, relatedModel in ((sourceFieldName, source),
                         (targetFieldName, target)):

          possibleFieldNames = []
          for f in through._meta.fields:
            if hasattr(f, 'rel') and getattr(f.rel, 'to', None) == relatedModel:
              possibleFieldNames.append(f.name)
          if possibleFieldNames:
            hint = ("Did you mean one of the following foreign "
                "keys to '%s': %s?") % (relatedModel._meta.objectName,
                            ', '.join(possibleFieldNames))
          else:
            hint = None

          try:
            field = through._meta.getField(fieldName)
          except FieldDoesNotExist:
            errors.append(
              checks.Error(
                ("The intermediary modal '%s' has no field '%s'.") % (
                  qualifiedModelName, fieldName),
                hint=hint,
                obj=self,
                id='fields.E338',
              )
            )
          else:
            if not (hasattr(field, 'rel') and
                getattr(field.rel, 'to', None) == relatedModel):
              errors.append(
                checks.Error(
                  "'%s.%s' is not a foreign key to '%s'." % (
                    through._meta.objectName, fieldName,
                    relatedModel._meta.objectName),
                  hint=hint,
                  obj=self,
                  id='fields.E339',
                )
              )

    return errors

  def deconstruct(self):
    name, path, args, kwargs = super(ManyToManyField, self).deconstruct()
    # Handle the simpler arguments
    if self.dbTable is not None:
      kwargs['dbTable'] = self.dbTable
    if self.rel.dbConstraint is not True:
      kwargs['dbConstraint'] = self.rel.dbConstraint
    if self.rel.relatedName is not None:
      kwargs['relatedName'] = self.rel.relatedName
    if self.rel.relatedQueryName is not None:
      kwargs['relatedQueryName'] = self.rel.relatedQueryName
    # Rel needs more work.
    if isinstance(self.rel.to, six.stringTypes):
      kwargs['to'] = self.rel.to
    else:
      kwargs['to'] = "%s.%s" % (self.rel.to._meta.appLabel, self.rel.to._meta.objectName)
    if getattr(self.rel, 'through', None) is not None:
      if isinstance(self.rel.through, six.stringTypes):
        kwargs['through'] = self.rel.through
      elif not self.rel.through._meta.autoCreated:
        kwargs['through'] = "%s.%s" % (self.rel.through._meta.appLabel, self.rel.through._meta.objectName)
    # If swappable is True, then see if we're actually pointing to the target
    # of a swap.
    swappableSetting = self.swappableSetting
    if swappableSetting is not None:
      # If it's already a settings reference, error
      if hasattr(kwargs['to'], "settingName"):
        if kwargs['to'].settingName != swappableSetting:
          raise ValueError("Cannot deconstruct a ManyToManyField pointing to a modal that is swapped in place of more than one modal (%s and %s)" % (kwargs['to'].settingName, swappableSetting))
      # Set it
      from theory.db.migrations.writer import SettingsReference
      kwargs['to'] = SettingsReference(
        kwargs['to'],
        swappableSetting,
      )
    return name, path, args, kwargs

  def _getPathInfo(self, direct=False):
    """
    Called by both direct and indirect m2m traversal.
    """
    pathinfos = []
    intModel = self.rel.through
    linkfield1 = intModel._meta.getFieldByName(self.m2mFieldName())[0]
    linkfield2 = intModel._meta.getFieldByName(self.m2mReverseFieldName())[0]
    if direct:
      join1infos = linkfield1.getReversePathInfo()
      join2infos = linkfield2.getPathInfo()
    else:
      join1infos = linkfield2.getReversePathInfo()
      join2infos = linkfield1.getPathInfo()
    pathinfos.extend(join1infos)
    pathinfos.extend(join2infos)
    return pathinfos

  def getPathInfo(self):
    return self._getPathInfo(direct=True)

  def getReversePathInfo(self):
    return self._getPathInfo(direct=False)

  def getChoicesDefault(self):
    return Field.getChoices(self, includeBlank=False)

  def _getM2mDbTable(self, opts):
    "Function that can be curried to provide the m2m table name for this relation"
    if self.rel.through is not None:
      return self.rel.through._meta.dbTable
    elif self.dbTable:
      return self.dbTable
    else:
      return utils.truncateName('%s_%s' % (opts.dbTable, self.name),
                   connection.ops.maxNameLength())

  def _getM2mAttr(self, related, attr):
    "Function that can be curried to provide the source accessor or DB column name for the m2m table"
    cacheAttr = '_m2m_%sCache' % attr
    if hasattr(self, cacheAttr):
      return getattr(self, cacheAttr)
    if self.rel.throughFields is not None:
      linkFieldName = self.rel.throughFields[0]
    else:
      linkFieldName = None
    for f in self.rel.through._meta.fields:
      if hasattr(f, 'rel') and f.rel and f.rel.to == related.modal and \
          (linkFieldName is None or linkFieldName == f.name):
        setattr(self, cacheAttr, getattr(f, attr))
        return getattr(self, cacheAttr)

  def _getM2mReverseAttr(self, related, attr):
    "Function that can be curried to provide the related accessor or DB column name for the m2m table"
    cacheAttr = '_m2mReverse_%sCache' % attr
    if hasattr(self, cacheAttr):
      return getattr(self, cacheAttr)
    found = False
    if self.rel.throughFields is not None:
      linkFieldName = self.rel.throughFields[1]
    else:
      linkFieldName = None
    for f in self.rel.through._meta.fields:
      if hasattr(f, 'rel') and f.rel and f.rel.to == related.parentModel:
        if linkFieldName is None and related.modal == related.parentModel:
          # If this is an m2m-intermediate to self,
          # the first foreign key you find will be
          # the source column. Keep searching for
          # the second foreign key.
          if found:
            setattr(self, cacheAttr, getattr(f, attr))
            break
          else:
            found = True
        elif linkFieldName is None or linkFieldName == f.name:
          setattr(self, cacheAttr, getattr(f, attr))
          break
    return getattr(self, cacheAttr)

  def valueToString(self, obj):
    data = ''
    if obj:
      qs = getattr(obj, self.name).all()
      data = [instance._getPkVal() for instance in qs]
    else:
      # In required many-to-many fields with only one available choice,
      # select that one available choice.
      if not self.blank:
        choicesList = self.getChoicesDefault()
        if len(choicesList) == 1:
          data = [choicesList[0][0]]
    return smartText(data)

  def contributeToClass(self, cls, name):
    # To support multiple relations to self, it's useful to have a non-None
    # related name on symmetrical relations for internal reasons. The
    # concept doesn't make a lot of sense externally ("you want me to
    # specify *what* on my non-reversible relation?!"), so we set it up
    # automatically. The funky name reduces the chance of an accidental
    # clash.
    if self.rel.symmetrical and (self.rel.to == "self" or self.rel.to == cls._meta.objectName):
      self.rel.relatedName = "%sRel_+" % name

    super(ManyToManyField, self).contributeToClass(cls, name)

    # The intermediate m2m modal is not auto created if:
    #  1) There is a manually specified intermediate, or
    #  2) The class owning the m2m field is abstract.
    #  3) The class owning the m2m field has been swapped out.
    if not self.rel.through and not cls._meta.abstract and not cls._meta.swapped:
      self.rel.through = createManyToManyIntermediaryModel(self, cls)

    # Add the descriptor for the m2m relation
    setattr(cls, self.name, ReverseManyRelatedObjectsDescriptor(self))

    # Set up the accessor for the m2m table name for the relation
    self.m2mDbTable = curry(self._getM2mDbTable, cls._meta)

    # Populate some necessary rel arguments so that cross-app relations
    # work correctly.
    if isinstance(self.rel.through, six.stringTypes):
      def resolveThroughModel(field, modal, cls):
        field.rel.through = modal
      addLazyRelation(cls, self, self.rel.through, resolveThroughModel)

  def contributeToRelatedClass(self, cls, related):
    # Internal M2Ms (i.e., those with a related name ending with '+')
    # and swapped model don't get a related descriptor.
    if not self.rel.isHidden() and not related.modal._meta.swapped:
      setattr(cls, related.getAccessorName(), ManyRelatedObjectsDescriptor(related))

    # Set up the accessors for the column names on the m2m table
    self.m2mColumnName = curry(self._getM2mAttr, related, 'column')
    self.m2mReverseName = curry(self._getM2mReverseAttr, related, 'column')

    self.m2mFieldName = curry(self._getM2mAttr, related, 'name')
    self.m2mReverseFieldName = curry(self._getM2mReverseAttr, related, 'name')

    getM2mRel = curry(self._getM2mAttr, related, 'rel')
    self.m2mTargetFieldName = lambda: getM2mRel().fieldName
    getM2mReverseRel = curry(self._getM2mReverseAttr, related, 'rel')
    self.m2mReverseTargetFieldName = lambda: getM2mReverseRel().fieldName

  def setAttributesFromRel(self):
    pass

  def valueFromObject(self, obj):
    "Returns the value of this field in the given modal instance."
    return getattr(obj, self.attname).all()

  def saveFormData(self, instance, data):
    setattr(instance, self.attname, data)

  def formfield(self, **kwargs):
    db = kwargs.pop('using', None)
    defaults = {
      'formClass': ModelMultipleChoiceField,
      'queryset': self.rel.to._defaultManager.using(db),
    }
    defaults.update(kwargs)
    # If initData is passed in, it's a list of related objects, but the
    # MultipleChoiceField takes a list of IDs.
    if defaults.get('initData') is not None:
      initData = defaults['initData']
      if callable(initData):
        initData = initData()
      defaults['initData'] = [i._getPkVal() for i in initData]
    return super(ManyToManyField, self).formfield(**defaults)

  def dbType(self, connection):
    # A ManyToManyField is not represented by a single column,
    # so return None.
    return None

  def dbParameters(self, connection):
    return {"type": None, "check": None}
