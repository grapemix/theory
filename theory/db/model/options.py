from __future__ import unicode_literals

from bisect import bisect
from collections import OrderedDict
import warnings

from theory.apps import apps
from theory.conf import settings
from theory.db.model.fields.related import ManyToManyRel
from theory.db.model.fields import AutoField, FieldDoesNotExist
from theory.db.model.fields.proxy import OrderWrt
from theory.utils import six
from theory.utils.deprecation import RemovedInTheory20Warning
from theory.utils.encoding import forceText, smartText, python2UnicodeCompatible
from theory.utils.functional import cachedProperty
from theory.utils.text import camelCaseToSpaces
from theory.utils.translation import activate, deactivateAll, getLanguage, stringConcat


DEFAULT_NAMES = ('verboseName', 'verboseNamePlural', 'dbTable', 'ordering',
         'uniqueTogether', 'permissions', 'getLatestBy',
         'orderWithRespectTo', 'appLabel', 'dbTablespace',
         'abstract', 'managed', 'proxy', 'swappable', 'autoCreated',
         'indexTogether', 'apps', 'defaultPermissions',
         'selectOnSave')


def normalizeTogether(optionTogether):
  """
  optionTogether can be either a tuple of tuples, or a single
  tuple of two strings. Normalize it to a tuple of tuples, so that
  calling code can uniformly expect that.
  """
  try:
    if not optionTogether:
      return ()
    if not isinstance(optionTogether, (tuple, list)):
      raise TypeError
    firstElement = next(iter(optionTogether))
    if not isinstance(firstElement, (tuple, list)):
      optionTogether = (optionTogether,)
    # Normalize everything to tuples
    return tuple(tuple(ot) for ot in optionTogether)
  except TypeError:
    # If the value of optionTogether isn't valid, return it
    # verbatim; this will be picked up by the check framework later.
    return optionTogether


@python2UnicodeCompatible
class Options(object):
  def __init__(self, meta, appLabel=None):
    self.localFields = []
    self.localManyToMany = []
    self.virtualFields = []
    self.modelName = None
    self.verboseName = None
    self.verboseNamePlural = None
    self.dbTable = ''
    self.ordering = []
    self.uniqueTogether = []
    self.indexTogether = []
    self.selectOnSave = False
    self.defaultPermissions = ('add', 'change', 'delete')
    self.permissions = []
    self.objectName = None
    self.appLabel = appLabel
    self.getLatestBy = None
    self.orderWithRespectTo = None
    self.dbTablespace = settings.DEFAULT_TABLESPACE
    self.meta = meta
    self.pk = None
    self.hasAutoField = False
    self.autoField = None
    self.abstract = False
    self.managed = True
    self.proxy = False
    # For any class that is a proxy (including automatically created
    # classes for deferred object loading), proxyForModel tells us
    # which class this modal is proxying. Note that proxyForModel
    # can create a chain of proxy model. For non-proxy model, the
    # variable is always None.
    self.proxyForModel = None
    # For any non-abstract class, the concrete class is the modal
    # in the end of the proxyForModel chain. In particular, for
    # concrete model, the concreteModel is always the class itself.
    self.concreteModel = None
    self.swappable = None
    self.parents = OrderedDict()
    self.autoCreated = False

    # To handle various inheritance situations, we need to track where
    # managers came from (concrete or abstract base classes).
    self.abstractManagers = []
    self.concreteManagers = []

    # List of all lookups defined in ForeignKey 'limitChoicesTo' options
    # from *other* model. Needed for some admin checks. Internal use only.
    self.relatedFkeyLookups = []

    # A custom app registry to use, if you're making a separate modal set.
    self.apps = apps

  @property
  def appConfig(self):
    # Don't go through getAppConfig to avoid triggering imports.
    return self.apps.appConfigs.get(self.appLabel)

  @property
  def installed(self):
    return self.appConfig is not None

  def contributeToClass(self, cls, name):
    from theory.db import connection
    from theory.db.backends.utils import truncateName

    cls._meta = self
    self.modal = cls
    # First, construct the default values for these options.
    self.objectName = cls.__name__
    self.modelName = self.objectName.lower()
    self.verboseName = camelCaseToSpaces(self.objectName)

    # Store the original user-defined values for each option,
    # for use when serializing the modal definition
    self.originalAttrs = {}

    # Next, apply any overridden values from 'class Meta'.
    if self.meta:
      metaAttrs = self.meta.__dict__.copy()
      for name in self.meta.__dict__:
        # Ignore any private attributes that Theory doesn't care about.
        # NOTE: We can't modify a dictionary's contents while looping
        # over it, so we loop over the *original* dictionary instead.
        if name.startswith('_'):
          del metaAttrs[name]
      for attrName in DEFAULT_NAMES:
        if attrName in metaAttrs:
          setattr(self, attrName, metaAttrs.pop(attrName))
          self.originalAttrs[attrName] = getattr(self, attrName)
        elif hasattr(self.meta, attrName):
          setattr(self, attrName, getattr(self.meta, attrName))
          self.originalAttrs[attrName] = getattr(self, attrName)

      ut = metaAttrs.pop('uniqueTogether', self.uniqueTogether)
      self.uniqueTogether = normalizeTogether(ut)

      it = metaAttrs.pop('indexTogether', self.indexTogether)
      self.indexTogether = normalizeTogether(it)

      # verboseNamePlural is a special case because it uses a 's'
      # by default.
      if self.verboseNamePlural is None:
        self.verboseNamePlural = stringConcat(self.verboseName, 's')

      # Any leftover attributes must be invalid.
      if metaAttrs != {}:
        raise TypeError("'class Meta' got invalid attribute(s): %s" % ','.join(metaAttrs.keys()))
    else:
      self.verboseNamePlural = stringConcat(self.verboseName, 's')
    del self.meta

    # If the dbTable wasn't provided, use the appLabel + modelName.
    if not self.dbTable:
      self.dbTable = "%s_%s" % (self.appLabel, self.modelName)
      self.dbTable = truncateName(self.dbTable, connection.ops.maxNameLength())

  @property
  def moduleName(self):
    """
    This property has been deprecated in favor of `modelName`. refs #19689
    """
    warnings.warn(
      "Options.moduleName has been deprecated in favor of modelName",
      RemovedInTheory20Warning, stacklevel=2)
    return self.modelName

  def _prepare(self, modal):
    if self.orderWithRespectTo:
      self.orderWithRespectTo = self.getField(self.orderWithRespectTo)
      self.ordering = ('_order',)
      if not any(isinstance(field, OrderWrt) for field in modal._meta.localFields):
        modal.addToClass('_order', OrderWrt())
    else:
      self.orderWithRespectTo = None

    if self.pk is None:
      if self.parents:
        # Promote the first parent link in lieu of adding yet another
        # field.
        field = next(six.itervalues(self.parents))
        # Look for a local field with the same name as the
        # first parent link. If a local field has already been
        # created, use it instead of promoting the parent
        alreadyCreated = [fld for fld in self.localFields if fld.name == field.name]
        if alreadyCreated:
          field = alreadyCreated[0]
        field.primaryKey = True
        self.setupPk(field)
      else:
        auto = AutoField(verboseName='ID', primaryKey=True,
            autoCreated=True)
        modal.addToClass('id', auto)

  def addField(self, field):
    # Insert the given field in the order in which it was created, using
    # the "creationCounter" attribute of the field.
    # Move many-to-many related fields from self.fields into
    # self.manyToMany.
    if field.rel and isinstance(field.rel, ManyToManyRel):
      self.localManyToMany.insert(bisect(self.localManyToMany, field), field)
      if hasattr(self, '_m2mCache'):
        del self._m2mCache
    else:
      self.localFields.insert(bisect(self.localFields, field), field)
      self.setupPk(field)
      if hasattr(self, '_fieldCache'):
        del self._fieldCache
        del self._fieldNameCache
        # The fields, concreteFields and localConcreteFields are
        # implemented as cached properties for performance reasons.
        # The attrs will not exists if the cached property isn't
        # accessed yet, hence the try-excepts.
        try:
          del self.fields
        except AttributeError:
          pass
        try:
          del self.concreteFields
        except AttributeError:
          pass
        try:
          del self.localConcreteFields
        except AttributeError:
          pass

    if hasattr(self, '_nameMap'):
      del self._nameMap

  def addVirtualField(self, field):
    self.virtualFields.append(field)

  def setupPk(self, field):
    if not self.pk and field.primaryKey:
      self.pk = field
      field.serialize = False

  def pkIndex(self):
    """
    Returns the index of the primary key field in the self.concreteFields
    list.
    """
    return self.concreteFields.index(self.pk)

  def setupProxy(self, target):
    """
    Does the internal setup so that the current modal is a proxy for
    "target".
    """
    self.pk = target._meta.pk
    self.proxyForModel = target
    self.dbTable = target._meta.dbTable

  def __repr__(self):
    return '<Options for %s>' % self.objectName

  def __str__(self):
    return "%s.%s" % (smartText(self.appLabel), smartText(self.modelName))

  def verboseNameRaw(self):
    """
    There are a few places where the untranslated verbose name is needed
    (so that we get the same value regardless of currently active
    locale).
    """
    lang = getLanguage()
    deactivateAll()
    raw = forceText(self.verboseName)
    activate(lang)
    return raw
  verboseNameRaw = property(verboseNameRaw)

  def _swapped(self):
    """
    Has this modal been swapped out for another? If so, return the modal
    name of the replacement; otherwise, return None.

    For historical reasons, modal name lookups using getModel() are
    case insensitive, so we make sure we are case insensitive here.
    """
    if self.swappable:
      modalLabel = '%s.%s' % (self.appLabel, self.modelName)
      swappedFor = getattr(settings, self.swappable, None)
      if swappedFor:
        try:
          swappedLabel, swappedObject = swappedFor.split('.')
        except ValueError:
          # setting not in the format appLabel.modelName
          # raising ImproperlyConfigured here causes problems with
          # test cleanup code - instead it is raised in getUserModel
          # or as part of validation.
          return swappedFor

        if '%s.%s' % (swappedLabel, swappedObject.lower()) not in (None, modalLabel):
          return swappedFor
    return None
  swapped = property(_swapped)

  @cachedProperty
  def fields(self):
    """
    The getter for self.fields. This returns the list of field objects
    available to this modal (including through parent model).

    Callers are not permitted to modify this list, since it's a reference
    to this instance (not a copy).
    """
    try:
      self._fieldNameCache
    except AttributeError:
      self._fillFieldsCache()
    return self._fieldNameCache

  @cachedProperty
  def concreteFields(self):
    return [f for f in self.fields if f.column is not None]

  @cachedProperty
  def localConcreteFields(self):
    return [f for f in self.localFields if f.column is not None]

  def getFieldsWithModel(self):
    """
    Returns a sequence of (field, modal) pairs for all fields. The "modal"
    element is None for fields on the current modal. Mostly of use when
    constructing queries so that we know which modal a field belongs to.
    """
    try:
      self._fieldCache
    except AttributeError:
      self._fillFieldsCache()
    return self._fieldCache

  def getConcreteFieldsWithModel(self):
    return [(field, modal) for field, modal in self.getFieldsWithModel() if
        field.column is not None]

  def _fillFieldsCache(self):
    cache = []
    for parent in self.parents:
      for field, modal in parent._meta.getFieldsWithModel():
        if modal:
          cache.append((field, modal))
        else:
          cache.append((field, parent))
    cache.extend((f, None) for f in self.localFields)
    self._fieldCache = tuple(cache)
    self._fieldNameCache = [x for x, _ in cache]

  def _manyToMany(self):
    try:
      self._m2mCache
    except AttributeError:
      self._fillM2mCache()
    return list(self._m2mCache)
  manyToMany = property(_manyToMany)

  def getM2mWithModel(self):
    """
    The many-to-many version of getFieldsWithModel().
    """
    try:
      self._m2mCache
    except AttributeError:
      self._fillM2mCache()
    return list(six.iteritems(self._m2mCache))

  def _fillM2mCache(self):
    cache = OrderedDict()
    for parent in self.parents:
      for field, modal in parent._meta.getM2mWithModel():
        if modal:
          cache[field] = modal
        else:
          cache[field] = parent
    for field in self.localManyToMany:
      cache[field] = None
    self._m2mCache = cache

  def getField(self, name, manyToMany=True):
    """
    Returns the requested field by name. Raises FieldDoesNotExist on error.
    """
    toSearch = (self.fields + self.manyToMany) if manyToMany else self.fields
    for f in toSearch:
      if f.name == name:
        return f
    raise FieldDoesNotExist('%s has no field named %r' % (self.objectName, name))

  def getFieldByName(self, name):
    """
    Returns the (fieldObject, modal, direct, m2m), where fieldObject is
    the Field instance for the given name, modal is the modal containing
    this field (None for local fields), direct is True if the field exists
    on this modal, and m2m is True for many-to-many relations. When
    'direct' is False, 'fieldObject' is the corresponding RelatedObject
    for this field (since the field doesn't have an instance associated
    with it).

    Uses a cache internally, so after the first access, this is very fast.
    """
    try:
      try:
        return self._nameMap[name]
      except AttributeError:
        cache = self.initNameMap()
        return cache[name]
    except KeyError:
      raise FieldDoesNotExist('%s has no field named %r'
          % (self.objectName, name))

  def getAllFieldNames(self):
    """
    Returns a list of all field names that are possible for this modal
    (including reverse relation names). This is used for pretty printing
    debugging output (a list of choices), so any internal-only field names
    are not included.
    """
    try:
      cache = self._nameMap
    except AttributeError:
      cache = self.initNameMap()
    names = sorted(cache.keys())
    # Internal-only names end with "+" (symmetrical m2m related names being
    # the main example). Trim them.
    return [val for val in names if not val.endswith('+')]

  def initNameMap(self):
    """
    Initialises the field name -> field object mapping.
    """
    cache = {}
    # We intentionally handle related m2m objects first so that symmetrical
    # m2m accessor names can be overridden, if necessary.
    for f, modal in self.getAllRelatedM2mObjectsWithModel():
      cache[f.field.relatedQueryName()] = (f, modal, False, True)
    for f, modal in self.getAllRelatedObjectsWithModel():
      cache[f.field.relatedQueryName()] = (f, modal, False, False)
    for f, modal in self.getM2mWithModel():
      cache[f.name] = cache[f.attname] = (f, modal, True, True)
    for f, modal in self.getFieldsWithModel():
      cache[f.name] = cache[f.attname] = (f, modal, True, False)
    for f in self.virtualFields:
      if hasattr(f, 'related'):
        cache[f.name] = cache[f.attname] = (
          f, None if f.modal == self.modal else f.modal, True, False)
    if apps.ready:
      self._nameMap = cache
    return cache

  def getAddPermission(self):
    """
    This method has been deprecated in favor of
    `theory.contrib.auth.getPermissionCodename`. refs #20642
    """
    warnings.warn(
      "`Options.getAddPermission` has been deprecated in favor "
      "of `theory.contrib.auth.getPermissionCodename`.",
      RemovedInTheory20Warning, stacklevel=2)
    return 'add_%s' % self.modelName

  def getChangePermission(self):
    """
    This method has been deprecated in favor of
    `theory.contrib.auth.getPermissionCodename`. refs #20642
    """
    warnings.warn(
      "`Options.getChangePermission` has been deprecated in favor "
      "of `theory.contrib.auth.getPermissionCodename`.",
      RemovedInTheory20Warning, stacklevel=2)
    return 'change_%s' % self.modelName

  def getDeletePermission(self):
    """
    This method has been deprecated in favor of
    `theory.contrib.auth.getPermissionCodename`. refs #20642
    """
    warnings.warn(
      "`Options.getDeletePermission` has been deprecated in favor "
      "of `theory.contrib.auth.getPermissionCodename`.",
      RemovedInTheory20Warning, stacklevel=2)
    return 'delete_%s' % self.modelName

  def getAllRelatedObjects(self, localOnly=False, includeHidden=False,
                includeProxyEq=False):
    return [k for k, v in self.getAllRelatedObjectsWithModel(
        localOnly=localOnly, includeHidden=includeHidden,
        includeProxyEq=includeProxyEq)]

  def getAllRelatedObjectsWithModel(self, localOnly=False,
                      includeHidden=False,
                      includeProxyEq=False):
    """
    Returns a list of (related-object, modal) pairs. Similar to
    getFieldsWithModel().
    """
    try:
      self._relatedObjectsCache
    except AttributeError:
      self._fillRelatedObjectsCache()
    predicates = []
    if localOnly:
      predicates.append(lambda k, v: not v)
    if not includeHidden:
      predicates.append(lambda k, v: not k.field.rel.isHidden())
    cache = (self._relatedObjectsProxyCache if includeProxyEq
         else self._relatedObjectsCache)
    return [t for t in cache.items() if all(p(*t) for p in predicates)]

  def _fillRelatedObjectsCache(self):
    cache = OrderedDict()
    parentList = self.getParentList()
    for parent in self.parents:
      for obj, modal in parent._meta.getAllRelatedObjectsWithModel(includeHidden=True):
        if (obj.field.creationCounter < 0 or obj.field.rel.parentLink) and obj.modal not in parentList:
          continue
        if not modal:
          cache[obj] = parent
        else:
          cache[obj] = modal
    # Collect also objects which are in relation to some proxy child/parent of self.
    proxyCache = cache.copy()
    for klass in self.apps.getModels(includeAutoCreated=True):
      if not klass._meta.swapped:
        for f in klass._meta.localFields + klass._meta.virtualFields:
          if (hasattr(f, 'rel') and f.rel and not isinstance(f.rel.to, six.stringTypes)
              and f.generateReverseRelation):
            if self == f.rel.to._meta:
              cache[f.related] = None
              proxyCache[f.related] = None
            elif self.concreteModel == f.rel.to._meta.concreteModel:
              proxyCache[f.related] = None
    self._relatedObjectsCache = cache
    self._relatedObjectsProxyCache = proxyCache

  def getAllRelatedManyToManyObjects(self, localOnly=False):
    try:
      cache = self._relatedManyToManyCache
    except AttributeError:
      cache = self._fillRelatedManyToManyCache()
    if localOnly:
      return [k for k, v in cache.items() if not v]
    return list(cache)

  def getAllRelatedM2mObjectsWithModel(self):
    """
    Returns a list of (related-m2m-object, modal) pairs. Similar to
    getFieldsWithModel().
    """
    try:
      cache = self._relatedManyToManyCache
    except AttributeError:
      cache = self._fillRelatedManyToManyCache()
    return list(six.iteritems(cache))

  def _fillRelatedManyToManyCache(self):
    cache = OrderedDict()
    parentList = self.getParentList()
    for parent in self.parents:
      for obj, modal in parent._meta.getAllRelatedM2mObjectsWithModel():
        if obj.field.creationCounter < 0 and obj.modal not in parentList:
          continue
        if not modal:
          cache[obj] = parent
        else:
          cache[obj] = modal
    for klass in self.apps.getModels():
      if not klass._meta.swapped:
        for f in klass._meta.localManyToMany:
          if (f.rel
              and not isinstance(f.rel.to, six.stringTypes)
              and self == f.rel.to._meta):
            cache[f.related] = None
    if apps.ready:
      self._relatedManyToManyCache = cache
    return cache

  def getBaseChain(self, modal):
    """
    Returns a list of parent classes leading to 'modal' (order from closet
    to most distant ancestor). This has to handle the case were 'modal' is
    a grandparent or even more distant relation.
    """
    if not self.parents:
      return None
    if modal in self.parents:
      return [modal]
    for parent in self.parents:
      res = parent._meta.getBaseChain(modal)
      if res:
        res.insert(0, parent)
        return res
    return None

  def getParentList(self):
    """
    Returns a list of all the ancestor of this modal as a list. Useful for
    determining if something is an ancestor, regardless of lineage.
    """
    result = set()
    for parent in self.parents:
      result.add(parent)
      result.update(parent._meta.getParentList())
    return result

  def getAncestorLink(self, ancestor):
    """
    Returns the field on the current modal which points to the given
    "ancestor". This is possible an indirect link (a pointer to a parent
    modal, which points, eventually, to the ancestor). Used when
    constructing table joins for modal inheritance.

    Returns None if the modal isn't an ancestor of this one.
    """
    if ancestor in self.parents:
      return self.parents[ancestor]
    for parent in self.parents:
      # Tries to get a link field from the immediate parent
      parentLink = parent._meta.getAncestorLink(ancestor)
      if parentLink:
        # In case of a proxied modal, the first link
        # of the chain to the ancestor is that parent
        # links
        return self.parents[parent] or parentLink
