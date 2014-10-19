# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from itertools import chain

from theory.utils.itercompat import isIterable


class Tags(object):
  """
  Built-in tags for internal checks.
  """
  admin = 'admin'
  compatibility = 'compatibility'
  models = 'models'
  signals = 'signals'


class CheckRegistry(object):

  def __init__(self):
    self.registeredChecks = []

  def register(self, *tags):
    """
    Decorator. Register given function `f` labeled with given `tags`. The
    function should receive **kwargs and return list of Errors and
    Warnings.

    Example::

      registry = CheckRegistry()
      @registry.register('mytag', 'anothertag')
      def myCheck(apps, **kwargs):
        # ... perform checks and collect `errors` ...
        return errors

    """

    def inner(check):
      check.tags = tags
      if check not in self.registeredChecks:
        self.registeredChecks.append(check)
      return check

    return inner

  def runChecks(self, appConfigs=None, tags=None):
    """ Run all registered checks and return list of Errors and Warnings.
    """
    errors = []
    if tags is not None:
      checks = [check for check in self.registeredChecks
           if hasattr(check, 'tags') and set(check.tags) & set(tags)]
    else:
      checks = self.registeredChecks

    for check in checks:
      newErrors = check(appConfigs=appConfigs)
      assert isIterable(newErrors), (
        "The function %r did not return a list. All functions registered "
        "with the checks registry must return a list." % check)
      errors.extend(newErrors)
    return errors

  def tagExists(self, tag):
    return tag in self.tagsAvailable()

  def tagsAvailable(self):
    return set(chain(*[check.tags for check in self.registeredChecks if hasattr(check, 'tags')]))


registry = CheckRegistry()
register = registry.register
runChecks = registry.runChecks
tagExists = registry.tagExists
