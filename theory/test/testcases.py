# -*- coding: utf-8 -*-
#!/usr/bin/env python
from __future__ import with_statement

import difflib
import re
from functools import wraps

from theory.conf import settings
from theory.core.exceptions import ValidationError
#from theory.core.management import call_command
# TODO: enable it
#from theory.core.signals import request_started
from theory.core.validators import EMPTY_VALUES
from theory.test.utils import (get_warnings_state, restore_warnings_state,
  override_settings)
from theory.test.utils import ContextList
from theory.utils import simplejson, unittest as ut2
from theory.utils.encoding import smart_str, force_unicode
from theory.utils.unittest.util import safe_repr

__all__ = ('TestCase', 'SimpleTestCase', )

normalize_long_ints = lambda s: re.sub(r'(?<![\w])(\d+)L(?![\w])', '\\1', s)
normalize_decimals = lambda s: re.sub(r"Decimal\('(\d+(\.\d*)?)'\)",
                lambda m: "Decimal(\"%s\")" % m.groups()[0], s)

def to_list(value):
  """
  Puts value into a list if it's not already one.
  Returns an empty list if value is None.
  """
  if value is None:
    value = []
  elif not isinstance(value, list):
    value = [value]
  return value

def nop(*args, **kwargs):
  return

class SimpleTestCase(ut2.TestCase):
  def save_warnings_state(self):
    """
    Saves the state of the warnings module
    """
    self._warnings_state = get_warnings_state()

  def restore_warnings_state(self):
    """
    Restores the state of the warnings module to the state
    saved by save_warnings_state()
    """
    restore_warnings_state(self._warnings_state)

  def settings(self, **kwargs):
    """
    A context manager that temporarily sets a setting and reverts
    back to the original value when exiting the context.
    """
    return override_settings(**kwargs)

  def assertRaisesMessage(self, expected_exception, expected_message,
              callable_obj=None, *args, **kwargs):
    """
    Asserts that the message in a raised exception matches the passed
    value.

    Args:
      expected_exception: Exception class expected to be raised.
      expected_message: expected error message string value.
      callable_obj: Function to be called.
      args: Extra args.
      kwargs: Extra kwargs.
    """
    return self.assertRaisesRegexp(expected_exception,
        re.escape(expected_message), callable_obj, *args, **kwargs)

  def assertFieldOutput(self, fieldclass, valid, invalid, field_args=None,
      field_kwargs=None, empty_value=u''):
    """
    Asserts that a form field behaves correctly with various inputs.

    Args:
      fieldclass: the class of the field to be tested.
      valid: a dictionary mapping valid inputs to their expected
          cleaned values.
      invalid: a dictionary mapping invalid inputs to one or more
          raised error messages.
      field_args: the args passed to instantiate the field
      field_kwargs: the kwargs passed to instantiate the field
      empty_value: the expected clean output for inputs in EMPTY_VALUES

    """
    if field_args is None:
      field_args = []
    if field_kwargs is None:
      field_kwargs = {}
    required = fieldclass(*field_args, **field_kwargs)
    optional = fieldclass(*field_args,
               **dict(field_kwargs, required=False))
    # test valid inputs
    for input, output in valid.items():
      self.assertEqual(required.clean(input), output)
      self.assertEqual(optional.clean(input), output)
    # test invalid inputs
    for input, errors in invalid.items():
      with self.assertRaises(ValidationError) as context_manager:
        required.clean(input)
      self.assertEqual(context_manager.exception.messages, errors)

      with self.assertRaises(ValidationError) as context_manager:
        optional.clean(input)
      self.assertEqual(context_manager.exception.messages, errors)
    # test required inputs
    error_required = [force_unicode(required.error_messages['required'])]
    for e in EMPTY_VALUES:
      with self.assertRaises(ValidationError) as context_manager:
        required.clean(e)
      self.assertEqual(context_manager.exception.messages,
               error_required)
      self.assertEqual(optional.clean(e), empty_value)

class TestCase(SimpleTestCase):
  """
  Does basically the same as TransactionTestCase, but surrounds every test
  with a transaction, monkey-patches the real transaction management routines
  to do nothing, and rollsback the test transaction at the end of the test.
  You have to use TransactionTestCase, if you need transaction management
  inside a test.
  """

  def _fixture_setup(self):
    return super(TestCase, self)._fixture_setup()

  def _fixture_teardown(self):
    return super(TestCase, self)._fixture_setup()


def _deferredSkip(condition, reason):
  def decorator(test_func):
    if not (isinstance(test_func, type) and
        issubclass(test_func, TestCase)):
      @wraps(test_func)
      def skip_wrapper(*args, **kwargs):
        if condition():
          raise ut2.SkipTest(reason)
        return test_func(*args, **kwargs)
      test_item = skip_wrapper
    else:
      test_item = test_func
    test_item.__unittest_skip_why__ = reason
    return test_item
  return decorator
