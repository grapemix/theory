from __future__ import with_statement

import warnings
from theory.conf import settings, UserSettingsHolder
# TODO: enable it
#from theory.test.signals import setting_changed
from theory.utils.translation import deactivate
from theory.utils.functional import wraps


__all__ = (
  'Approximate', 'ContextList',  'get_runner', 'override_settings',
  'setup_test_environment', 'teardown_test_environment',
)


class Approximate(object):
  def __init__(self, val, places=7):
    self.val = val
    self.places = places

  def __repr__(self):
    return repr(self.val)

  def __eq__(self, other):
    if self.val == other:
      return True
    return round(abs(self.val-other), self.places) == 0


class ContextList(list):
  """A wrapper that provides direct key access to context items contained
  in a list of context objects.
  """
  def __getitem__(self, key):
    if isinstance(key, basestring):
      for subcontext in self:
        if key in subcontext:
          return subcontext[key]
      raise KeyError(key)
    else:
      return super(ContextList, self).__getitem__(key)

  def __contains__(self, key):
    try:
      value = self[key]
    except KeyError:
      return False
    return True


def setup_test_environment():
  """Perform any global pre-test setup. This involves:

    - Installing the instrumented test renderer
    - Set the email backend to the locmem email backend.
    - Setting the active locale to match the LANGUAGE_CODE setting.
  """

  deactivate()


def teardown_test_environment():
  """Perform any global post-test teardown. This involves:

    - Restoring the original test renderer
    - Restoring the email sending functions

  """
  pass


def get_warnings_state():
  """
  Returns an object containing the state of the warnings module
  """
  # There is no public interface for doing this, but this implementation of
  # get_warnings_state and restore_warnings_state appears to work on Python
  # 2.4 to 2.7.
  return warnings.filters[:]


def restore_warnings_state(state):
  """
  Restores the state of the warnings module when passed an object that was
  returned by get_warnings_state()
  """
  warnings.filters = state[:]


def get_runner(settings, test_runner_class=None):
  if not test_runner_class:
    test_runner_class = settings.TEST_RUNNER

  test_path = test_runner_class.split('.')
  # Allow for Python 2.5 relative paths
  if len(test_path) > 1:
    test_module_name = '.'.join(test_path[:-1])
  else:
    test_module_name = '.'
  test_module = __import__(test_module_name, {}, {}, test_path[-1])
  test_runner = getattr(test_module, test_path[-1])
  return test_runner

class override_settings(object):
  """
  Acts as either a decorator, or a context manager. If it's a decorator it
  takes a function and returns a wrapped function. If it's a contextmanager
  it's used with the ``with`` statement. In either event entering/exiting
  are called before and after, respectively, the function/block is executed.
  """
  def __init__(self, **kwargs):
    self.options = kwargs
    self.wrapped = settings._wrapped

  def __enter__(self):
    self.enable()

  def __exit__(self, exc_type, exc_value, traceback):
    self.disable()

  def __call__(self, test_func):
    @wraps(test_func)
    def inner(*args, **kwargs):
      with self:
        return test_func(*args, **kwargs)
    return inner

  def enable(self):
    override = UserSettingsHolder(settings._wrapped)
    for key, new_value in self.options.items():
      setattr(override, key, new_value)
    settings._wrapped = override
    for key, new_value in self.options.items():
      setting_changed.send(sender=settings._wrapped.__class__,
                 setting=key, value=new_value)

  def disable(self):
    settings._wrapped = self.wrapped
    for key in self.options:
      new_value = getattr(settings, key, None)
      setting_changed.send(sender=settings._wrapped.__class__,
                 setting=key, value=new_value)

