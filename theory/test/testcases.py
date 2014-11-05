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

from theory.apps import apps
from theory.apps.command.flush import Flush
from theory.apps.command.loaddata import Loaddata
from theory.conf import settings
from theory.core.bridge import Bridge
from theory.core.exceptions import ValidationError, ImproperlyConfigured
from theory.db import connection, connections, DEFAULT_DB_ALIAS, transaction
from theory.gui.common.baseField import TextField
from theory.gui.color import noStyle
from theory.test.signals import settingChanged, templateRendered
from theory.test.util import (CaptureQueriesContext, ContextList,
  overrideSettings, modifySettings, compareXml)
from theory.utils.deprecation import RemovedInTheory20Warning
from theory.utils.encoding import forceText
from theory.utils import six
from theory.utils.six.moves.urllib.parse import urlsplit, urlunsplit, urlparse, unquote
from theory.utils.six.moves.urllib.request import url2pathname

__all__ = ('TestCase', 'TransactionTestCase',
      'SimpleTestCase', 'skipIfDBFeature', 'skipUnlessDBFeature')


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

realCommit = transaction.commit
realRollback = transaction.rollback


def nop(*args, **kwargs):
  return


def disableTransactionMethods():
  transaction.commit = nop
  transaction.rollback = nop


def restoreTransactionMethods():
  transaction.commit = realCommit
  transaction.rollback = realRollback


class _AssertNumQueriesContext(CaptureQueriesContext):
  def __init__(self, testCase, num, connection):
    self.testCase = testCase
    self.num = num
    super(_AssertNumQueriesContext, self).__init__(connection)

  def __exit__(self, excType, excValue, traceback):
    super(_AssertNumQueriesContext, self).__exit__(excType, excValue, traceback)
    if excType is not None:
      return
    executed = len(self)
    self.testCase.assertEqual(
      executed, self.num,
      "%d queries executed, %d expected\nCaptured queries were:\n%s" % (
        executed, self.num,
        '\n'.join(
          query['sql'] for query in self.capturedQueries
        )
      )
    )


class _AssertTemplateUsedContext(object):
  def __init__(self, testCase, templateName):
    self.testCase = testCase
    self.templateName = templateName
    self.renderedTemplates = []
    self.renderedTemplateNames = []
    self.context = ContextList()

  def onTemplateRender(self, sender, signal, template, context, **kwargs):
    self.renderedTemplates.append(template)
    self.renderedTemplateNames.append(template.name)
    self.context.append(copy(context))

  def test(self):
    return self.templateName in self.renderedTemplateNames

  def message(self):
    return '%s was not rendered.' % self.templateName

  def __enter__(self):
    templateRendered.connect(self.onTemplateRender)
    return self

  def __exit__(self, excType, excValue, traceback):
    templateRendered.disconnect(self.onTemplateRender)
    if excType is not None:
      return

    if not self.test():
      message = self.message()
      if len(self.renderedTemplates) == 0:
        message += ' No template was rendered.'
      else:
        message += ' Following templates were rendered: %s' % (
          ', '.join(self.renderedTemplateNames))
      self.testCase.fail(message)


class _AssertTemplateNotUsedContext(_AssertTemplateUsedContext):
  def test(self):
    return self.templateName not in self.renderedTemplateNames

  def message(self):
    return '%s was rendered.' % self.templateName


class SimpleTestCase(unittest.TestCase):

  # Can be overridden in derived classes.
  _overriddenSettings = None
  _modifiedSettings = None

  def __call__(self, result=None):
    """
    Wrapper around default __call__ method to perform common Theory test
    set up. This means that user-defined Test Cases aren't required to
    include a call to super().setUp().
    """
    self.bridge = Bridge()
    testMethod = getattr(self, self._testMethodName)
    skipped = (getattr(self.__class__, "__unittestSkip__", False) or
      getattr(testMethod, "__unittestSkip__", False))

    if not skipped:
      try:
        self._preSetup()
      except Exception:
        result.addError(self, sys.exc_info())
        return
    super(SimpleTestCase, self).__call__(result)
    if not skipped:
      try:
        self._postTeardown()
      except Exception:
        result.addError(self, sys.exc_info())
        return

  def _preSetup(self):
    """Performs any pre-test setup. This includes:

    * If the class has a 'urls' attribute, replace ROOT_URLCONF with it.
    """
    if self._overriddenSettings:
      self._overriddenContext = overrideSettings(**self._overriddenSettings)
      self._overriddenContext.enable()
    if self._modifiedSettings:
      self._modifiedContext = modifySettings(self._modifiedSettings)
      self._modifiedContext.enable()

  def _postTeardown(self):
    """Performs any post-test things. This includes:

    * Putting back the original ROOT_URLCONF if it was changed.
    """
    if self._modifiedSettings:
      self._modifiedContext.disable()
    if self._overriddenSettings:
      self._overriddenContext.disable()

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

  def assertFormError(self, response, form, field, errors, msgPrefix=''):
    """
    Asserts that a form used to render the response has a specific field
    error.
    """
    if msgPrefix:
      msgPrefix += ": "

    # Put context(s) into a list to simplify processing.
    contexts = toList(response.context)
    if not contexts:
      self.fail(msgPrefix + "Response did not use any contexts to "
           "render the response")

    # Put error(s) into a list to simplify processing.
    errors = toList(errors)

    # Search all contexts for the error.
    foundForm = False
    for i, context in enumerate(contexts):
      if form not in context:
        continue
      foundForm = True
      for err in errors:
        if field:
          if field in context[form].errors:
            fieldErrors = context[form].errors[field]
            self.assertTrue(err in fieldErrors,
              msgPrefix + "The field '%s' on form '%s' in"
              " context %d does not contain the error '%s'"
              " (actual errors: %s)" %
              (field, form, i, err, repr(fieldErrors)))
          elif field in context[form].fields:
            self.fail(msgPrefix + "The field '%s' on form '%s'"
                 " in context %d contains no errors" %
                 (field, form, i))
          else:
            self.fail(msgPrefix + "The form '%s' in context %d"
                 " does not contain the field '%s'" %
                 (form, i, field))
        else:
          nonFieldErrors = context[form].nonFieldErrors()
          self.assertTrue(err in nonFieldErrors,
            msgPrefix + "The form '%s' in context %d does not"
            " contain the non-field error '%s'"
            " (actual errors: %s)" %
              (form, i, err, nonFieldErrors))
    if not foundForm:
      self.fail(msgPrefix + "The form '%s' was not used to render the"
           " response" % form)

  def assertFormsetError(self, response, formset, formIndex, field, errors,
              msgPrefix=''):
    """
    Asserts that a formset used to render the response has a specific error.

    For field errors, specify the ``formIndex`` and the ``field``.
    For non-field errors, specify the ``formIndex`` and the ``field`` as
    None.
    For non-form errors, specify ``formIndex`` as None and the ``field``
    as None.
    """
    # Add punctuation to msgPrefix
    if msgPrefix:
      msgPrefix += ": "

    # Put context(s) into a list to simplify processing.
    contexts = toList(response.context)
    if not contexts:
      self.fail(msgPrefix + 'Response did not use any contexts to '
           'render the response')

    # Put error(s) into a list to simplify processing.
    errors = toList(errors)

    # Search all contexts for the error.
    foundFormset = False
    for i, context in enumerate(contexts):
      if formset not in context:
        continue
      foundFormset = True
      for err in errors:
        if field is not None:
          if field in context[formset].forms[formIndex].errors:
            fieldErrors = context[formset].forms[formIndex].errors[field]
            self.assertTrue(err in fieldErrors,
                msgPrefix + "The field '%s' on formset '%s', "
                "form %d in context %d does not contain the "
                "error '%s' (actual errors: %s)" %
                (field, formset, formIndex, i, err,
                 repr(fieldErrors)))
          elif field in context[formset].forms[formIndex].fields:
            self.fail(msgPrefix + "The field '%s' "
                 "on formset '%s', form %d in "
                 "context %d contains no errors" %
                 (field, formset, formIndex, i))
          else:
            self.fail(msgPrefix + "The formset '%s', form %d in "
                 "context %d does not contain the field '%s'" %
                 (formset, formIndex, i, field))
        elif formIndex is not None:
          nonFieldErrors = context[formset].forms[formIndex].nonFieldErrors()
          self.assertFalse(len(nonFieldErrors) == 0,
                   msgPrefix + "The formset '%s', form %d in "
                   "context %d does not contain any non-field "
                   "errors." % (formset, formIndex, i))
          self.assertTrue(err in nonFieldErrors,
                  msgPrefix + "The formset '%s', form %d "
                  "in context %d does not contain the "
                  "non-field error '%s' "
                  "(actual errors: %s)" %
                  (formset, formIndex, i, err,
                   repr(nonFieldErrors)))
        else:
          nonFormErrors = context[formset].nonFormErrors()
          self.assertFalse(len(nonFormErrors) == 0,
                   msgPrefix + "The formset '%s' in "
                   "context %d does not contain any "
                   "non-form errors." % (formset, i))
          self.assertTrue(err in nonFormErrors,
                  msgPrefix + "The formset '%s' in context "
                  "%d does not contain the "
                  "non-form error '%s' (actual errors: %s)" %
                  (formset, i, err, repr(nonFormErrors)))
    if not foundFormset:
      self.fail(msgPrefix + "The formset '%s' was not used to render "
           "the response" % formset)

  def _assertTemplateUsed(self, response, templateName, msgPrefix):

    if response is None and templateName is None:
      raise TypeError('response and/or templateName argument must be provided')

    if msgPrefix:
      msgPrefix += ": "

    if not hasattr(response, 'templates') or (response is None and templateName):
      if response:
        templateName = response
        response = None
      # use this template with context manager
      return templateName, None, msgPrefix

    templateNames = [t.name for t in response.templates if t.name is not
             None]
    return None, templateNames, msgPrefix

  def assertTemplateUsed(self, response=None, templateName=None, msgPrefix='', count=None):
    """
    Asserts that the template with the provided name was used in rendering
    the response. Also usable as context manager.
    """
    contextMgrTemplate, templateNames, msgPrefix = self._assertTemplateUsed(
      response, templateName, msgPrefix)

    if contextMgrTemplate:
      # Use assertTemplateUsed as context manager.
      return _AssertTemplateUsedContext(self, contextMgrTemplate)

    if not templateNames:
      self.fail(msgPrefix + "No templates used to render the response")
    self.assertTrue(templateName in templateNames,
      msgPrefix + "Template '%s' was not a template used to render"
      " the response. Actual template(s) used: %s" %
        (templateName, ', '.join(templateNames)))

    if count is not None:
      self.assertEqual(templateNames.count(templateName), count,
        msgPrefix + "Template '%s' was expected to be rendered %d "
        "time(s) but was actually rendered %d time(s)." %
          (templateName, count, templateNames.count(templateName)))

  def assertTemplateNotUsed(self, response=None, templateName=None, msgPrefix=''):
    """
    Asserts that the template with the provided name was NOT used in
    rendering the response. Also usable as context manager.
    """

    contextMgrTemplate, templateNames, msgPrefix = self._assertTemplateUsed(
      response, templateName, msgPrefix)

    if contextMgrTemplate:
      # Use assertTemplateNotUsed as context manager.
      return _AssertTemplateNotUsedContext(self, contextMgrTemplate)

    self.assertFalse(templateName in templateNames,
      msgPrefix + "Template '%s' was used unexpectedly in rendering"
      " the response" % templateName)

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

  def assertHTMLEqual(self, html1, html2, msg=None):
    """
    Asserts that two HTML snippets are semantically the same.
    Whitespace in most cases is ignored, and attribute ordering is not
    significant. The passed-in arguments must be valid HTML.
    """
    dom1 = assertAndParseHtml(self, html1, msg,
      'First argument is not valid HTML:')
    dom2 = assertAndParseHtml(self, html2, msg,
      'Second argument is not valid HTML:')

    if dom1 != dom2:
      standardMsg = '%s != %s' % (
        safe_repr(dom1, True), safe_repr(dom2, True))
      diff = ('\n' + '\n'.join(difflib.ndiff(
              six.textType(dom1).splitlines(),
              six.textType(dom2).splitlines())))
      standardMsg = self._truncateMessage(standardMsg, diff)
      self.fail(self._formatMessage(msg, standardMsg))

  def assertHTMLNotEqual(self, html1, html2, msg=None):
    """Asserts that two HTML snippets are not semantically equivalent."""
    dom1 = assertAndParseHtml(self, html1, msg,
      'First argument is not valid HTML:')
    dom2 = assertAndParseHtml(self, html2, msg,
      'Second argument is not valid HTML:')

    if dom1 == dom2:
      standardMsg = '%s == %s' % (
        safe_repr(dom1, True), safe_repr(dom2, True))
      self.fail(self._formatMessage(msg, standardMsg))

  def assertInHTML(self, needle, haystack, count=None, msgPrefix=''):
    needle = assertAndParseHtml(self, needle, None,
      'First argument is not valid HTML:')
    haystack = assertAndParseHtml(self, haystack, None,
      'Second argument is not valid HTML:')
    realCount = haystack.count(needle)
    if count is not None:
      self.assertEqual(realCount, count,
        msgPrefix + "Found %d instances of '%s' in response"
        " (expected %d)" % (realCount, needle, count))
    else:
      self.assertTrue(realCount != 0,
        msgPrefix + "Couldn't find '%s' in response" % needle)

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
        standardMsg = '%s != %s' % (safe_repr(xml1, True), safe_repr(xml2, True))
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
        standardMsg = '%s == %s' % (safe_repr(xml1, True), safe_repr(xml2, True))
        self.fail(self._formatMessage(msg, standardMsg))


class TransactionTestCase(SimpleTestCase):

  # Subclasses can ask for resetting of auto increment sequence before each
  # test case
  resetSequences = False

  # Subclasses can enable only a subset of apps for faster tests
  availableApps = None

  # Subclasses can define fixtures which will be automatically installed.
  fixtures = None

  # If transactions aren't available, Theory will serialize the database
  # contents into a fixture during setup and flush and reload them
  # during teardown (as flush does not restore data from migrations).
  # This can be slow; this flag allows enabling on a per-case basis.
  serializedRollback = False

  def _preSetup(self):
    """Performs any pre-test setup. This includes:

    * If the class has an 'availableApps' attribute, restricting the app
     registry to these applications, then firing postMigrate -- it must
     run with the correct set of applications for the test case.
    * If the class has a 'fixtures' attribute, installing these fixtures.
    """
    super(TransactionTestCase, self)._preSetup()
    if self.availableApps is not None:
      apps.setAvailableApps(self.availableApps)
      settingChanged.send(sender=settings._wrapped.__class__,
                 setting='INSTALLED_APPS',
                 value=self.availableApps,
                 enter=True)
      for dbName in self._databasesNames(includeMirrors=False):
        Flush.emitPostMigrate(verbosity=0, interactive=False, database=dbName)
    try:
      self._fixtureSetup()
    except Exception:
      if self.availableApps is not None:
        apps.unsetAvailableApps()
        settingChanged.send(sender=settings._wrapped.__class__,
                   setting='INSTALLED_APPS',
                   value=settings.INSTALLED_APPS,
                   enter=False)

      raise

  def _databasesNames(self, includeMirrors=True):
    # If the test case has a multiDb=True flag, act on all databases,
    # including mirrors or not. Otherwise, just on the default DB.
    if getattr(self, 'multiDb', False):
      return [alias for alias in connections
          if includeMirrors or not connections[alias].settingsDict['TEST']['MIRROR']]
    else:
      return [DEFAULT_DB_ALIAS]

  def _resetSequences(self, dbName):
    conn = connections[dbName]
    if conn.features.supportsSequenceReset:
      sqlList = conn.ops.sequenceResetByNameSql(
        noStyle(), conn.introspection.sequenceList())
      if sqlList:
        with transaction.atomic(using=dbName):
          cursor = conn.cursor()
          for sql in sqlList:
            cursor.execute(sql)

  def _fixtureSetup(self):
    for dbName in self._databasesNames(includeMirrors=False):
      # Reset sequences
      if self.resetSequences:
        self._resetSequences(dbName)

      # If we need to provide replica initial data from migrated apps,
      # then do so.
      if self.serializedRollback and hasattr(connections[dbName], "_testSerializedContents"):
        if self.availableApps is not None:
          apps.unsetAvailableApps()
        connections[dbName].creation.deserializeDbFromString(
          connections[dbName]._testSerializedContents
        )
        if self.availableApps is not None:
          apps.setAvailableApps(self.availableApps)

      if self.fixtures:
        # We have to use this slightly awkward syntax due to the fact
        # that we're using *args and **kwargs together.
        self.bridge.execeuteEzCommand(
            'theory',
            'loaddata',
            self.fixtures,
            {
              "fixtureLabel": "initialData",
              "verbosity": 0,
              "database": dbName,
              #"appLabel": appLabel,
              "skipChecks": True
            }
        )

        #callCommand('loaddata', *self.fixtures,
        #       **{'verbosity': 0, 'database': dbName, 'skipChecks': True})

  def _postTeardown(self):
    """Performs any post-test things. This includes:

    * Flushing the contents of the database, to leave a clean slate. If
     the class has an 'availableApps' attribute, postMigrate isn't fired.
    * Force-closing the connection, so the next test gets a clean cursor.
    """
    try:
      self._fixtureTeardown()
      super(TransactionTestCase, self)._postTeardown()
      # Some DB cursors include SQL statements as part of cursor
      # creation. If you have a test that does rollback, the effect of
      # these statements is lost, which can effect the operation of
      # tests (e.g., losing a timezone setting causing objects to be
      # created with the wrong time). To make sure this doesn't happen,
      # get a clean connection at the start of every test.
      for conn in connections.all():
        conn.close()
    finally:
      if self.availableApps is not None:
        apps.unsetAvailableApps()
        settingChanged.send(sender=settings._wrapped.__class__,
                   setting='INSTALLED_APPS',
                   value=settings.INSTALLED_APPS,
                   enter=False)

  def _fixtureTeardown(self):
    # Allow TRUNCATE ... CASCADE and don't emit the postMigrate signal
    # when flushing only a subset of the apps
    for dbName in self._databasesNames(includeMirrors=False):
      # Flush the database
      self.bridge.execeuteEzCommand(
          'theory',
          'flush',
          self.fixtures,
          {
            "verbosity": 0,
            "interactive": False,
            "database": dbName,
            "skipChecks": True,
            "resetSequences": False,
            "allowCascade": self.availableApps is not None,
            'inhibitPostMigrate': self.availableApps is not None,
          }
      )

      #callCommand('flush', verbosity=0, interactive=False,
      #       database=dbName, skipChecks=True,
      #       resetSequences=False,
      #       allowCascade=self.availableApps is not None,
      #       inhibitPostMigrate=self.availableApps is not None)

  def assertQuerysetEqual(self, qs, values, transform=repr, ordered=True, msg=None):
    items = six.moves.map(transform, qs)
    if not ordered:
      return self.assertEqual(set(items), set(values), msg=msg)
    values = list(values)
    # For example qs.iterator() could be passed as qs, but it does not
    # have 'ordered' attribute.
    if len(values) > 1 and hasattr(qs, 'ordered') and not qs.ordered:
      raise ValueError("Trying to compare non-ordered queryset "
               "against more than one ordered values")
    return self.assertEqual(list(items), values, msg=msg)

  def assertNumQueries(self, num, func=None, *args, **kwargs):
    using = kwargs.pop("using", DEFAULT_DB_ALIAS)
    conn = connections[using]

    context = _AssertNumQueriesContext(self, num, conn)
    if func is None:
      return context

    with context:
      func(*args, **kwargs)


def connectionsSupportTransactions():
  """
  Returns True if all connections support transactions.
  """
  return all(conn.features.supportsTransactions
        for conn in connections.all())


class TestCase(TransactionTestCase):
  """
  Does basically the same as TransactionTestCase, but surrounds every test
  with a transaction, monkey-patches the real transaction management routines
  to do nothing, and rollsback the test transaction at the end of the test.
  You have to use TransactionTestCase, if you need transaction management
  inside a test.
  """

  def _fixtureSetup(self):
    if not connectionsSupportTransactions():
      return super(TestCase, self)._fixtureSetup()

    assert not self.resetSequences, 'resetSequences cannot be used on TestCase instances'

    self.atomics = {}
    for dbName in self._databasesNames():
      self.atomics[dbName] = transaction.atomic(using=dbName)
      self.atomics[dbName].__enter__()
    # Remove this when the legacy transaction management goes away.
    disableTransactionMethods()

    for dbName in self._databasesNames(includeMirrors=False):
      if self.fixtures:
        try:
          cmd = Loaddata()
          cmd.paramForm = cmd.ParamForm()
          cmd.paramForm.fields["fixtureLabelLst"].finalData = self.fixtures
          cmd.paramForm.fields["verbosity"].finalData = 0
          cmd.paramForm.fields["appLabel"].finalData = None
          #cmd.paramForm.fields["appLabel"].finalData = "theory.apps"
          cmd.paramForm.fields["database"].finalData = dbName
          #cmd.paramForm.fields["commit"].finalData = False
          #cmd.paramForm.fields["skipChecks"].finalData = True
          cmd.paramForm.isValid()
          cmd.run()
        except Exception:
          self._fixtureTeardown()
          raise

  def _fixtureTeardown(self):
    if not connectionsSupportTransactions():
      return super(TestCase, self)._fixtureTeardown()

    # Remove this when the legacy transaction management goes away.
    restoreTransactionMethods()
    for dbName in reversed(self._databasesNames()):
      # Hack to force a rollback
      connections[dbName].needsRollback = True
      self.atomics[dbName].__exit__(None, None, None)


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


def skipIfDBFeature(feature):
  """
  Skip a test if a database has the named feature
  """
  return _deferredSkip(lambda: getattr(connection.features, feature),
             "Database has feature %s" % feature)


def skipUnlessDBFeature(feature):
  """
  Skip a test unless a database has the named feature
  """
  return _deferredSkip(lambda: not getattr(connection.features, feature),
             "Database doesn't support feature %s" % feature)

