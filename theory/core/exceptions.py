"""
Global Theory exception and warning classes.
"""
from functools import reduce
import operator

from theory.utils import six
from theory.utils.encoding import forceText


class TheoryRuntimeWarning(RuntimeWarning):
  pass


class AppRegistryNotReady(Exception):
  """The theory.apps registry is not populated yet"""
  pass


class ObjectDoesNotExist(Exception):
  """The requested object does not exist"""
  silentVariableFailure = True


class MultipleObjectsReturned(Exception):
  """The query returned multiple objects when only one was expected."""
  pass


class SuspiciousOperation(Exception):
  """The user did something suspicious"""


class SuspiciousMultipartForm(SuspiciousOperation):
  """Suspect MIME request in multipart form data"""
  pass


class SuspiciousFileOperation(SuspiciousOperation):
  """A Suspicious filesystem operation was attempted"""
  pass


class DisallowedHost(SuspiciousOperation):
  """HTTP_HOST header contains invalid value"""
  pass


class DisallowedRedirect(SuspiciousOperation):
  """Redirect to scheme not in allowed list"""
  pass


class PermissionDenied(Exception):
  """The user did not have permission to do that"""
  pass


class UIDoesNotExist(Exception):
  """The requested UI does not exist"""
  pass


class MiddlewareNotUsed(Exception):
  """This middleware is not used in this server configuration"""
  pass


class ImproperlyConfigured(Exception):
  """Theory is somehow improperly configured"""
  pass


class FieldError(Exception):
  """Some kind of problem with a model field."""
  pass


NON_FIELD_ERRORS = '__all__'


class ValidationError(Exception):
  """An error while validating data."""
  def __init__(self, message, code=None, params=None):
    """
    The `message` argument can be a single error, a list of errors, or a
    dictionary that maps field names to lists of errors. What we define as
    an "error" can be either a simple string or an instance of
    ValidationError with its message attribute set, and what we define as
    list or dictionary can be an actual `list` or `dict` or an instance
    of ValidationError with its `errorList` or `errorDict` attribute set.
    """

    # PY2 can't pickle naive exception: http://bugs.python.org/issue1692335.
    super(ValidationError, self).__init__(message, code, params)

    if isinstance(message, ValidationError):
      if hasattr(message, 'errorDict'):
        message = message.errorDict
      # PY2 has a `message` property which is always there so we can't
      # duck-type on it. It was introduced in Python 2.5 and already
      # deprecated in Python 2.6.
      elif not hasattr(message, 'message' if six.PY3 else 'code'):
        message = message.errorList
      else:
        message, code, params = message.message, message.code, message.params

    if isinstance(message, dict):
      self.errorDict = {}
      for field, messages in message.items():
        if not isinstance(messages, ValidationError):
          messages = ValidationError(messages)
        self.errorDict[field] = messages.errorList

    elif isinstance(message, list):
      self.errorList = []
      for message in message:
        # Normalize plain strings to instances of ValidationError.
        if not isinstance(message, ValidationError):
          message = ValidationError(message)
        self.errorList.extend(message.errorList)

    else:
      self.message = message
      self.code = code
      self.params = params
      self.errorList = [self]

  @property
  def messageDict(self):
    # Trigger an AttributeError if this ValidationError
    # doesn't have an errorDict.
    getattr(self, 'errorDict')

    return dict(self)

  @property
  def messages(self):
    if hasattr(self, 'errorDict'):
      return reduce(operator.add, dict(self).values())
    return list(self)

  def updateErrorDict(self, errorDict):
    if hasattr(self, 'errorDict'):
      for field, errorList in self.errorDict.items():
        errorDict.setdefault(field, []).extend(errorList)
    else:
      errorDict.setdefault(NON_FIELD_ERRORS, []).extend(self.errorList)
    return errorDict

  def __iter__(self):
    if hasattr(self, 'errorDict'):
      for field, errors in self.errorDict.items():
        yield field, list(ValidationError(errors))
    else:
      for error in self.errorList:
        message = error.message
        if error.params:
          message %= error.params
        yield forceText(message)

  def __str__(self):
    if hasattr(self, 'errorDict'):
      return repr(dict(self))
    return repr(list(self))

  def __repr__(self):
    return 'ValidationError(%s)' % self

class CommandDoesNotExist(Exception):
  """The requested command does not exist"""
  pass

class CommandSyntaxError(Exception):
  """The syntax of requested command has error"""
  pass

