from __future__ import unicode_literals

import copy
import sys
from functools import update_wrapper
import warnings

from theory.apps import apps
from theory.apps.config import MODELS_MODULE_NAME
import theory.db.model.manager  # NOQA: Imported to register signal handler.
from theory.conf import settings
from theory.core import checks
from theory.core.exceptions import (ObjectDoesNotExist,
  MultipleObjectsReturned, FieldError, ValidationError, NON_FIELD_ERRORS)
from theory.db.model.fields import AutoField, FieldDoesNotExist
from theory.db.model.fields.related import (ForeignObjectRel, ManyToOneRel,
  OneToOneField, addLazyRelation)
from theory.db import (router, transaction, DatabaseError,
  DEFAULT_DB_ALIAS)
from theory.db.model.query import Q
from theory.db.model.queryUtils import DeferredAttribute, deferredClassFactory
from theory.db.model.deletion import Collector
from theory.db.model.options import Options
from theory.db.model import signals
from theory.utils import six
from theory.utils.deprecation import RemovedInTheory19Warning
from theory.utils.encoding import forceStr, forceText
from theory.utils.functional import curry
from theory.utils.six.moves import zip
from theory.utils.text import getTextList, capfirst
from theory.utils.translation import ugettextLazy as _


def subclassException(name, parents, module, attachedTo=None):
  """
  Create exception subclass. Used by ModelBase below.

  If 'attachedTo' is supplied, the exception will be created in a way that
  allows it to be pickled, assuming the returned exception class will be added
  as an attribute to the 'attachedTo' class.
  """
  classDict = {'__module__': module}
  if attachedTo is not None:
    def __reduce__(self):
      # Exceptions are special - they've got state that isn't
      # in self.__dict__. We assume it is all in self.args.
      return (unpickleInnerException, (attachedTo, name), self.args)

    def __setstate__(self, args):
      self.args = args

    classDict['__reduce__'] = __reduce__
    classDict['__setstate__'] = __setstate__

  return type(name, parents, classDict)


class ModelBase(type):
  """
  Metaclass for all model.
  """
  def __new__(cls, name, bases, attrs):
    superNew = super(ModelBase, cls).__new__

    # Also ensure initialization is only performed for subclasses of Model
    # (excluding Model class itself).
    parents = [b for b in bases if isinstance(b, ModelBase)]
    if not parents:
      return superNew(cls, name, bases, attrs)

    # Create the class.
    module = attrs.pop('__module__')
    newClass = superNew(cls, name, bases, {'__module__': module})
    attrMeta = attrs.pop('Meta', None)
    abstract = getattr(attrMeta, 'abstract', False)
    if not attrMeta:
      meta = getattr(newClass, 'Meta', None)
    else:
      meta = attrMeta
    baseMeta = getattr(newClass, '_meta', None)

    # Look for an application configuration to attach the modal to.
    appConfig = apps.getContainingAppConfig(module)

    if getattr(meta, 'appLabel', None) is None:

      if appConfig is None:
        # If the modal is imported before the configuration for its
        # application is created (#21719), or isn't in an installed
        # application (#21680), use the legacy logic to figure out the
        # appLabel by looking one level up from the package or module
        # named 'model'. If no such package or module exists, fall
        # back to looking one level up from the module this modal is
        # defined in.

        # For 'theory.contrib.sites.model', this would be 'sites'.
        # For 'geo.model.places' this would be 'geo'.

        msg = (
          "Model class %s.%s doesn't declare an explicit appLabel "
          "and either isn't in an application in INSTALLED_APPS or "
          "else was imported before its application was loaded. " %
          (module, name))
        if abstract:
          msg += "Its appLabel will be set to None in Theory 1.9."
        else:
          msg += "This will no longer be supported in Theory 1.9."
        warnings.warn(msg, RemovedInTheory19Warning, stacklevel=2)

        modalModule = sys.modules[newClass.__module__]
        packageComponents = modalModule.__name__.split('.')
        packageComponents.reverse()  # find the last occurrence of 'model'
        try:
          appLabelIndex = packageComponents.index(MODELS_MODULE_NAME) + 1
        except ValueError:
          appLabelIndex = 1
        kwargs = {"appLabel": packageComponents[appLabelIndex]}

      else:
        kwargs = {"appLabel": appConfig.label}

    else:
      kwargs = {}

    newClass.addToClass('_meta', Options(meta, **kwargs))
    if not abstract:
      newClass.addToClass(
        'DoesNotExist',
        subclassException(
          str('DoesNotExist'),
          tuple(x.DoesNotExist for x in parents if hasattr(x, '_meta') and not x._meta.abstract) or (ObjectDoesNotExist,),
          module,
          attachedTo=newClass))
      newClass.addToClass(
        'MultipleObjectsReturned',
        subclassException(
          str('MultipleObjectsReturned'),
          tuple(x.MultipleObjectsReturned for x in parents if hasattr(x, '_meta') and not x._meta.abstract) or (MultipleObjectsReturned,),
          module,
          attachedTo=newClass))
      if baseMeta and not baseMeta.abstract:
        # Non-abstract child classes inherit some attributes from their
        # non-abstract parent (unless an ABC comes before it in the
        # method resolution order).
        if not hasattr(meta, 'ordering'):
          newClass._meta.ordering = baseMeta.ordering
        if not hasattr(meta, 'getLatestBy'):
          newClass._meta.getLatestBy = baseMeta.getLatestBy

    isProxy = newClass._meta.proxy

    # If the modal is a proxy, ensure that the base class
    # hasn't been swapped out.
    if isProxy and baseMeta and baseMeta.swapped:
      raise TypeError("%s cannot proxy the swapped modal '%s'." % (name, baseMeta.swapped))

    if getattr(newClass, '_defaultManager', None):
      if not isProxy:
        # Multi-table inheritance doesn't inherit default manager from
        # parents.
        newClass._defaultManager = None
        newClass._baseManager = None
      else:
        # Proxy classes do inherit parent's default manager, if none is
        # set explicitly.
        newClass._defaultManager = newClass._defaultManager._copyToModel(newClass)
        newClass._baseManager = newClass._baseManager._copyToModel(newClass)

    # Add all attributes to the class.
    for objName, obj in attrs.items():
      newClass.addToClass(objName, obj)

    # All the fields of any type declared on this modal
    newFields = (
      newClass._meta.localFields +
      newClass._meta.localManyToMany +
      newClass._meta.virtualFields
    )
    fieldNames = set(f.name for f in newFields)

    # Basic setup for proxy model.
    if isProxy:
      base = None
      for parent in [kls for kls in parents if hasattr(kls, '_meta')]:
        if parent._meta.abstract:
          if parent._meta.fields:
            raise TypeError("Abstract base class containing modal fields not permitted for proxy modal '%s'." % name)
          else:
            continue
        if base is not None:
          raise TypeError("Proxy modal '%s' has more than one non-abstract modal base class." % name)
        else:
          base = parent
      if base is None:
        raise TypeError("Proxy modal '%s' has no non-abstract modal base class." % name)
      newClass._meta.setupProxy(base)
      newClass._meta.concreteModel = base._meta.concreteModel
    else:
      newClass._meta.concreteModel = newClass

    # Collect the parent links for multi-table inheritance.
    parentLinks = {}
    for base in reversed([newClass] + parents):
      # Conceptually equivalent to `if base is Model`.
      if not hasattr(base, '_meta'):
        continue
      # Skip concrete parent classes.
      if base != newClass and not base._meta.abstract:
        continue
      # Locate OneToOneField instances.
      for field in base._meta.localFields:
        if isinstance(field, OneToOneField):
          parentLinks[field.rel.to] = field

    # Do the appropriate setup for any modal parents.
    for base in parents:
      originalBase = base
      if not hasattr(base, '_meta'):
        # Things without _meta aren't functional model, so they're
        # uninteresting parents.
        continue

      parentFields = base._meta.localFields + base._meta.localManyToMany
      # Check for clashes between locally declared fields and those
      # on the base classes (we cannot handle shadowed fields at the
      # moment).
      for field in parentFields:
        if field.name in fieldNames:
          raise FieldError(
            'Local field %r in class %r clashes '
            'with field of similar name from '
            'base class %r' % (field.name, name, base.__name__)
          )
      if not base._meta.abstract:
        # Concrete classes...
        base = base._meta.concreteModel
        if base in parentLinks:
          field = parentLinks[base]
        elif not isProxy:
          attrName = '%sPtr' % base._meta.modelName
          field = OneToOneField(base, name=attrName,
              autoCreated=True, parentLink=True)
          # Only add the ptr field if it's not already present;
          # e.g. migrations will already have it specified
          if not hasattr(newClass, attrName):
            newClass.addToClass(attrName, field)
        else:
          field = None
        newClass._meta.parents[base] = field
      else:
        # .. and abstract ones.
        for field in parentFields:
          newClass.addToClass(field.name, copy.deepcopy(field))

        # Pass any non-abstract parent classes onto child.
        newClass._meta.parents.update(base._meta.parents)

      # Inherit managers from the abstract base classes.
      newClass.copyManagers(base._meta.abstractManagers)

      # Proxy model inherit the non-abstract managers from their base,
      # unless they have redefined any of them.
      if isProxy:
        newClass.copyManagers(originalBase._meta.concreteManagers)

      # Inherit virtual fields (like GenericForeignKey) from the parent
      # class
      for field in base._meta.virtualFields:
        if base._meta.abstract and field.name in fieldNames:
          raise FieldError(
            'Local field %r in class %r clashes '
            'with field of similar name from '
            'abstract base class %r' % (field.name, name, base.__name__)
          )
        newClass.addToClass(field.name, copy.deepcopy(field))

    if abstract:
      # Abstract base model can't be instantiated and don't appear in
      # the list of model for an app. We do the final setup for them a
      # little differently from normal model.
      attrMeta.abstract = False
      newClass.Meta = attrMeta
      return newClass

    newClass._prepare()
    newClass._meta.apps.registerModel(newClass._meta.appLabel, newClass)
    return newClass

  def copyManagers(cls, baseManagers):
    # This is in-place sorting of an Options attribute, but that's fine.
    baseManagers.sort()
    for _, mgrName, manager in baseManagers:  # NOQA (redefinition of _)
      val = getattr(cls, mgrName, None)
      if not val or val is manager:
        newManager = manager._copyToModel(cls)
        cls.addToClass(mgrName, newManager)

  def addToClass(cls, name, value):
    if hasattr(value, 'contributeToClass'):
      value.contributeToClass(cls, name)
    else:
      setattr(cls, name, value)

  def _prepare(cls):
    """
    Creates some methods once self._meta has been populated.
    """
    opts = cls._meta
    opts._prepare(cls)

    if opts.orderWithRespectTo:
      cls.getNextInOrder = curry(cls._getNextOrPreviousInOrder, isNext=True)
      cls.getPreviousInOrder = curry(cls._getNextOrPreviousInOrder, isNext=False)

      # defer creating accessors on the foreign class until we are
      # certain it has been created
      def makeForeignOrderAccessors(field, modal, cls):
        setattr(
          field.rel.to,
          'get_%sOrder' % cls.__name__.lower(),
          curry(methodGetOrder, cls)
        )
        setattr(
          field.rel.to,
          'set_%sOrder' % cls.__name__.lower(),
          curry(methodSetOrder, cls)
        )
      addLazyRelation(
        cls,
        opts.orderWithRespectTo,
        opts.orderWithRespectTo.rel.to,
        makeForeignOrderAccessors
      )

    # Give the class a docstring -- its definition.
    if cls.__doc__ is None:
      cls.__doc__ = "%s(%s)" % (cls.__name__, ", ".join(f.attname for f in opts.fields))

    if hasattr(cls, 'getAbsoluteUrl'):
      cls.getAbsoluteUrl = update_wrapper(curry(getAbsoluteUrl, opts, cls.getAbsoluteUrl),
                         cls.getAbsoluteUrl)

    signals.classPrepared.send(sender=cls)


class ModelState(object):
  """
  A class for storing instance state
  """
  def __init__(self, db=None):
    self.db = db
    # If true, uniqueness validation checks will consider this a new, as-yet-unsaved object.
    # Necessary for correct validation of new instances of objects with explicit (non-auto) PKs.
    # This impacts validation only; it has no effect on the actual save.
    self.adding = True


class Model(six.withMetaclass(ModelBase)):
  _deferred = False

  def __init__(self, *args, **kwargs):
    signals.preInit.send(sender=self.__class__, args=args, kwargs=kwargs)

    # Set up the storage for instance state
    self._state = ModelState()

    # There is a rather weird disparity here; if kwargs, it's set, then args
    # overrides it. It should be one or the other; don't duplicate the work
    # The reason for the kwargs check is that standard iterator passes in by
    # args, and instantiation for iteration is 33% faster.
    argsLen = len(args)
    if argsLen > len(self._meta.concreteFields):
      # Daft, but matches old exception sans the err msg.
      raise IndexError("Number of args exceeds number of fields")

    if not kwargs:
      fieldsIter = iter(self._meta.concreteFields)
      # The ordering of the zip calls matter - zip throws StopIteration
      # when an iter throws it. So if the first iter throws it, the second
      # is *not* consumed. We rely on this, so don't change the order
      # without changing the logic.
      for val, field in zip(args, fieldsIter):
        setattr(self, field.attname, val)
    else:
      # Slower, kwargs-ready version.
      fieldsIter = iter(self._meta.fields)
      for val, field in zip(args, fieldsIter):
        setattr(self, field.attname, val)
        kwargs.pop(field.name, None)
        # Maintain compatibility with existing calls.
        if isinstance(field.rel, ManyToOneRel):
          kwargs.pop(field.attname, None)

    # Now we're left with the unprocessed fields that *must* come from
    # keywords, or default.

    for field in fieldsIter:
      isRelatedObject = False
      # This slightly odd construct is so that we can access any
      # data-descriptor object (DeferredAttribute) without triggering its
      # __get__ method.
      if (field.attname not in kwargs and
          (isinstance(self.__class__.__dict__.get(field.attname), DeferredAttribute)
           or field.column is None)):
        # This field will be populated on request.
        continue
      if kwargs:
        if isinstance(field.rel, ForeignObjectRel):
          try:
            # Assume object instance was passed in.
            relObj = kwargs.pop(field.name)
            isRelatedObject = True
          except KeyError:
            try:
              # Object instance wasn't passed in -- must be an ID.
              val = kwargs.pop(field.attname)
            except KeyError:
              val = field.getDefault()
          else:
            # Object instance was passed in. Special case: You can
            # pass in "None" for related objects if it's allowed.
            if relObj is None and field.null:
              val = None
        else:
          try:
            val = kwargs.pop(field.attname)
          except KeyError:
            # This is done with an exception rather than the
            # default argument on pop because we don't want
            # getDefault() to be evaluated, and then not used.
            # Refs #12057.
            val = field.getDefault()
      else:
        val = field.getDefault()

      if isRelatedObject:
        # If we are passed a related instance, set it using the
        # field.name instead of field.attname (e.g. "user" instead of
        # "userId") so that the object gets properly cached (and type
        # checked) by the RelatedObjectDescriptor.
        setattr(self, field.name, relObj)
      else:
        setattr(self, field.attname, val)

    if kwargs:
      for prop in list(kwargs):
        try:
          if isinstance(getattr(self.__class__, prop), property):
            setattr(self, prop, kwargs.pop(prop))
        except AttributeError:
          pass
      if kwargs:
        raise TypeError("'%s' is an invalid keyword argument for this function" % list(kwargs)[0])
    super(Model, self).__init__()
    signals.postInit.send(sender=self.__class__, instance=self)

  def __repr__(self):
    try:
      u = six.textType(self)
    except (UnicodeEncodeError, UnicodeDecodeError):
      u = '[Bad Unicode data]'
    return forceStr('<%s: %s>' % (self.__class__.__name__, u))

  def __str__(self):
    if six.PY2 and hasattr(self, '__unicode__'):
      return forceText(self).encode('utf-8')
    return '%s object' % self.__class__.__name__

  def __eq__(self, other):
    if not isinstance(other, Model):
      return False
    if self._meta.concreteModel != other._meta.concreteModel:
      return False
    myPk = self._getPkVal()
    if myPk is None:
      return self is other
    return myPk == other._getPkVal()

  def __ne__(self, other):
    return not self.__eq__(other)

  def __hash__(self):
    if self._getPkVal() is None:
      raise TypeError("Model instances without primary key value are unhashable")
    return hash(self._getPkVal())

  def __reduce__(self):
    """
    Provides pickling support. Normally, this just dispatches to Python's
    standard handling. However, for model with deferred field loading, we
    need to do things manually, as they're dynamically created classes and
    only module-level classes can be pickled by the default path.
    """
    data = self.__dict__
    if not self._deferred:
      classId = self._meta.appLabel, self._meta.objectName
      return modalUnpickle, (classId, [], simpleClassFactory), data
    defers = []
    for field in self._meta.fields:
      if isinstance(self.__class__.__dict__.get(field.attname),
             DeferredAttribute):
        defers.append(field.attname)
    modal = self._meta.proxyForModel
    classId = modal._meta.appLabel, modal._meta.objectName
    return (modalUnpickle, (classId, defers, deferredClassFactory), data)

  def _getPkVal(self, meta=None):
    if not meta:
      meta = self._meta
    return getattr(self, meta.pk.attname)

  def _setPkVal(self, value):
    return setattr(self, self._meta.pk.attname, value)

  pk = property(_getPkVal, _setPkVal)

  def serializableValue(self, fieldName):
    """
    Returns the value of the field name for this instance. If the field is
    a foreign key, returns the id value, instead of the object. If there's
    no Field object with this name on the modal, the modal attribute's
    value is returned directly.

    Used to serialize a field's value (in the serializer, or form output,
    for example). Normally, you would just access the attribute directly
    and not use this method.
    """
    try:
      field = self._meta.getFieldByName(fieldName)[0]
    except FieldDoesNotExist:
      return getattr(self, fieldName)
    return getattr(self, field.attname)

  def save(self, forceInsert=False, forceUpdate=False, using=None,
       updateFields=None):
    """
    Saves the current instance. Override this in a subclass if you want to
    control the saving process.

    The 'forceInsert' and 'forceUpdate' parameters can be used to insist
    that the "save" must be an SQL insert or update (or equivalent for
    non-SQL backends), respectively. Normally, they should not be set.
    """
    using = using or router.dbForWrite(self.__class__, instance=self)
    if forceInsert and (forceUpdate or updateFields):
      raise ValueError("Cannot force both insert and updating in modal saving.")

    if updateFields is not None:
      # If updateFields is empty, skip the save. We do also check for
      # no-op saves later on for inheritance cases. This bailout is
      # still needed for skipping signal sending.
      if len(updateFields) == 0:
        return

      updateFields = frozenset(updateFields)
      fieldNames = set()

      for field in self._meta.fields:
        if not field.primaryKey:
          fieldNames.add(field.name)

          if field.name != field.attname:
            fieldNames.add(field.attname)

      nonModelFields = updateFields.difference(fieldNames)

      if nonModelFields:
        raise ValueError("The following fields do not exist in this "
                 "modal or are m2m fields: %s"
                 % ', '.join(nonModelFields))

    # If saving to the same database, and this modal is deferred, then
    # automatically do a "updateFields" save on the loaded fields.
    elif not forceInsert and self._deferred and using == self._state.db:
      fieldNames = set()
      for field in self._meta.concreteFields:
        if not field.primaryKey and not hasattr(field, 'through'):
          fieldNames.add(field.attname)
      deferredFields = [
        f.attname for f in self._meta.fields
        if (f.attname not in self.__dict__ and
          isinstance(self.__class__.__dict__[f.attname], DeferredAttribute))
      ]

      loadedFields = fieldNames.difference(deferredFields)
      if loadedFields:
        updateFields = frozenset(loadedFields)

    self.saveBase(using=using, forceInsert=forceInsert,
            forceUpdate=forceUpdate, updateFields=updateFields)
  save.altersData = True

  def saveBase(self, raw=False, forceInsert=False,
         forceUpdate=False, using=None, updateFields=None):
    """
    Handles the parts of saving which should be done only once per save,
    yet need to be done in raw saves, too. This includes some sanity
    checks and signal sending.

    The 'raw' argument is telling saveBase not to save any parent
    model and not to do any changes to the values before save. This
    is used by fixture loading.
    """
    using = using or router.dbForWrite(self.__class__, instance=self)
    assert not (forceInsert and (forceUpdate or updateFields))
    assert updateFields is None or len(updateFields) > 0
    cls = origin = self.__class__
    # Skip proxies, but keep the origin as the proxy modal.
    if cls._meta.proxy:
      cls = cls._meta.concreteModel
    meta = cls._meta
    if not meta.autoCreated:
      signals.preSave.send(sender=origin, instance=self, raw=raw, using=using,
                 updateFields=updateFields)
    with transaction.commitOnSuccessUnlessManaged(using=using, savepoint=False):
      if not raw:
        self._saveParents(cls, using, updateFields)
      updated = self._saveTable(raw, cls, forceInsert, forceUpdate, using, updateFields)
    # Store the database on which the object was saved
    self._state.db = using
    # Once saved, this is no longer a to-be-added instance.
    self._state.adding = False

    # Signal that the save is complete
    if not meta.autoCreated:
      signals.postSave.send(sender=origin, instance=self, created=(not updated),
                  updateFields=updateFields, raw=raw, using=using)

  saveBase.altersData = True

  def _saveParents(self, cls, using, updateFields):
    """
    Saves all the parents of cls using values from self.
    """
    meta = cls._meta
    for parent, field in meta.parents.items():
      # Make sure the link fields are synced between parent and self.
      if (field and getattr(self, parent._meta.pk.attname) is None
          and getattr(self, field.attname) is not None):
        setattr(self, parent._meta.pk.attname, getattr(self, field.attname))
      self._saveParents(cls=parent, using=using, updateFields=updateFields)
      self._saveTable(cls=parent, using=using, updateFields=updateFields)
      # Set the parent's PK value to self.
      if field:
        setattr(self, field.attname, self._getPkVal(parent._meta))
        # Since we didn't have an instance of the parent handy set
        # attname directly, bypassing the descriptor. Invalidate
        # the related object cache, in case it's been accidentally
        # populated. A fresh instance will be re-built from the
        # database if necessary.
        cacheName = field.getCacheName()
        if hasattr(self, cacheName):
          delattr(self, cacheName)

  def _saveTable(self, raw=False, cls=None, forceInsert=False,
          forceUpdate=False, using=None, updateFields=None):
    """
    Does the heavy-lifting involved in saving. Updates or inserts the data
    for a single table.
    """
    meta = cls._meta
    nonPks = [f for f in meta.localConcreteFields if not f.primaryKey]

    if updateFields:
      nonPks = [f for f in nonPks
            if f.name in updateFields or f.attname in updateFields]

    pkVal = self._getPkVal(meta)
    pkSet = pkVal is not None
    if not pkSet and (forceUpdate or updateFields):
      raise ValueError("Cannot force an update in save() with no primary key.")
    updated = False
    # If possible, try an UPDATE. If that doesn't update anything, do an INSERT.
    if pkSet and not forceInsert:
      baseQs = cls._baseManager.using(using)
      values = [(f, None, (getattr(self, f.attname) if raw else f.preSave(self, False)))
           for f in nonPks]
      forcedUpdate = updateFields or forceUpdate
      updated = self._doUpdate(baseQs, using, pkVal, values, updateFields,
                   forcedUpdate)
      if forceUpdate and not updated:
        raise DatabaseError("Forced update did not affect any rows.")
      if updateFields and not updated:
        raise DatabaseError("Save with updateFields did not affect any rows.")
    if not updated:
      if meta.orderWithRespectTo:
        # If this is a modal with an orderWithRespectTo
        # autopopulate the _order field
        field = meta.orderWithRespectTo
        orderValue = cls._baseManager.using(using).filter(
          **{field.name: getattr(self, field.attname)}).count()
        self._order = orderValue

      fields = meta.localConcreteFields
      if not pkSet:
        fields = [f for f in fields if not isinstance(f, AutoField)]

      updatePk = bool(meta.hasAutoField and not pkSet)
      result = self._doInsert(cls._baseManager, using, fields, updatePk, raw)
      if updatePk:
        setattr(self, meta.pk.attname, result)
    return updated

  def _doUpdate(self, baseQs, using, pkVal, values, updateFields, forcedUpdate):
    """
    This method will try to update the modal. If the modal was updated (in
    the sense that an update query was done and a matching row was found
    from the DB) the method will return True.
    """
    filtered = baseQs.filter(pk=pkVal)
    if not values:
      # We can end up here when saving a modal in inheritance chain where
      # updateFields doesn't target any field in current modal. In that
      # case we just say the update succeeded. Another case ending up here
      # is a modal with just PK - in that case check that the PK still
      # exists.
      return updateFields is not None or filtered.exists()
    if self._meta.selectOnSave and not forcedUpdate:
      if filtered.exists():
        filtered._update(values)
        return True
      else:
        return False
    return filtered._update(values) > 0

  def _doInsert(self, manager, using, fields, updatePk, raw):
    """
    Do an INSERT. If updatePk is defined then this method should return
    the new pk for the modal.
    """
    return manager._insert([self], fields=fields, returnId=updatePk,
                using=using, raw=raw)

  def delete(self, using=None):
    using = using or router.dbForWrite(self.__class__, instance=self)
    assert self._getPkVal() is not None, "%s object can't be deleted because its %s attribute is set to None." % (self._meta.objectName, self._meta.pk.attname)

    collector = Collector(using=using)
    collector.collect([self])
    collector.delete()

  delete.altersData = True

  def _get_FIELD_display(self, field):
    value = getattr(self, field.attname)
    return forceText(dict(field.flatchoices).get(value, value), stringsOnly=True)

  def _getNextOrPreviousBy_FIELD(self, field, isNext, **kwargs):
    if not self.pk:
      raise ValueError("getNext/getPrevious cannot be used on unsaved objects.")
    op = 'gt' if isNext else 'lt'
    order = '' if isNext else '-'
    param = forceText(getattr(self, field.attname))
    q = Q(**{'%s__%s' % (field.name, op): param})
    q = q | Q(**{field.name: param, 'pk__%s' % op: self.pk})
    qs = self.__class__._defaultManager.using(self._state.db).filter(**kwargs).filter(q).orderBy('%s%s' % (order, field.name), '%spk' % order)
    try:
      return qs[0]
    except IndexError:
      raise self.DoesNotExist("%s matching query does not exist." % self.__class__._meta.objectName)

  def _getNextOrPreviousInOrder(self, isNext):
    cachename = "__%sOrderCache" % isNext
    if not hasattr(self, cachename):
      op = 'gt' if isNext else 'lt'
      order = '_order' if isNext else '-_order'
      orderField = self._meta.orderWithRespectTo
      obj = self._defaultManager.filter(**{
        orderField.name: getattr(self, orderField.attname)
      }).filter(**{
        '_order__%s' % op: self._defaultManager.values('_order').filter(**{
          self._meta.pk.name: self.pk
        })
      }).orderBy(order)[:1].get()
      setattr(self, cachename, obj)
    return getattr(self, cachename)

  def prepareDatabaseSave(self, unused):
    if self.pk is None:
      raise ValueError("Unsaved modal instance %r cannot be used in an ORM query." % self)
    return self.pk

  def clean(self):
    """
    Hook for doing any extra modal-wide validation after clean() has been
    called on every field by self.cleanFields. Any ValidationError raised
    by this method will not be associated with a particular field; it will
    have a special-case association with the field defined by NON_FIELD_ERRORS.
    """
    pass

  def validateUnique(self, exclude=None):
    """
    Checks unique constraints on the modal and raises ``ValidationError``
    if any failed.
    """
    uniqueChecks, dateChecks = self._getUniqueChecks(exclude=exclude)

    errors = self._performUniqueChecks(uniqueChecks)
    dateErrors = self._performDateChecks(dateChecks)

    for k, v in dateErrors.items():
      errors.setdefault(k, []).extend(v)

    if errors:
      raise ValidationError(errors)

  def _getUniqueChecks(self, exclude=None):
    """
    Gather a list of checks to perform. Since validateUnique could be
    called from a ModelForm, some fields may have been excluded; we can't
    perform a unique check on a modal that is missing fields involved
    in that check.
    Fields that did not validate should also be excluded, but they need
    to be passed in via the exclude argument.
    """
    if exclude is None:
      exclude = []
    uniqueChecks = []

    uniqueTogethers = [(self.__class__, self._meta.uniqueTogether)]
    for parentClass in self._meta.parents.keys():
      if parentClass._meta.uniqueTogether:
        uniqueTogethers.append((parentClass, parentClass._meta.uniqueTogether))

    for modalClass, uniqueTogether in uniqueTogethers:
      for check in uniqueTogether:
        for name in check:
          # If this is an excluded field, don't add this check.
          if name in exclude:
            break
        else:
          uniqueChecks.append((modalClass, tuple(check)))

    # These are checks for the uniqueFor_<date/year/month>.
    dateChecks = []

    # Gather a list of checks for fields declared as unique and add them to
    # the list of checks.

    fieldsWithClass = [(self.__class__, self._meta.localFields)]
    for parentClass in self._meta.parents.keys():
      fieldsWithClass.append((parentClass, parentClass._meta.localFields))

    for modalClass, fields in fieldsWithClass:
      for f in fields:
        name = f.name
        if name in exclude:
          continue
        if f.unique:
          uniqueChecks.append((modalClass, (name,)))
        if f.uniqueForDate and f.uniqueForDate not in exclude:
          dateChecks.append((modalClass, 'date', name, f.uniqueForDate))
        if f.uniqueForYear and f.uniqueForYear not in exclude:
          dateChecks.append((modalClass, 'year', name, f.uniqueForYear))
        if f.uniqueForMonth and f.uniqueForMonth not in exclude:
          dateChecks.append((modalClass, 'month', name, f.uniqueForMonth))
    return uniqueChecks, dateChecks

  def _performUniqueChecks(self, uniqueChecks):
    errors = {}

    for modalClass, uniqueCheck in uniqueChecks:
      # Try to look up an existing object with the same values as this
      # object's values for all the unique field.

      lookupKwargs = {}
      for fieldName in uniqueCheck:
        f = self._meta.getField(fieldName)
        lookupValue = getattr(self, f.attname)
        if lookupValue is None:
          # no value, skip the lookup
          continue
        if f.primaryKey and not self._state.adding:
          # no need to check for unique primary key when editing
          continue
        lookupKwargs[str(fieldName)] = lookupValue

      # some fields were skipped, no reason to do the check
      if len(uniqueCheck) != len(lookupKwargs):
        continue

      qs = modalClass._defaultManager.filter(**lookupKwargs)

      # Exclude the current object from the query if we are editing an
      # instance (as opposed to creating a new one)
      # Note that we need to use the pk as defined by modalClass, not
      # self.pk. These can be different fields because modal inheritance
      # allows single modal to have effectively multiple primary keys.
      # Refs #17615.
      modalClassPk = self._getPkVal(modalClass._meta)
      if not self._state.adding and modalClassPk is not None:
        qs = qs.exclude(pk=modalClassPk)
      if qs.exists():
        if len(uniqueCheck) == 1:
          key = uniqueCheck[0]
        else:
          key = NON_FIELD_ERRORS
        errors.setdefault(key, []).append(self.uniqueErrorMessage(modalClass, uniqueCheck))

    return errors

  def _performDateChecks(self, dateChecks):
    errors = {}
    for modalClass, lookupType, field, uniqueFor in dateChecks:
      lookupKwargs = {}
      # there's a ticket to add a date lookup, we can remove this special
      # case if that makes it's way in
      date = getattr(self, uniqueFor)
      if date is None:
        continue
      if lookupType == 'date':
        lookupKwargs['%s__day' % uniqueFor] = date.day
        lookupKwargs['%s__month' % uniqueFor] = date.month
        lookupKwargs['%s__year' % uniqueFor] = date.year
      else:
        lookupKwargs['%s__%s' % (uniqueFor, lookupType)] = getattr(date, lookupType)
      lookupKwargs[field] = getattr(self, field)

      qs = modalClass._defaultManager.filter(**lookupKwargs)
      # Exclude the current object from the query if we are editing an
      # instance (as opposed to creating a new one)
      if not self._state.adding and self.pk is not None:
        qs = qs.exclude(pk=self.pk)

      if qs.exists():
        errors.setdefault(field, []).append(
          self.dateErrorMessage(lookupType, field, uniqueFor)
        )
    return errors

  def dateErrorMessage(self, lookupType, fieldName, uniqueFor):
    opts = self._meta
    field = opts.getField(fieldName)
    return ValidationError(
      message=field.errorMessages['uniqueForDate'],
      code='uniqueForDate',
      params={
        'modal': self,
        'modelName': six.textType(capfirst(opts.verboseName)),
        'lookupType': lookupType,
        'field': fieldName,
        'fieldLabel': six.textType(capfirst(field.verboseName)),
        'dateField': uniqueFor,
        'dateFieldLabel': six.textType(capfirst(opts.getField(uniqueFor).verboseName)),
      }
    )

  def uniqueErrorMessage(self, modalClass, uniqueCheck):
    opts = modalClass._meta

    params = {
      'modal': self,
      'modalClass': modalClass,
      'modelName': six.textType(capfirst(opts.verboseName)),
      'uniqueCheck': uniqueCheck,
    }

    # A unique field
    if len(uniqueCheck) == 1:
      field = opts.getField(uniqueCheck[0])
      params['fieldLabel'] = six.textType(capfirst(field.verboseName))
      return ValidationError(
        message=field.errorMessages['unique'],
        code='unique',
        params=params,
      )

    # uniqueTogether
    else:
      fieldLabels = [capfirst(opts.getField(f).verboseName) for f in uniqueCheck]
      params['fieldLabels'] = six.textType(getTextList(fieldLabels, _('and')))
      return ValidationError(
        message=_("%(modelName)s with this %(fieldLabels)s already exists."),
        code='uniqueTogether',
        params=params,
      )

  def fullClean(self, exclude=None, validateUnique=True):
    """
    Calls cleanFields, clean, and validateUnique, on the modal,
    and raises a ``ValidationError`` for any errors that occurred.
    """
    errors = {}
    if exclude is None:
      exclude = []
    else:
      exclude = list(exclude)

    try:
      self.cleanFields(exclude=exclude)
    except ValidationError as e:
      errors = e.updateErrorDict(errors)

    # Form.clean() is run even if other validation fails, so do the
    # same with Model.clean() for consistency.
    try:
      self.clean()
    except ValidationError as e:
      errors = e.updateErrorDict(errors)

    # Run unique checks, but only for fields that passed validation.
    if validateUnique:
      for name in errors.keys():
        if name != NON_FIELD_ERRORS and name not in exclude:
          exclude.append(name)
      try:
        self.validateUnique(exclude=exclude)
      except ValidationError as e:
        errors = e.updateErrorDict(errors)

    if errors:
      raise ValidationError(errors)

  def cleanFields(self, exclude=None):
    """
    Cleans all fields and raises a ValidationError containing a dict
    of all validation errors if any occur.
    """
    if exclude is None:
      exclude = []

    errors = {}
    for f in self._meta.fields:
      if f.name in exclude:
        continue
      # Skip validation for empty fields with blank=True. The developer
      # is responsible for making sure they have a valid value.
      rawValue = getattr(self, f.attname)
      if f.blank and rawValue in f.emptyValues:
        continue
      try:
        setattr(self, f.attname, f.clean(rawValue, self))
      except ValidationError as e:
        errors[f.name] = e.errorList

    if errors:
      raise ValidationError(errors)

  @classmethod
  def check(cls, **kwargs):
    errors = []
    errors.extend(cls._checkSwappable())
    errors.extend(cls._checkModel())
    errors.extend(cls._checkManagers(**kwargs))
    if not cls._meta.swapped:
      errors.extend(cls._checkFields(**kwargs))
      errors.extend(cls._checkM2mThroughSameRelationship())
      clashErrors = cls._checkIdField() + cls._checkFieldNameClashes()
      errors.extend(clashErrors)
      # If there are field name clashes, hide consequent column name
      # clashes.
      if not clashErrors:
        errors.extend(cls._checkColumnNameClashes())
      errors.extend(cls._checkIndexTogether())
      errors.extend(cls._checkUniqueTogether())
      errors.extend(cls._checkOrdering())

    return errors

  @classmethod
  def _checkSwappable(cls):
    """ Check if the swapped modal exists. """

    errors = []
    if cls._meta.swapped:
      try:
        apps.getModel(cls._meta.swapped)
      except ValueError:
        errors.append(
          checks.Error(
            "'%s' is not of the form 'appLabel.appName'." % cls._meta.swappable,
            hint=None,
            obj=None,
            id='model.E001',
          )
        )
      except LookupError:
        appLabel, modelName = cls._meta.swapped.split('.')
        errors.append(
          checks.Error(
            ("'%s' references '%s.%s', which has not been installed, or is abstract.") % (
              cls._meta.swappable, appLabel, modelName
            ),
            hint=None,
            obj=None,
            id='model.E002',
          )
        )
    return errors

  @classmethod
  def _checkModel(cls):
    errors = []
    if cls._meta.proxy:
      if cls._meta.localFields or cls._meta.localManyToMany:
        errors.append(
          checks.Error(
            "Proxy modal '%s' contains modal fields." % cls.__name__,
            hint=None,
            obj=None,
            id='model.E017',
          )
        )
    return errors

  @classmethod
  def _checkManagers(cls, **kwargs):
    """ Perform all manager checks. """

    errors = []
    managers = cls._meta.concreteManagers + cls._meta.abstractManagers
    for __, __, manager in managers:
      errors.extend(manager.check(**kwargs))
    return errors

  @classmethod
  def _checkFields(cls, **kwargs):
    """ Perform all field checks. """

    errors = []
    for field in cls._meta.localFields:
      errors.extend(field.check(**kwargs))
    for field in cls._meta.localManyToMany:
      errors.extend(field.check(fromModel=cls, **kwargs))
    return errors

  @classmethod
  def _checkM2mThroughSameRelationship(cls):
    """ Check if no relationship modal is used by more than one m2m field.
    """

    errors = []
    seenIntermediarySignatures = []

    fields = cls._meta.localManyToMany

    # Skip when the target modal wasn't found.
    fields = (f for f in fields if isinstance(f.rel.to, ModelBase))

    # Skip when the relationship modal wasn't found.
    fields = (f for f in fields if isinstance(f.rel.through, ModelBase))

    for f in fields:
      signature = (f.rel.to, cls, f.rel.through)
      if signature in seenIntermediarySignatures:
        errors.append(
          checks.Error(
            ("The modal has two many-to-many relations through "
             "the intermediate modal '%s.%s'.") % (
              f.rel.through._meta.appLabel,
              f.rel.through._meta.objectName
            ),
            hint=None,
            obj=cls,
            id='model.E003',
          )
        )
      else:
        seenIntermediarySignatures.append(signature)
    return errors

  @classmethod
  def _checkIdField(cls):
    """ Check if `id` field is a primary key. """

    fields = list(f for f in cls._meta.localFields
      if f.name == 'id' and f != cls._meta.pk)
    # fields is empty or consists of the invalid "id" field
    if fields and not fields[0].primaryKey and cls._meta.pk.name == 'id':
      return [
        checks.Error(
          ("'id' can only be used as a field name if the field also "
           "sets 'primaryKey=True'."),
          hint=None,
          obj=cls,
          id='model.E004',
        )
      ]
    else:
      return []

  @classmethod
  def _checkFieldNameClashes(cls):
    """ Ref #17673. """

    errors = []
    usedFields = {}  # name or attname -> field

    # Check that multi-inheritance doesn't cause field name shadowing.
    for parent in cls._meta.parents:
      for f in parent._meta.localFields:
        clash = usedFields.get(f.name) or usedFields.get(f.attname) or None
        if clash:
          errors.append(
            checks.Error(
              ("The field '%s' from parent modal "
               "'%s' clashes with the field '%s' "
               "from parent modal '%s'.") % (
                clash.name, clash.modal._meta,
                f.name, f.modal._meta
              ),
              hint=None,
              obj=cls,
              id='model.E005',
            )
          )
        usedFields[f.name] = f
        usedFields[f.attname] = f

    # Check that fields defined in the modal don't clash with fields from
    # parents.
    for f in cls._meta.localFields:
      clash = usedFields.get(f.name) or usedFields.get(f.attname) or None
      # Note that we may detect clash between user-defined non-unique
      # field "id" and automatically added unique field "id", both
      # defined at the same modal. This special case is considered in
      # _checkIdField and here we ignore it.
      idConflict = (f.name == "id" and
        clash and clash.name == "id" and clash.modal == cls)
      if clash and not idConflict:
        errors.append(
          checks.Error(
            ("The field '%s' clashes with the field '%s' "
             "from modal '%s'.") % (
              f.name, clash.name, clash.modal._meta
            ),
            hint=None,
            obj=f,
            id='model.E006',
          )
        )
      usedFields[f.name] = f
      usedFields[f.attname] = f

    return errors

  @classmethod
  def _checkColumnNameClashes(cls):
    # Store a list of column names which have already been used by other fields.
    usedColumnNames = []
    errors = []

    for f in cls._meta.localFields:
      _, columnName = f.getAttnameColumn()

      # Ensure the column name is not already in use.
      if columnName and columnName in usedColumnNames:
        errors.append(
          checks.Error(
            "Field '%s' has column name '%s' that is used by another field." % (f.name, columnName),
            hint="Specify a 'dbColumn' for the field.",
            obj=cls,
            id='model.E007'
          )
        )
      else:
        usedColumnNames.append(columnName)

    return errors

  @classmethod
  def _checkIndexTogether(cls):
    """ Check the value of "indexTogether" option. """
    if not isinstance(cls._meta.indexTogether, (tuple, list)):
      return [
        checks.Error(
          "'indexTogether' must be a list or tuple.",
          hint=None,
          obj=cls,
          id='model.E008',
        )
      ]

    elif any(not isinstance(fields, (tuple, list))
        for fields in cls._meta.indexTogether):
      return [
        checks.Error(
          "All 'indexTogether' elements must be lists or tuples.",
          hint=None,
          obj=cls,
          id='model.E009',
        )
      ]

    else:
      errors = []
      for fields in cls._meta.indexTogether:
        errors.extend(cls._checkLocalFields(fields, "indexTogether"))
      return errors

  @classmethod
  def _checkUniqueTogether(cls):
    """ Check the value of "uniqueTogether" option. """
    if not isinstance(cls._meta.uniqueTogether, (tuple, list)):
      return [
        checks.Error(
          "'uniqueTogether' must be a list or tuple.",
          hint=None,
          obj=cls,
          id='model.E010',
        )
      ]

    elif any(not isinstance(fields, (tuple, list))
        for fields in cls._meta.uniqueTogether):
      return [
        checks.Error(
          "All 'uniqueTogether' elements must be lists or tuples.",
          hint=None,
          obj=cls,
          id='model.E011',
        )
      ]

    else:
      errors = []
      for fields in cls._meta.uniqueTogether:
        errors.extend(cls._checkLocalFields(fields, "uniqueTogether"))
      return errors

  @classmethod
  def _checkLocalFields(cls, fields, option):
    from theory.db import model

    errors = []
    for fieldName in fields:
      try:
        field = cls._meta.getField(fieldName,
          manyToMany=True)
      except model.FieldDoesNotExist:
        errors.append(
          checks.Error(
            "'%s' refers to the non-existent field '%s'." % (option, fieldName),
            hint=None,
            obj=cls,
            id='model.E012',
          )
        )
      else:
        if isinstance(field.rel, model.ManyToManyRel):
          errors.append(
            checks.Error(
              ("'%s' refers to a ManyToManyField '%s', but "
               "ManyToManyFields are not permitted in '%s'.") % (
                option, fieldName, option
              ),
              hint=None,
              obj=cls,
              id='model.E013',
            )
          )
    return errors

  @classmethod
  def _checkOrdering(cls):
    """ Check "ordering" option -- is it a list of strings and do all fields
    exist? """

    from theory.db.model import FieldDoesNotExist

    if not cls._meta.ordering:
      return []

    if not isinstance(cls._meta.ordering, (list, tuple)):
      return [
        checks.Error(
          ("'ordering' must be a tuple or list "
           "(even if you want to order by only one field)."),
          hint=None,
          obj=cls,
          id='model.E014',
        )
      ]

    errors = []

    fields = cls._meta.ordering

    # Skip '?' fields.
    fields = (f for f in fields if f != '?')

    # Convert "-field" to "field".
    fields = ((f[1:] if f.startswith('-') else f) for f in fields)

    fields = (f for f in fields if
      f != '_order' or not cls._meta.orderWithRespectTo)

    # Skip ordering in the format field1__field2 (FIXME: checking
    # this format would be nice, but it's a little fiddly).
    fields = (f for f in fields if '__' not in f)

    # Skip ordering on pk. This is always a valid orderBy field
    # but is an alias and therefore won't be found by opts.getField.
    fields = (f for f in fields if f != 'pk')

    for fieldName in fields:
      try:
        cls._meta.getField(fieldName, manyToMany=False)
      except FieldDoesNotExist:
        if fieldName.endswith('_id'):
          try:
            field = cls._meta.getField(fieldName[:-3], manyToMany=False)
          except FieldDoesNotExist:
            pass
          else:
            if field.attname == fieldName:
              continue
        errors.append(
          checks.Error(
            "'ordering' refers to the non-existent field '%s'." % fieldName,
            hint=None,
            obj=cls,
            id='model.E015',
          )
        )
    return errors


############################################
# HELPER FUNCTIONS (CURRIED MODEL METHODS) #
############################################

# ORDERING METHODS #########################

def methodSetOrder(orderedObj, self, idList, using=None):
  if using is None:
    using = DEFAULT_DB_ALIAS
  relVal = getattr(self, orderedObj._meta.orderWithRespectTo.rel.fieldName)
  orderName = orderedObj._meta.orderWithRespectTo.name
  # FIXME: It would be nice if there was an "update many" version of update
  # for situations like this.
  with transaction.commitOnSuccessUnlessManaged(using=using):
    for i, j in enumerate(idList):
      orderedObj.objects.filter(**{'pk': j, orderName: relVal}).update(_order=i)


def methodGetOrder(orderedObj, self):
  relVal = getattr(self, orderedObj._meta.orderWithRespectTo.rel.fieldName)
  orderName = orderedObj._meta.orderWithRespectTo.name
  pkName = orderedObj._meta.pk.name
  return [r[pkName] for r in
      orderedObj.objects.filter(**{orderName: relVal}).values(pkName)]


##############################################
# HELPER FUNCTIONS (CURRIED MODEL FUNCTIONS) #
##############################################

def getAbsoluteUrl(opts, func, self, *args, **kwargs):
  return settings.ABSOLUTE_URL_OVERRIDES.get('%s.%s' % (opts.appLabel, opts.modelName), func)(self, *args, **kwargs)


########
# MISC #
########


def simpleClassFactory(modal, attrs):
  """
  Needed for dynamic classes.
  """
  return modal


def modalUnpickle(modalId, attrs, factory):
  """
  Used to unpickle Model subclasses with deferred fields.
  """
  if isinstance(modalId, tuple):
    modal = apps.getModel(*modalId)
  else:
    # Backwards compat - the modal was cached directly in earlier versions.
    modal = modalId
  cls = factory(modal, attrs)
  return cls.__new__(cls)
modalUnpickle.__safeForUnpickle__ = True


def unpickleInnerException(klass, exceptionName):
  # Get the exception class from the class it is attached to:
  exception = getattr(klass, exceptionName)
  return exception.__new__(exception)
