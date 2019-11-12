from __future__ import unicode_literals

import difflib
import json
import posixpath
import sys
#import threading
import unittest
import warnings
from collections import Counter
from contextlib import contextmanager
from copy import copy
from functools import wraps
from unittest.util import safe_repr

from theory.apps import apps
from theory.conf import settings
from theory.core.exceptions import ValidationError
from theory.core.files import locks
from theory.core.bridge import Bridge
from theory.apps.command.flush import Flush
from theory.apps.command.loaddata import Loaddata
#from theory.core.management import callCommand
#from theory.core.management.color import noStyle
#from theory.core.management.sql import emitPostMigrateSignal
from theory.gui.color import noStyle
from theory.db import DEFAULT_DB_ALIAS, connection, connections, transaction
#from theory.forms.fields import CharField
from theory.test.signals import settingChanged
from theory.test.util import (
  CaptureQueriesContext, ContextList, compareXml, modifySettings,
  overrideSettings,
)
from theory.utils import six
from theory.utils.deprecation import RemovedInTheory20Warning
from theory.utils.six.moves.urllib.parse import (
  unquote, urljoin, urlparse, urlsplit, urlunsplit,
)
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
    return self.templateName in self.rendered_templateNames

  def message(self):
    return '%s was not rendered.' % self.templateName

  def __enter__(self):
    return self

  def __exit__(self, excType, excValue, traceback):
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
    return self.templateName not in self.rendered_templateNames

  def message(self):
    return '%s was rendered.' % self.templateName


class _CursorFailure(object):
  def __init__(self, clsName, wrapped):
    self.clsName = clsName
    self.wrapped = wrapped

  def __call__(self):
    raise AssertionError(
      "Database queries aren't allowed in SimpleTestCase. "
      "Either use TestCase or TransactionTestCase to ensure proper test isolation or "
      "set %s.allowDatabaseQueries to True to silence this failure." % self.clsName
    )


class SimpleTestCase(unittest.TestCase):

  _overridden_settings = None
  _modified_settings = None

  # Tests shouldn't be allowed to query the database since
  # this base class doesn't enforce any isolation.
  allowDatabaseQueries = False

  @classmethod
  def setUpClass(cls):
    super(SimpleTestCase, cls).setUpClass()
    if cls._overridden_settings:
      cls._cls_overridden_context = overrideSettings(**cls._overridden_settings)
      cls._cls_overridden_context.enable()
    if cls._modified_settings:
      cls._cls_modified_context = modifySettings(cls._modified_settings)
      cls._cls_modified_context.enable()
    if not cls.allowDatabaseQueries:
      for alias in connections:
        connection = connections[alias]
        connection.cursor = _CursorFailure(cls.__name__, connection.cursor)
        connection.chunkedCursor = _CursorFailure(cls.__name__, connection.chunkedCursor)

  @classmethod
  def tearDownClass(cls):
    if not cls.allowDatabaseQueries:
      for alias in connections:
        connection = connections[alias]
        connection.cursor = connection.cursor.wrapped
        connection.chunkedCursor = connection.chunkedCursor.wrapped
    if hasattr(cls, '_cls_modified_context'):
      cls._cls_modified_context.disable()
      delattr(cls, '_cls_modified_context')
    if hasattr(cls, '_cls_overridden_context'):
      cls._cls_overridden_context.disable()
      delattr(cls, '_cls_overridden_context')
    super(SimpleTestCase, cls).tearDownClass()

  def __call__(self, result=None):
    """
    Wrapper around default __call__ method to perform common Django test
    set up. This means that user-defined Test Cases aren't required to
    include a call to super().setUp().
    """
    testMethod = getattr(self, self._testMethodName)
    skipped = (
      getattr(self.__class__, "__unittest_skip__", False) or
      getattr(testMethod, "__unittest_skip__", False)
    )

    if not skipped:
      try:
        self._pre_setup()
      except Exception:
        result.addError(self, sys.exc_info())
        return
    super(SimpleTestCase, self).__call__(result)
    if not skipped:
      try:
        self._post_teardown()
      except Exception:
        result.addError(self, sys.exc_info())
        return

  def _pre_setup(self):
    """Performs any pre-test setup. This includes:

    * Creating a test client.
    """
    pass

  def _post_teardown(self):
    """Perform any post-test things."""
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

  @contextmanager
  def _assert_raises_message_cm(self, expectedException, expectedMessage):
    with self.assertRaises(expectedException) as cm:
      yield cm
    self.assertIn(expectedMessage, str(cm.exception))

  def assertRaisesMessage(self, expectedException, expectedMessage, *args, **kwargs):
    """
    Asserts that expectedMessage is found in the the message of a raised
    exception.

    Args:
      expectedException: Exception class expected to be raised.
      expectedMessage: expected error message string value.
      args: Function to be called and extra positional args.
      kwargs: Extra kwargs.
    """
    # callableObj was a documented kwarg in Django 1.8 and older.
    callableObj = kwargs.pop('callableObj', None)
    if callableObj:
      warnings.warn(
        'The callableObj kwarg is deprecated. Pass the callable '
        'as a positional argument instead.', RemovedInTheory20Warning
      )
    elif len(args):
      callableObj = args[0]
      args = args[1:]

    cm = self._assert_raises_message_cm(expectedException, expectedMessage)
    # Assertion used in context manager fashion.
    if callableObj is None:
      return cm
    # Assertion was passed a callable.
    with cm:
      callableObj(*args, **kwargs)

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
        diff = ('\n' + '\n'.join(
          difflib.ndiff(
            six.textType(xml1).splitlines(),
            six.textType(xml2).splitlines(),
          )
        ))
        standardMsg = self._truncateMessage(standardMsg, diff)
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

  if six.PY2:
    assertCountEqual = unittest.TestCase.assertItemsEqual
    assertNotRegex = unittest.TestCase.assertNotRegexpMatches
    assertRaisesRegex = unittest.TestCase.assertRaisesRegexp
    assertRegex = unittest.TestCase.assertRegexpMatches

  def assertDict(self, dict1, dict2, excludeKeyLst=[], excludePathLst=[]):
    self.assertDataBlock(
      dict1,
      dict2,
      lambda d, key: d.get(key),
      lambda d: d.keys(),
      [],
      excludeKeyLst,
      excludePathLst,
    )

  def assertObj(self, obj1, obj2, excludeKeyLst=[], excludePathLst=[]):
    self.assertDataBlock(
      obj1,
      obj2,
      lambda obj, key: getattr(obj, key),
      # or may be we should use dirs, can we cmp method? We should investigate
      # deeper when we have more time
      lambda obj: vars(obj),
      [],
      excludeKeyLst,
      excludePathLst,
    )

  def assertDataBlock(
    self,
    dobj1,
    dobj2,
    getFxn,
    lstFxn,
    pathLst,
    excludeKeyLst=[],
    excludePathLst=[],
    ):
    """
    Being used by assertDict and assertObj which should be easier to use.
    """
    keyLst = [i for i in sorted(lstFxn(dobj1)) if i not in excludeKeyLst]
    keyLst2 = [i for i in sorted(lstFxn(dobj2)) if i not in excludeKeyLst]
    self.assertEqual(
      keyLst,
      keyLst2,
      {
        "version 1": keyLst,
        "version 2": keyLst2,
        "path": pathLst,
        "excludeKeyLst": excludeKeyLst
      }
    )
    for key in keyLst:
      if key in excludeKeyLst:
        continue
      child = getFxn(dobj1, key)
      child2 = getFxn(dobj2, key)
      if isinstance(child, dict) or isinstance(child, type):
        # Only continue the recursion when child is a dict or an object
        childPathLst = pathLst + [key]
        if childPathLst not in excludeKeyLst:
          self.assertDataBlock(
            child,
            child2,
            getFxn,
            lstFxn,
            childPathLst,
            excludeKeyLst,
            excludePathLst,
          )
      else:
        self.assertEqual(
          child,
          child2,
          (
            "path: {0}\n"
            "version 1: {1}\n"
            "version 2: {2}\n"
          ).format(pathLst, child, child2)
        )


class TransactionTestCase(SimpleTestCase):

  # Subclasses can ask for resetting of auto increment sequence before each
  # test case
  resetSequences = False

  # Subclasses can enable only a subset of apps for faster tests
  availableApps = None

  # Subclasses can define fixtures which will be automatically installed.
  fixtures = None

  # If transactions aren't available, Django will serialize the database
  # contents into a fixture during setup and flush and reload them
  # during teardown (as flush does not restore data from migrations).
  # This can be slow; this flag allows enabling on a per-case basis.
  serializedRollback = False

  # Since tests will be wrapped in a transaction, or serialized if they
  # are not available, we allow queries to be run.
  allowDatabaseQueries = True

  def _pre_setup(self):
    """Performs any pre-test setup. This includes:

    * If the class has an 'availableApps' attribute, restricting the app
     registry to these applications, then firing postMigrate -- it must
     run with the correct set of applications for the test case.
    * If the class has a 'fixtures' attribute, installing these fixtures.
    """
    super(TransactionTestCase, self)._pre_setup()
    if self.availableApps is not None:
      apps.setAvailableApps(self.availableApps)
      settingChanged.send(
        sender=settings._wrapped.__class__,
        setting='INSTALLED_APPS',
        value=self.availableApps,
        enter=True,
      )
      for dbName in self._databases_names(includeMirrors=False):
        Flush.emitPostMigrateSignal(verbosity=0, interactive=False, db=dbName)
    try:
      self._fixture_setup()
    except Exception:
      if self.availableApps is not None:
        apps.unsetAvailableApps()
        settingChanged.send(
          sender=settings._wrapped.__class__,
          setting='INSTALLED_APPS',
          value=settings.INSTALLED_APPS,
          enter=False,
        )
      raise

  @classmethod
  def _databases_names(cls, includeMirrors=True):
    # If the test case has a multiDb=True flag, act on all databases,
    # including mirrors or not. Otherwise, just on the default DB.
    if getattr(cls, 'multiDb', False):
      return [
        alias for alias in connections
        if includeMirrors or not connections[alias].settingsDict['TEST']['MIRROR']
      ]
    else:
      return [DEFAULT_DB_ALIAS]

  def _reset_sequences(self, dbName):
    conn = connections[dbName]
    if conn.features.supportsSequenceReset:
      sqlList = conn.ops.sequenceResetByNameSql(
        noStyle(), conn.introspection.sequenceList())
      if sqlList:
        with transaction.atomic(using=dbName):
          cursor = conn.cursor()
          for sql in sqlList:
            cursor.execute(sql)

  def _fixture_setup(self):
    for dbName in self._databases_names(includeMirrors=False):
      # Reset sequences
      if self.resetSequences:
        self._reset_sequences(dbName)

      # If we need to provide replica initial data from migrated apps,
      # then do so.
      if self.serializedRollback and hasattr(connections[dbName], "_test_serialized_contents"):
        if self.availableApps is not None:
          apps.unsetAvailableApps()
        connections[dbName].creation.deserializeDbFromString(
          connections[dbName]._test_serialized_contents
        )
        if self.availableApps is not None:
          apps.setAvailableApps(self.availableApps)

      if self.fixtures:
        self.bridge.executeEzCommand(
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
        ## We have to use this slightly awkward syntax due to the fact
        ## that we're using *args and **kwargs together.
        #callCommand('loaddata', *self.fixtures,
        #       **{'verbosity': 0, 'database': dbName})

  def _should_reload_connections(self):
    return True

  def _post_teardown(self):
    """Performs any post-test things. This includes:

    * Flushing the contents of the database, to leave a clean slate. If
     the class has an 'availableApps' attribute, postMigrate isn't fired.
    * Force-closing the connection, so the next test gets a clean cursor.
    """
    try:
      self._fixture_teardown()
      super(TransactionTestCase, self)._post_teardown()
      if self._should_reload_connections():
        # Some DB cursors include SQL statements as part of cursor
        # creation. If you have a test that does a rollback, the effect
        # of these statements is lost, which can affect the operation of
        # tests (e.g., losing a timezone setting causing objects to be
        # created with the wrong time). To make sure this doesn't
        # happen, get a clean connection at the start of every test.
        for conn in connections.all():
          conn.close()
    finally:
      if self.availableApps is not None:
        apps.unsetAvailableApps()
        settingChanged.send(sender=settings._wrapped.__class__,
                   setting='INSTALLED_APPS',
                   value=settings.INSTALLED_APPS,
                   enter=False)

  def _fixture_teardown(self):
    # Allow TRUNCATE ... CASCADE and don't emit the postMigrate signal
    # when flushing only a subset of the apps
    for dbName in self._databases_names(includeMirrors=False):
      # Flush the database
      inhibitPostMigrate = (
        self.availableApps is not None or
        (  # Inhibit the postMigrate signal when using serialized
          # rollback to avoid trying to recreate the serialized data.
          self.serializedRollback and
          hasattr(connections[dbName], '_test_serialized_contents')
        )
      )
      # Flush the database
      self.bridge.executeEzCommand(
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
      #       database=dbName, resetSequences=False,
      #       allowCascade=self.availableApps is not None,
      #       inhibitPostMigrate=inhibitPostMigrate)

  def assertQuerysetEqual(self, qs, values, transform=repr, ordered=True, msg=None):
    items = six.moves.map(transform, qs)
    if not ordered:
      return self.assertEqual(Counter(items), Counter(values), msg=msg)
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
  Similar to TransactionTestCase, but uses `transaction.atomic()` to achieve
  test isolation.

  In most situations, TestCase should be preferred to TransactionTestCase as
  it allows faster execution. However, there are some situations where using
  TransactionTestCase might be necessary (e.g. testing some transactional
  behavior).

  On database backends with no transaction support, TestCase behaves as
  TransactionTestCase.
  """
  @classmethod
  def _enter_atomics(cls):
    """Helper method to open atomic blocks for multiple databases"""
    atomics = {}
    for dbName in cls._databases_names():
      atomics[dbName] = transaction.atomic(using=dbName)
      atomics[dbName].__enter__()
    return atomics

  @classmethod
  def _rollback_atomics(cls, atomics):
    """Rollback atomic blocks opened through the previous method"""
    for dbName in reversed(cls._databases_names()):
      transaction.setRollback(True, using=dbName)
      atomics[dbName].__exit__(None, None, None)

  @classmethod
  def setUpClass(cls):
    super(TestCase, cls).setUpClass()
    if not connectionsSupportTransactions():
      return
    cls.clsAtomics = cls._enter_atomics()

    if cls.fixtures:
      bridge = Bridge()
      for dbName in cls._databases_names(includeMirrors=False):
        try:
										# Cannot use executeEzCommand in here because the app is not
          # yet ready
          cmd = Loaddata()
          cmd.paramForm = cmd.ParamForm()
          cmd.paramForm.fields[
            "fixtureLabelLst"
          ].finalData = cls.fixtures
          cmd.paramForm.fields["verbosity"].finalData = 0
          cmd.paramForm.fields["appLabel"].finalData = None
          cmd.paramForm.fields["database"].finalData = dbName
          cmd.paramForm.isValid()
          cmd.run()
        except Exception:
          cls._rollback_atomics(cls.clsAtomics)
          raise
        #try:
        #  callCommand('loaddata', *cls.fixtures, **{
        #    'verbosity': 0,
        #    'commit': False,
        #    'database': dbName,
        #  })
        #except Exception:
        #  cls._rollback_atomics(cls.clsAtomics)
        #  raise
    try:
      cls.setUpTestData()
    except Exception:
      cls._rollback_atomics(cls.clsAtomics)
      raise

  @classmethod
  def tearDownClass(cls):
    if connectionsSupportTransactions():
      cls._rollback_atomics(cls.clsAtomics)
      for conn in connections.all():
        conn.close()
    super(TestCase, cls).tearDownClass()

  @classmethod
  def setUpTestData(cls):
    """Load initial data for the TestCase"""
    pass

  def _should_reload_connections(self):
    if connectionsSupportTransactions():
      return False
    return super(TestCase, self)._should_reload_connections()

  def _fixture_setup(self):
    if not connectionsSupportTransactions():
      # If the backend does not support transactions, we should reload
      # class data before each test
      self.setUpTestData()
      return super(TestCase, self)._fixture_setup()

    assert not self.resetSequences, 'resetSequences cannot be used on TestCase instances'
    self.atomics = self._enter_atomics()

  def _fixture_teardown(self):
    if not connectionsSupportTransactions():
      return super(TestCase, self)._fixture_teardown()
    try:
      for dbName in reversed(self._databases_names()):
        if self._should_check_constraints(connections[dbName]):
          connections[dbName].checkConstraints()
    finally:
      self._rollback_atomics(self.atomics)

  def _should_check_constraints(self, connection):
    return (
      connection.features.canDeferConstraintChecks and
      not connection.needsRollback and connection.isUsable()
    )


class CheckCondition(object):
  """Descriptor class for deferred condition checking"""
  def __init__(self, *conditions):
    self.conditions = conditions

  def addCondition(self, condition, reason):
    return self.__class__(*self.conditions + ((condition, reason),))

  def __get__(self, instance, cls=None):
    # Trigger access for all bases.
    if any(getattr(base, '__unittest_skip__', False) for base in cls.__bases__):
      return True
    for condition, reason in self.conditions:
      if condition():
        # Override this descriptor's value and set the skip reason.
        cls.__unittest_skip__ = True
        cls.__unittest_skip_why__ = reason
        return True
    return False


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
      # Retrieve the possibly existing value from the class's dict to
      # avoid triggering the descriptor.
      skip = testFunc.__dict__.get('__unittest_skip__')
      if isinstance(skip, CheckCondition):
        testItem.__unittest_skip__ = skip.addCondition(condition, reason)
      elif skip is not True:
        testItem.__unittest_skip__ = CheckCondition((condition, reason))
    return testItem
  return decorator


def skipIfDBFeature(*features):
  """
  Skip a test if a database has at least one of the named features.
  """
  return _deferredSkip(
    lambda: any(getattr(connection.features, feature, False) for feature in features),
    "Database has feature(s) %s" % ", ".join(features)
  )


def skipUnlessDBFeature(*features):
  """
  Skip a test unless a database has all the named features.
  """
  return _deferredSkip(
    lambda: not all(getattr(connection.features, feature, False) for feature in features),
    "Database doesn't support feature(s): %s" % ", ".join(features)
  )


def skipUnlessAnyDBFeature(*features):
  """
  Skip a test unless a database has any of the named features.
  """
  return _deferredSkip(
    lambda: not any(getattr(connection.features, feature, False) for feature in features),
    "Database doesn't support any of the feature(s): %s" % ", ".join(features)
  )

#class LiveServerTestCase(TransactionTestCase):
#  """
#  Does basically the same as TransactionTestCase but also launches a live
#  http server in a separate thread so that the tests may use another testing
#  framework, such as Selenium for example, instead of the built-in dummy
#  client.
#  Note that it inherits from TransactionTestCase instead of TestCase because
#  the threads do not share the same transactions (unless if using in-memory
#  sqlite) and each thread needs to commit all their transactions so that the
#  other thread can see the changes.
#  """
#  host = 'localhost'
#  port = 0
#  serverThreadClass = LiveServerThread
#  staticHandler = _StaticFilesHandler
#
#  @classproperty
#  def liveServerUrl(cls):
#    return 'http://%s:%s' % (cls.host, cls.serverThread.port)
#
#  @classmethod
#  def setUpClass(cls):
#    super(LiveServerTestCase, cls).setUpClass()
#    connectionsOverride = {}
#    for conn in connections.all():
#      # If using in-memory sqlite databases, pass the connections to
#      # the server thread.
#      if conn.vendor == 'sqlite' and conn.isInMemoryDb():
#        # Explicitly enable thread-shareability for this connection
#        conn.allowThreadSharing = True
#        connectionsOverride[conn.alias] = conn
#
#    cls._live_server_modified_settings = modifySettings(
#      ALLOWED_HOSTS={'append': cls.host},
#    )
#    cls._live_server_modified_settings.enable()
#    cls.serverThread = cls._create_serverThread(connectionsOverride)
#    cls.serverThread.daemon = True
#    cls.serverThread.start()
#
#    # Wait for the live server to be ready
#    cls.serverThread.isReady.wait()
#    if cls.serverThread.error:
#      # Clean up behind ourselves, since tearDownClass won't get called in
#      # case of errors.
#      cls._tearDownClassInternal()
#      raise cls.serverThread.error
#
#  @classmethod
#  def _create_server_thread(cls, connectionsOverride):
#    return cls.serverThreadClass(
#      cls.host,
#      cls.staticHandler,
#      connectionsOverride=connectionsOverride,
#      port=cls.port,
#    )
#
#  @classmethod
#  def _tearDownClassInternal(cls):
#    # There may not be a 'serverThread' attribute if setUpClass() for some
#    # reasons has raised an exception.
#    if hasattr(cls, 'serverThread'):
#      # Terminate the live server's thread
#      cls.serverThread.terminate()
#
#    # Restore sqlite in-memory database connections' non-shareability
#    for conn in connections.all():
#      if conn.vendor == 'sqlite' and conn.isInMemoryDb():
#        conn.allowThreadSharing = False
#
#  @classmethod
#  def tearDownClass(cls):
#    cls._tearDownClassInternal()
#    cls._live_server_modified_settings.disable()
#    super(LiveServerTestCase, cls).tearDownClass()


class SerializeMixin(object):
  """
  Mixin to enforce serialization of TestCases that share a common resource.

  Define a common 'lockfile' for each set of TestCases to serialize. This
  file must exist on the filesystem.

  Place it early in the MRO in order to isolate setUpClass / tearDownClass.
  """

  lockfile = None

  @classmethod
  def setUpClass(cls):
    if cls.lockfile is None:
      raise ValueError(
        "{}.lockfile isn't set. Set it to a unique value "
        "in the base class.".format(cls.__name__))
    cls._lockfile = open(cls.lockfile)
    locks.lock(cls._lockfile, locks.LOCK_EX)
    super(SerializeMixin, cls).setUpClass()

  @classmethod
  def tearDownClass(cls):
    super(SerializeMixin, cls).tearDownClass()
    cls._lockfile.close()

