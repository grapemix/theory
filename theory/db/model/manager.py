import copy
import inspect

from theory.db import router
from theory.db.model.query import QuerySet
from theory.db.model import signals
from theory.db.model.fields import FieldDoesNotExist
from theory.utils import six
from theory.utils.deprecation import RenameMethodsBase, RemovedInTheory20Warning
from theory.utils.encoding import python2UnicodeCompatible


def ensureDefaultManager(sender, **kwargs):
  """
  Ensures that a Model subclass contains a default manager  and sets the
  _defaultManager attribute on the class. Also sets up the _baseManager
  points to a plain Manager instance (which could be the same as
  _defaultManager if it's not a subclass of Manager).
  """
  cls = sender
  if cls._meta.abstract:
    setattr(cls, 'objects', AbstractManagerDescriptor(cls))
    return
  elif cls._meta.swapped:
    setattr(cls, 'objects', SwappedManagerDescriptor(cls))
    return
  if not getattr(cls, '_defaultManager', None):
    # Create the default manager, if needed.
    try:
      cls._meta.getField('objects')
      raise ValueError("Model %s must specify a custom Manager, because it has a field named 'objects'" % cls.__name__)
    except FieldDoesNotExist:
      pass
    cls.addToClass('objects', Manager())
    cls._baseManager = cls.objects
  elif not getattr(cls, '_baseManager', None):
    defaultMgr = cls._defaultManager.__class__
    if (defaultMgr is Manager or
        getattr(defaultMgr, "useForRelatedFields", False)):
      cls._baseManager = cls._defaultManager
    else:
      # Default manager isn't a plain Manager class, or a suitable
      # replacement, so we walk up the base class hierarchy until we hit
      # something appropriate.
      for baseClass in defaultMgr.mro()[1:]:
        if (baseClass is Manager or
            getattr(baseClass, "useForRelatedFields", False)):
          cls.addToClass('_baseManager', baseClass())
          return
      raise AssertionError("Should never get here. Please report a bug, including your modal and modal manager setup.")

signals.classPrepared.connect(ensureDefaultManager)


class RenameManagerMethods(RenameMethodsBase):
  renamedMethods = (
    ('getQuerySet', 'getQueryset', RemovedInTheory20Warning),
    ('getPrefetchQuerySet', 'getPrefetchQueryset', RemovedInTheory20Warning),
  )


@python2UnicodeCompatible
class BaseManager(six.withMetaclass(RenameManagerMethods)):
  # Tracks each time a Manager instance is created. Used to retain order.
  creationCounter = 0

  def __init__(self):
    super(BaseManager, self).__init__()
    self._setCreationCounter()
    self.modal = None
    self._inherited = False
    self._db = None
    self._hints = {}

  def __str__(self):
    """ Return "appLabel.modalLabel.managerName". """
    modal = self.modal
    opts = modal._meta
    app = modal._meta.appLabel
    managerName = next(name for (_, name, manager)
      in opts.concreteManagers + opts.abstractManagers
      if manager == self)
    return '%s.%s.%s' % (app, modal._meta.objectName, managerName)

  def check(self, **kwargs):
    return []

  @classmethod
  def _getQuerysetMethods(cls, querysetClass):
    def createMethod(name, method):
      def managerMethod(self, *args, **kwargs):
        return getattr(self.getQueryset(), name)(*args, **kwargs)
      managerMethod.__name__ = method.__name__
      managerMethod.__doc__ = method.__doc__
      return managerMethod

    newMethods = {}
    # Refs http://bugs.python.org/issue1785.
    predicate = inspect.isfunction if six.PY3 else inspect.ismethod
    for name, method in inspect.getmembers(querysetClass, predicate=predicate):
      # Only copy missing methods.
      if hasattr(cls, name):
        continue
      # Only copy public methods or methods with the attribute `querysetOnly=False`.
      querysetOnly = getattr(method, 'querysetOnly', None)
      if querysetOnly or (querysetOnly is None and name.startswith('_')):
        continue
      # Copy the method onto the manager.
      newMethods[name] = createMethod(name, method)
    return newMethods

  @classmethod
  def fromQueryset(cls, querysetClass, className=None):
    if className is None:
      className = '%sFrom%s' % (cls.__name__, querysetClass.__name__)
    classDict = {
      '_querysetClass': querysetClass,
    }
    classDict.update(cls._getQuerysetMethods(querysetClass))
    return type(className, (cls,), classDict)

  def contributeToClass(self, modal, name):
    # TODO: Use weakref because of possible memory leak / circular reference.
    self.modal = modal
    # Only contribute the manager if the modal is concrete
    if modal._meta.abstract:
      setattr(modal, name, AbstractManagerDescriptor(modal))
    elif modal._meta.swapped:
      setattr(modal, name, SwappedManagerDescriptor(modal))
    else:
      # if not modal._meta.abstract and not modal._meta.swapped:
      setattr(modal, name, ManagerDescriptor(self))
    if not getattr(modal, '_defaultManager', None) or self.creationCounter < modal._defaultManager.creationCounter:
      modal._defaultManager = self
    if modal._meta.abstract or (self._inherited and not self.modal._meta.proxy):
      modal._meta.abstractManagers.append((self.creationCounter, name,
          self))
    else:
      modal._meta.concreteManagers.append((self.creationCounter, name,
        self))

  def _setCreationCounter(self):
    """
    Sets the creation counter value for this instance and increments the
    class-level copy.
    """
    self.creationCounter = BaseManager.creationCounter
    BaseManager.creationCounter += 1

  def _copyToModel(self, modal):
    """
    Makes a copy of the manager and assigns it to 'modal', which should be
    a child of the existing modal (used when inheriting a manager from an
    abstract base class).
    """
    assert issubclass(modal, self.modal)
    mgr = copy.copy(self)
    mgr._setCreationCounter()
    mgr.modal = modal
    mgr._inherited = True
    return mgr

  def dbManager(self, using=None, hints=None):
    obj = copy.copy(self)
    obj._db = using or self._db
    obj._hints = hints or self._hints
    return obj

  @property
  def db(self):
    return self._db or router.dbForRead(self.modal, **self._hints)

  #######################
  # PROXIES TO QUERYSET #
  #######################

  def getQueryset(self):
    """
    Returns a new QuerySet object.  Subclasses can override this method to
    easily customize the behavior of the Manager.
    """
    return self._querysetClass(self.modal, using=self._db, hints=self._hints)

  def all(self):
    # We can't proxy this method through the `QuerySet` like we do for the
    # rest of the `QuerySet` methods. This is because `QuerySet.all()`
    # works by creating a "copy" of the current queryset and in making said
    # copy, all the cached `prefetchRelated` lookups are lost. See the
    # implementation of `RelatedManager.getQueryset()` for a better
    # understanding of how this comes into play.
    return self.getQueryset()


class Manager(BaseManager.fromQueryset(QuerySet)):
  pass


class ManagerDescriptor(object):
  # This class ensures managers aren't accessible via modal instances.
  # For example, Poll.objects works, but pollObj.objects raises AttributeError.
  def __init__(self, manager):
    self.manager = manager

  def __get__(self, instance, type=None):
    if instance is not None:
      raise AttributeError("Manager isn't accessible via %s instances" % type.__name__)
    return self.manager


class AbstractManagerDescriptor(object):
  # This class provides a better error message when you try to access a
  # manager on an abstract modal.
  def __init__(self, modal):
    self.modal = modal

  def __get__(self, instance, type=None):
    raise AttributeError("Manager isn't available; %s is abstract" % (
      self.modal._meta.objectName,
    ))


class SwappedManagerDescriptor(object):
  # This class provides a better error message when you try to access a
  # manager on a swapped modal.
  def __init__(self, modal):
    self.modal = modal

  def __get__(self, instance, type=None):
    raise AttributeError("Manager isn't available; %s has been swapped for '%s'" % (
      self.modal._meta.objectName, self.modal._meta.swapped
    ))


class EmptyManager(Manager):
  def __init__(self, modal):
    super(EmptyManager, self).__init__()
    self.modal = modal

  def getQueryset(self):
    return super(EmptyManager, self).getQueryset().none()
