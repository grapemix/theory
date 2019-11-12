from functools import wraps
import sys
import warnings

from theory.core.exceptions import ObjectDoesNotExist, ImproperlyConfigured  # NOQA
from theory.db.model.query import Q, QuerySet, Prefetch  # NOQA
from theory.db.model.expressions import F  # NOQA
from theory.db.model.manager import Manager  # NOQA
from theory.db.model.base import Model  # NOQA
from theory.db.model.aggregates import *  # NOQA
from theory.db.model.fields import *  # NOQA
from theory.db.model.fields.subclassing import SubfieldBase        # NOQA
from theory.db.model.fields.files import FileField, ImageField  # NOQA
from theory.db.model.fields.related import (  # NOQA
  ForeignKey, ForeignObject, OneToOneField, ManyToManyField,
  ManyToOneRel, ManyToManyRel, OneToOneRel)
from theory.db.model.fields.proxy import OrderWrt  # NOQA
from theory.db.model.deletion import (  # NOQA
  CASCADE, PROTECT, SET, SET_NULL, SET_DEFAULT, DO_NOTHING, ProtectedError)
from theory.db.model.lookups import Lookup, Transform  # NOQA
from theory.db.model import signals  # NOQA
from theory.utils.deprecation import RemovedInTheory19Warning

def permalink(func):
  """
  Decorator that calls urlresolvers.reverse() to return a URL using
  parameters returned by the decorated function "func".

  "func" should be a function that returns a tuple in one of the
  following formats:
    (viewname, viewargs)
    (viewname, viewargs, viewkwargs)
  """
  from theory.core.urlresolvers import reverse

  @wraps(func)
  def inner(*args, **kwargs):
    bits = func(*args, **kwargs)
    return reverse(bits[0], None, *bits[1:3])
  return inner


# Deprecated aliases for functions were exposed in this module.

def makeAlias(functionName):
  # Close functionName.
  def alias(*args, **kwargs):
    warnings.warn(
      "theory.db.model.%s is deprecated." % functionName,
      RemovedInTheory19Warning, stacklevel=2)
    # This raises a second warning.
    from . import loading
    return getattr(loading, functionName)(*args, **kwargs)
  alias.__name__ = functionName
  return alias

thisModule = sys.modules['theory.db.model']

for functionName in ('getApps', 'getAppPath', 'getAppPaths', 'getApp',
           'getModels', 'getModel', 'registerModels'):
  setattr(thisModule, functionName, makeAlias(functionName))

del thisModule, makeAlias, functionName
