from __future__ import unicode_literals

from copy import copy
import difflib
import errno
from functools import wraps
import json
import os
import posixpath
import re
import socket
import sys
import threading
import unittest
import warnings
from unittest import skipIf         # NOQA: Imported here for backward compatibility
from unittest.util import safe_repr

from theory.conf import settings
from theory.core.exceptions import ValidationError, ImproperlyConfigured
from theory.gui.common.baseField import TextField
from theory.test.util import (overrideSettings, modifySettings, compareXml)
from theory.utils.deprecation import RemovedInTheory20Warning
from theory.utils.encoding import forceText
from theory.utils import six
from theory.utils.six.moves.urllib.parse import urlsplit, urlunsplit, urlparse, unquote
from theory.utils.six.moves.urllib.request import url2pathname

__all__ = ('TestCase', 'SimpleTestCase', )



def toList(value):
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


class SimpleTestCase(unittest.TestCase):

  _modifiedSettings = None

  def __call__(self, result=None):
    """
    Wrapper around default __call__ method to perform common Theory test
    set up. This means that user-defined Test Cases aren't required to
    include a call to super().setUp().
    """
    testMethod = getattr(self, self._testMethodName)
    skipped = (getattr(self.__class__, "__unittestSkip__", False) or
      getattr(testMethod, "__unittestSkip__", False))

    if not skipped:
      try:
        self._preSetup()
      except Exception:
        result.addError(self, sys.excInfo())
        return
    super(SimpleTestCase, self).__call__(result)
    if not skipped:
      try:
        self._postTeardown()
      except Exception:
        result.addError(self, sys.excInfo())
        return

  def _preSetup(self):
    """Performs any pre-test setup. This includes:
    """
    pass

  def _postTeardown(self):
    """Performs any post-test things. This includes:

    * Putting back the original ROOT_URLCONF if it was changed.
    """
    pass

  def settings(self, **kwargs):
    """
    A context manager that temporarily sets a setting and reverts to the original value when exiting the context.
    """
    return overrideSettings(**kwargs)

  def modifySettings(self, **kwargs):
    """
    A context manager that temporarily applies changes a list setting and
    reverts back to the original value when exiting the context.
    """
    return modifySettings(**kwargs)

  def _assertContains(self, response, text, statusCode, msgPrefix, html):
    # If the response supports deferred rendering and hasn't been rendered
    # yet, then ensure that it does get rendered before proceeding further.
    if (hasattr(response, 'render') and callable(response.render)
        and not response.isRendered):
      response.render()

    if msgPrefix:
      msgPrefix += ": "

    self.assertEqual(response.statusCode, statusCode,
      msgPrefix + "Couldn't retrieve content: Response code was %d"
      " (expected %d)" % (response.statusCode, statusCode))

    if response.streaming:
      content = b''.join(response.streamingContent)
    else:
      content = response.content
    if not isinstance(text, bytes) or html:
      text = forceText(text, encoding=response._charset)
      content = content.decode(response._charset)
      textRepr = "'%s'" % text
    else:
      textRepr = repr(text)
    if html:
      content = assertAndParseHtml(self, content, None,
        "Response's content is not valid HTML:")
      text = assertAndParseHtml(self, text, None,
        "Second argument is not valid HTML:")
    realCount = content.count(text)
    return (textRepr, realCount, msgPrefix)

  def assertContains(self, response, text, count=None, statusCode=200,
            msgPrefix='', html=False):
    """
    Asserts that a response indicates that some content was retrieved
    successfully, (i.e., the HTTP status code was as expected), and that
    ``text`` occurs ``count`` times in the content of the response.
    If ``count`` is None, the count doesn't matter - the assertion is true
    if the text occurs at least once in the response.
    """
    textRepr, realCount, msgPrefix = self._assertContains(
      response, text, statusCode, msgPrefix, html)

    if count is not None:
      self.assertEqual(realCount, count,
        msgPrefix + "Found %d instances of %s in response"
        " (expected %d)" % (realCount, textRepr, count))
    else:
      self.assertTrue(realCount != 0,
        msgPrefix + "Couldn't find %s in response" % textRepr)

  def assertNotContains(self, response, text, statusCode=200,
             msgPrefix='', html=False):
    """
    Asserts that a response indicates that some content was retrieved
    successfully, (i.e., the HTTP status code was as expected), and that
    ``text`` doesn't occurs in the content of the response.
    """
    textRepr, realCount, msgPrefix = self._assertContains(
      response, text, statusCode, msgPrefix, html)

    self.assertEqual(realCount, 0,
        msgPrefix + "Response should not contain %s" % textRepr)

  def assertRaisesMessage(self, expectedException, expectedMessage,
              callableObj=None, *args, **kwargs):
    """
    Asserts that the message in a raised exception matches the passed
    value.

    Args:
      expectedException: Exception class expected to be raised.
      expectedMessage: expected error message string value.
      callableObj: Function to be called.
      args: Extra args.
      kwargs: Extra kwargs.
    """
    return six.assertRaisesRegex(self, expectedException,
        re.escape(expectedMessage), callableObj, *args, **kwargs)

  def assertFieldOutput(self, fieldclass, valid, invalid, fieldArgs=None,
      fieldKwargs=None, emptyValue=''):
    """
    Asserts that a form field behaves correctly with various inputs.

    Args:
      fieldclass: the class of the field to be tested.
      valid: a dictionary mapping valid inputs to their expected
          cleaned values.
      invalid: a dictionary mapping invalid inputs to one or more
          raised error messages.
      fieldArgs: the args passed to instantiate the field
      fieldKwargs: the kwargs passed to instantiate the field
      emptyValue: the expected clean output for inputs in emptyValues

    """
    if fieldArgs is None:
      fieldArgs = []
    if fieldKwargs is None:
      fieldKwargs = {}
    required = fieldclass(*fieldArgs, **fieldKwargs)
    optional = fieldclass(*fieldArgs,
               **dict(fieldKwargs, required=False))
    # test valid inputs
    for input, output in valid.items():
      self.assertEqual(required.clean(input), output)
      self.assertEqual(optional.clean(input), output)
    # test invalid inputs
    for input, errors in invalid.items():
      with self.assertRaises(ValidationError) as contextManager:
        required.clean(input)
      self.assertEqual(contextManager.exception.messages, errors)

      with self.assertRaises(ValidationError) as contextManager:
        optional.clean(input)
      self.assertEqual(contextManager.exception.messages, errors)
    # test required inputs
    errorRequired = [forceText(required.errorMessages['required'])]
    for e in required.emptyValues:
      with self.assertRaises(ValidationError) as contextManager:
        required.clean(e)
      self.assertEqual(contextManager.exception.messages,
               errorRequired)
      self.assertEqual(optional.clean(e), emptyValue)
    # test that maxLength and minLength are always accepted
    if issubclass(fieldclass, TextField):
      fieldKwargs.update({'minLength': 2, 'maxLength': 20})
      self.assertIsInstance(fieldclass(*fieldArgs, **fieldKwargs),
                 fieldclass)

  def assertJSONEqual(self, raw, expectedData, msg=None):
    """
    Asserts that the JSON fragments raw and expectedData are equal.
    Usual JSON non-significant whitespace rules apply as the heavyweight
    is delegated to the json library.
    """
    try:
      data = json.loads(raw)
    except ValueError:
      self.fail("First argument is not valid JSON: %r" % raw)
    if isinstance(expectedData, six.stringTypes):
      try:
        expectedData = json.loads(expectedData)
      except ValueError:
        self.fail("Second argument is not valid JSON: %r" % expectedData)
    self.assertEqual(data, expectedData, msg=msg)

  def assertJSONNotEqual(self, raw, expectedData, msg=None):
    """
    Asserts that the JSON fragments raw and expectedData are not equal.
    Usual JSON non-significant whitespace rules apply as the heavyweight
    is delegated to the json library.
    """
    try:
      data = json.loads(raw)
    except ValueError:
      self.fail("First argument is not valid JSON: %r" % raw)
    if isinstance(expectedData, six.stringTypes):
      try:
        expectedData = json.loads(expectedData)
      except ValueError:
        self.fail("Second argument is not valid JSON: %r" % expectedData)
    self.assertNotEqual(data, expectedData, msg=msg)

  def assertXMLEqual(self, xml1, xml2, msg=None):
    """
    Asserts that two XML snippets are semantically the same.
    Whitespace in most cases is ignored, and attribute ordering is not
    significant. The passed-in arguments must be valid XML.
    """
    try:
      result = compareXml(xml1, xml2)
    except Exception as e:
      standardMsg = 'First or second argument is not valid XML\n%s' % e
      self.fail(self._formatMessage(msg, standardMsg))
    else:
      if not result:
        standardMsg = '%s != %s' % (safeRepr(xml1, True), safeRepr(xml2, True))
        self.fail(self._formatMessage(msg, standardMsg))

  def assertXMLNotEqual(self, xml1, xml2, msg=None):
    """
    Asserts that two XML snippets are not semantically equivalent.
    Whitespace in most cases is ignored, and attribute ordering is not
    significant. The passed-in arguments must be valid XML.
    """
    try:
      result = compareXml(xml1, xml2)
    except Exception as e:
      standardMsg = 'First or second argument is not valid XML\n%s' % e
      self.fail(self._formatMessage(msg, standardMsg))
    else:
      if result:
        standardMsg = '%s == %s' % (safeRepr(xml1, True), safeRepr(xml2, True))
        self.fail(self._formatMessage(msg, standardMsg))


class TestCase(SimpleTestCase):
  """
  Does basically the same as TransactionTestCase, but surrounds every test
  with a transaction, monkey-patches the real transaction management routines
  to do nothing, and rollsback the test transaction at the end of the test.
  You have to use TransactionTestCase, if you need transaction management
  inside a test.
  """

  def _fixtureSetup(self):
    return super(TestCase, self)._fixtureSetup()

  def _fixtureTeardown(self):
    return super(TestCase, self)._fixtureTeardown()

class CheckCondition(object):
  """Descriptor class for deferred condition checking"""
  def __init__(self, condFunc):
    self.condFunc = condFunc

  def __get__(self, obj, objtype):
    return self.condFunc()


def _deferredSkip(condition, reason):
  def decorator(testFunc):
    if not (isinstance(testFunc, type) and
        issubclass(testFunc, unittest.TestCase)):
      @wraps(testFunc)
      def skipWrapper(*args, **kwargs):
        if condition():
          raise unittest.SkipTest(reason)
        return testFunc(*args, **kwargs)
      testItem = skipWrapper
    else:
      # Assume a class is decorated
      testItem = testFunc
      testItem.__unittestSkip__ = CheckCondition(condition)
    testItem.__unittestSkipWhy__ = reason
    return testItem
  return decorator
