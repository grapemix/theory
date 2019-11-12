import collections
import logging
import re
import sys
import time
import warnings
from contextlib import contextmanager
from functools import wraps
from unittest import TestCase, skipIf, skipUnless
from xml.dom.minidom import Node, parseString

from theory.apps import apps
from theory.apps.registry import Apps
from theory.conf import UserSettingsHolder, settings
from theory.core.exceptions import ImproperlyConfigured
from theory.core.signals import requestStarted
from theory.db import DEFAULT_DB_ALIAS, connections, resetQueries
from theory.db.model.options import Options
from theory.test.signals import settingChanged
from theory.utils import six
from theory.utils.decorators import availableAttrs
from theory.utils.encoding import forceStr
from theory.utils.translation import deactivate

if six.PY3:
  from types import SimpleNamespace
else:
  class SimpleNamespace(object):
    pass

try:
  import jinja2
except ImportError:
  jinja2 = None


__all__ = (
  'Approximate', 'ContextList', 'isolateLruCache', 'getRunner',
  'modifySettings', 'overrideSettings',
  'requiresTzSupport',
  'setupTestEnvironment', 'teardownTestEnvironment',
)

TZ_SUPPORT = hasattr(time, 'tzset')


class Approximate(object):
  def __init__(self, val, places=7):
    self.val = val
    self.places = places

  def __repr__(self):
    return repr(self.val)

  def __eq__(self, other):
    if self.val == other:
      return True
    return round(abs(self.val - other), self.places) == 0


class ContextList(list):
  """A wrapper that provides direct key access to context items contained
  in a list of context objects.
  """
  def __getitem__(self, key):
    if isinstance(key, six.stringTypes):
      for subcontext in self:
        if key in subcontext:
          return subcontext[key]
      raise KeyError(key)
    else:
      return super(ContextList, self).__getitem__(key)

  def get(self, key, default=None):
    try:
      return self.__getitem__(key)
    except KeyError:
      return default

  def __contains__(self, key):
    try:
      self[key]
    except KeyError:
      return False
    return True

  def keys(self):
    """
    Flattened keys of subcontexts.
    """
    keys = set()
    for subcontext in self:
      for dict in subcontext:
        keys |= set(dict.keys())
    return keys


#def instrumentedTestRender(self, context):
#  """
#  An instrumented Template render method, providing a signal
#  that can be intercepted by the test system Client
#  """
#  templateRendered.send(sender=self, template=self, context=context)
#  return self.nodelist.render(context)


class _TestState(object):
  pass


def setupTestEnvironment(debug=None):
  """
  Perform global pre-test setup, such as installing the instrumented template
  renderer and setting the email backend to the locmem email backend.
  """
  if hasattr(_TestState, 'savedData'):
    # Executing this function twice would overwrite the saved values.
    raise RuntimeError(
      "setupTestEnvironment() was already called and can't be called "
      "again without first calling teardownTestEnvironment()."
    )

  if debug is None:
    debug = settings.DEBUG

  savedData = SimpleNamespace()
  _TestState.savedData = savedData

  savedData.debug = settings.DEBUG
  settings.DEBUG = debug

  deactivate()


def teardownTestEnvironment():
  """
  Perform any global post-test teardown, such as restoring the original
  template renderer and restoring the email sending functions.
  """
  savedData = _TestState.savedData

  settings.DEBUG = savedData.debug

  del _TestState.savedData


def setupDatabases(verbosity, interactive, keepdb=False, debugSql=False, parallel=0, **kwargs):
  """
  Create the test databases.
  """
  testDatabases, mirroredAliases = getUniqueDatabasesAndMirrors()

  oldNames = []

  for signature, (dbName, aliases) in testDatabases.items():
    firstAlias = None
    for alias in aliases:
      connection = connections[alias]
      oldNames.append((connection, dbName, firstAlias is None))

      # Actually create the database for the first connection
      if firstAlias is None:
        firstAlias = alias
        connection.creation.createTestDb(
          verbosity=verbosity,
          autoclobber=not interactive,
          #keepdb=keepdb,
          serialize=connection.settingsDict.get('TEST', {}).get('SERIALIZE', True),
        )
        if parallel > 1:
          for index in range(parallel):
            connection.creation.cloneTestDb(
              number=index + 1,
              verbosity=verbosity,
              keepdb=keepdb,
            )
      # Configure all other connections as mirrors of the first one
      else:
        connections[alias].creation.setAsTestMirror(connections[firstAlias].settingsDict)

  # Configure the test mirrors.
  for alias, mirrorAlias in mirroredAliases.items():
    connections[alias].creation.setAsTestMirror(
      connections[mirrorAlias].settingsDict)

  if debugSql:
    for alias in connections:
      connections[alias].forceDebugCursor = True

  return oldNames


def dependencyOrdered(testDatabases, dependencies):
  """
  Reorder testDatabases into an order that honors the dependencies
  described in TEST[DEPENDENCIES].
  """
  orderedTestDatabases = []
  resolvedDatabases = set()

  # Maps db signature to dependencies of all its aliases
  dependenciesMap = {}

  # Check that no database depends on its own alias
  for sig, (_, aliases) in testDatabases:
    allDeps = set()
    for alias in aliases:
      allDeps.update(dependencies.get(alias, []))
    if not allDeps.isdisjoint(aliases):
      raise ImproperlyConfigured(
        "Circular dependency: databases %r depend on each other, "
        "but are aliases." % aliases
      )
    dependenciesMap[sig] = allDeps

  while testDatabases:
    changed = False
    deferred = []

    # Try to find a DB that has all its dependencies met
    for signature, (dbName, aliases) in testDatabases:
      if dependenciesMap[signature].issubset(resolvedDatabases):
        resolvedDatabases.update(aliases)
        orderedTestDatabases.append((signature, (dbName, aliases)))
        changed = True
      else:
        deferred.append((signature, (dbName, aliases)))

    if not changed:
      raise ImproperlyConfigured("Circular dependency in TEST[DEPENDENCIES]")
    testDatabases = deferred
  return orderedTestDatabases


def getUniqueDatabasesAndMirrors():
  """
  Figure out which databases actually need to be created.

  Deduplicate entries in DATABASES that correspond the same database or are
  configured as test mirrors.

  Return two values:
  - testDatabases: ordered mapping of signatures to (name, list of aliases)
           where all aliases share the same underlying database.
  - mirroredAliases: mapping of mirror aliases to original aliases.
  """
  mirroredAliases = {}
  testDatabases = {}
  dependencies = {}
  defaultSig = connections[DEFAULT_DB_ALIAS].creation.testDbSignature()

  for alias in connections:
    connection = connections[alias]
    testSettings = connection.settingsDict['TEST']

    if testSettings['MIRROR']:
      # If the database is marked as a test mirror, save the alias.
      mirroredAliases[alias] = testSettings['MIRROR']
    else:
      # Store a tuple with DB parameters that uniquely identify it.
      # If we have two aliases with the same values for that tuple,
      # we only need to create the test database once.
      item = testDatabases.setdefault(
        connection.creation.testDbSignature(),
        (connection.settingsDict['NAME'], set())
      )
      item[1].add(alias)

      if 'DEPENDENCIES' in testSettings:
        dependencies[alias] = testSettings['DEPENDENCIES']
      else:
        if alias != DEFAULT_DB_ALIAS and connection.creation.testDbSignature() != defaultSig:
          dependencies[alias] = testSettings.get('DEPENDENCIES', [DEFAULT_DB_ALIAS])

  testDatabases = dependencyOrdered(testDatabases.items(), dependencies)
  testDatabases = collections.OrderedDict(testDatabases)
  return testDatabases, mirroredAliases


def teardownDatabases(oldConfig, verbosity, parallel=0, keepdb=False):
  """
  Destroy all the non-mirror databases.
  """
  for connection, oldName, destroy in oldConfig:
    if destroy:
      if parallel > 1:
        for index in range(parallel):
          connection.creation.destroyTestDb(
            number=index + 1,
            verbosity=verbosity,
            #keepdb=keepdb,
          )
      #connection.creation.destroyTestDb(oldName, verbosity, keepdb)
      connection.creation.destroyTestDb(oldName, verbosity)


def getRunner(settings, testRunnerClass=None):
  if not testRunnerClass:
    testRunnerClass = settings.TEST_RUNNER

  testPath = testRunnerClass.split('.')
  # Allow for Python 2.5 relative paths
  if len(testPath) > 1:
    testModuleName = '.'.join(testPath[:-1])
  else:
    testModuleName = '.'
  testModule = __import__(testModuleName, {}, {}, forceStr(testPath[-1]))
  testRunner = getattr(testModule, testPath[-1])
  return testRunner


class TestContextDecorator(object):
  """
  A base class that can either be used as a context manager during tests
  or as a test function or unittest.TestCase subclass decorator to perform
  temporary alterations.

  `attrName`: attribute assigned the return value of enable() if used as
         a class decorator.

  `kwargName`: keyword argument passing the return value of enable() if
         used as a function decorator.
  """
  def __init__(self, attrName=None, kwargName=None):
    self.attrName = attrName
    self.kwargName = kwargName

  def enable(self):
    raise NotImplementedError

  def disable(self):
    raise NotImplementedError

  def __enter__(self):
    return self.enable()

  def __exit__(self, excType, excValue, traceback):
    self.disable()

  def decorateClass(self, cls):
    if issubclass(cls, TestCase):
      decoratedSetUp = cls.setUp
      decoratedTearDown = cls.tearDown

      def setUp(innerSelf):
        context = self.enable()
        if self.attrName:
          setattr(innerSelf, self.attrName, context)
        decoratedSetUp(innerSelf)

      def tearDown(innerSelf):
        decoratedTearDown(innerSelf)
        self.disable()

      cls.setUp = setUp
      cls.tearDown = tearDown
      return cls
    raise TypeError('Can only decorate subclasses of unittest.TestCase')

  def decorateCallable(self, func):
    @wraps(func, assigned=availableAttrs(func))
    def inner(*args, **kwargs):
      with self as context:
        if self.kwargName:
          kwargs[self.kwargName] = context
        return func(*args, **kwargs)
    return inner

  def __call__(self, decorated):
    if isinstance(decorated, type):
      return self.decorateClass(decorated)
    elif callable(decorated):
      return self.decorateCallable(decorated)
    raise TypeError('Cannot decorate object of type %s' % type(decorated))


class overrideSettings(TestContextDecorator):
  """
  Acts as either a decorator or a context manager. If it's a decorator it
  takes a function and returns a wrapped function. If it's a contextmanager
  it's used with the ``with`` statement. In either event entering/exiting
  are called before and after, respectively, the function/block is executed.
  """
  def __init__(self, **kwargs):
    self.options = kwargs
    super(overrideSettings, self).__init__()

  def enable(self):
    # Keep this code at the beginning to leave the settings unchanged
    # in case it raises an exception because INSTALLED_APPS is invalid.
    if 'INSTALLED_APPS' in self.options:
      try:
        apps.setInstalledApps(self.options['INSTALLED_APPS'])
      except Exception:
        apps.unsetInstalledApps()
        raise
    override = UserSettingsHolder(settings._wrapped)
    for key, newValue in self.options.items():
      setattr(override, key, newValue)
    self.wrapped = settings._wrapped
    settings._wrapped = override
    for key, newValue in self.options.items():
      settingChanged.send(sender=settings._wrapped.__class__,
                 setting=key, value=newValue, enter=True)

  def disable(self):
    if 'INSTALLED_APPS' in self.options:
      apps.unsetInstalledApps()
    settings._wrapped = self.wrapped
    del self.wrapped
    for key in self.options:
      newValue = getattr(settings, key, None)
      settingChanged.send(sender=settings._wrapped.__class__,
                 setting=key, value=newValue, enter=False)

  def saveOptions(self, testFunc):
    if testFunc._overridden_settings is None:
      testFunc._overridden_settings = self.options
    else:
      # Duplicate dict to prevent subclasses from altering their parent.
      testFunc._overridden_settings = dict(
        testFunc._overridden_settings, **self.options)

  def decorateClass(self, cls):
    from django.test import SimpleTestCase
    if not issubclass(cls, SimpleTestCase):
      raise ValueError(
        "Only subclasses of Django SimpleTestCase can be decorated "
        "with overrideSettings")
    self.saveOptions(cls)
    return cls


class modifySettings(overrideSettings):
  """
  Like overrideSettings, but makes it possible to append, prepend or remove
  items instead of redefining the entire list.
  """
  def __init__(self, *args, **kwargs):
    if args:
      # Hack used when instantiating from SimpleTestCase.setUpClass.
      assert not kwargs
      self.operations = args[0]
    else:
      assert not args
      self.operations = list(kwargs.items())
    super(overrideSettings, self).__init__()

  def saveOptions(self, testFunc):
    if testFunc._modified_settings is None:
      testFunc._modified_settings = self.operations
    else:
      # Duplicate list to prevent subclasses from altering their parent.
      testFunc._modified_settings = list(
        testFunc._modified_settings) + self.operations

  def enable(self):
    self.options = {}
    for name, operations in self.operations:
      try:
        # When called from SimpleTestCase.setUpClass, values may be
        # overridden several times; cumulate changes.
        value = self.options[name]
      except KeyError:
        value = list(getattr(settings, name, []))
      for action, items in operations.items():
        # items my be a single value or an iterable.
        if isinstance(items, six.stringTypes):
          items = [items]
        if action == 'append':
          value = value + [item for item in items if item not in value]
        elif action == 'prepend':
          value = [item for item in items if item not in value] + value
        elif action == 'remove':
          value = [item for item in value if item not in items]
        else:
          raise ValueError("Unsupported action: %s" % action)
      self.options[name] = value
    super(modifySettings, self).enable()


class overrideSystemChecks(TestContextDecorator):
  """
  Acts as a decorator. Overrides list of registered system checks.
  Useful when you override `INSTALLED_APPS`, e.g. if you exclude `auth` app,
  you also need to exclude its system checks.
  """
  def __init__(self, newChecks, deploymentChecks=None):
    from django.core.checks.registry import registry
    self.registry = registry
    self.newChecks = newChecks
    self.deploymentChecks = deploymentChecks
    super(overrideSystemChecks, self).__init__()

  def enable(self):
    self.oldChecks = self.registry.registeredChecks
    self.registry.registeredChecks = self.newChecks
    self.oldDeploymentChecks = self.registry.deploymentChecks
    if self.deploymentChecks is not None:
      self.registry.deploymentChecks = self.deploymentChecks

  def disable(self):
    self.registry.registeredChecks = self.oldChecks
    self.registry.deploymentChecks = self.old_deploymentChecks


def compareXml(want, got):
  """Tries to do a 'xml-comparison' of want and got. Plain string
  comparison doesn't always work because, for example, attribute
  ordering should not be important. Comment nodes are not considered in the
  comparison. Leading and trailing whitespace is ignored on both chunks.

  Based on https://github.com/lxml/lxml/blob/master/src/lxml/doctestcompare.py
  """
  _norm_whitespace_re = re.compile(r'[ \t\n][ \t\n]+')

  def normWhitespace(v):
    return _norm_whitespace_re.sub(' ', v)

  def childText(element):
    return ''.join(c.data for c in element.childNodes
            if c.nodeType == Node.TEXT_NODE)

  def children(element):
    return [c for c in element.childNodes
        if c.nodeType == Node.ELEMENT_NODE]

  def normChildText(element):
    return normWhitespace(childText(element))

  def attrsDict(element):
    return dict(element.attributes.items())

  def checkElement(wantElement, gotElement):
    if wantElement.tagName != gotElement.tagName:
      return False
    if normChildText(wantElement) != normChildText(gotElement):
      return False
    if attrsDict(wantElement) != attrsDict(gotElement):
      return False
    wantChildren = children(wantElement)
    gotChildren = children(gotElement)
    if len(wantChildren) != len(gotChildren):
      return False
    for want, got in zip(wantChildren, gotChildren):
      if not checkElement(want, got):
        return False
    return True

  def firstNode(document):
    for node in document.childNodes:
      if node.nodeType != Node.COMMENT_NODE:
        return node

  want, got = stripQuotes(want, got)
  want = want.strip().replace('\\n', '\n')
  got = got.strip().replace('\\n', '\n')

  # If the string is not a complete xml document, we may need to add a
  # root element. This allow us to compare fragments, like "<foo/><bar/>"
  if not want.startswith('<?xml'):
    wrapper = '<root>%s</root>'
    want = wrapper % want
    got = wrapper % got

  # Parse the want and got strings, and compare the parsings.
  wantRoot = firstNode(parseString(want))
  gotRoot = firstNode(parseString(got))

  return checkElement(wantRoot, gotRoot)


def stripQuotes(want, got):
  """
  Strip quotes of doctests output values:

  >>> stripQuotes("'foo'")
  "foo"
  >>> stripQuotes('"foo"')
  "foo"
  """
  def isQuotedString(s):
    s = s.strip()
    return len(s) >= 2 and s[0] == s[-1] and s[0] in ('"', "'")

  def isQuotedUnicode(s):
    s = s.strip()
    return len(s) >= 3 and s[0] == 'u' and s[1] == s[-1] and s[1] in ('"', "'")

  if isQuotedString(want) and isQuotedString(got):
    want = want.strip()[1:-1]
    got = got.strip()[1:-1]
  elif isQuotedUnicode(want) and isQuotedUnicode(got):
    want = want.strip()[2:-1]
    got = got.strip()[2:-1]
  return want, got


def strPrefix(s):
  return s % {'_': '' if six.PY3 else 'u'}


class CaptureQueriesContext(object):
  """
  Context manager that captures queries executed by the specified connection.
  """
  def __init__(self, connection):
    self.connection = connection

  def __iter__(self):
    return iter(self.capturedQueries)

  def __getitem__(self, index):
    return self.capturedQueries[index]

  def __len__(self):
    return len(self.capturedQueries)

  @property
  def capturedQueries(self):
    return self.connection.queries[self.initialQueries:self.finalQueries]

  def __enter__(self):
    self.forceDebugCursor = self.connection.forceDebugCursor
    self.connection.forceDebugCursor = True
    self.initialQueries = len(self.connection.queriesLog)
    self.finalQueries = None
    requestStarted.disconnect(resetQueries)
    return self

  def __exit__(self, excType, excValue, traceback):
    self.connection.forceDebugCursor = self.forceDebugCursor
    requestStarted.connect(resetQueries)
    if excType is not None:
      return
    self.finalQueries = len(self.connection.queriesLog)


class ignoreWarnings(TestContextDecorator):
  def __init__(self, **kwargs):
    self.ignoreKwargs = kwargs
    if 'message' in self.ignoreKwargs or 'module' in self.ignoreKwargs:
      self.filterFunc = warnings.filterwarnings
    else:
      self.filterFunc = warnings.simplefilter
    super(ignoreWarnings, self).__init__()

  def enable(self):
    self.catchWarnings = warnings.catchWarnings()
    self.catchWarnings.__enter__()
    self.filterFunc('ignore', **self.ignoreKwargs)

  def disable(self):
    self.catchWarnings.__exit__(*sys.exc_info())


@contextmanager
def patchLogger(loggerName, logLevel, logKwargs=False):
  """
  Context manager that takes a named logger and the logging level
  and provides a simple mock-like list of messages received
  """
  calls = []

  def replacement(msg, *args, **kwargs):
    call = msg % args
    calls.append((call, kwargs) if logKwargs else call)
  logger = logging.getLogger(loggerName)
  orig = getattr(logger, logLevel)
  setattr(logger, logLevel, replacement)
  try:
    yield calls
  finally:
    setattr(logger, logLevel, orig)


# On OSes that don't provide tzset (Windows), we can't set the timezone
# in which the program runs. As a consequence, we must skip tests that
# don't enforce a specific timezone (with timezone.override or equivalent),
# or attempt to interpret naive datetimes in the default timezone.

requiresTzSupport = skipUnless(
  TZ_SUPPORT,
  "This test relies on the ability to run a program in an arbitrary "
  "time zone, but your operating system isn't able to do that."
)


@contextmanager
def extendSysPath(*paths):
  """Context manager to temporarily add paths to sys.path."""
  _orig_sys_path = sys.path[:]
  sys.path.extend(paths)
  try:
    yield
  finally:
    sys.path = _orig_sys_path


@contextmanager
def isolateLruCache(lruCacheObject):
  """Clear the cache of an LRU cache object on entering and exiting."""
  lruCacheObject.cacheClear()
  try:
    yield
  finally:
    lruCacheObject.cacheClear()


@contextmanager
def capturedOutput(streamName):
  """Return a context manager used by capturedStdout/stdin/stderr
  that temporarily replaces the sys stream *streamName* with a StringIO.

  Note: This function and the following ``capturedStd*`` are copied
     from CPython's ``test.support`` module."""
  origStdout = getattr(sys, streamName)
  setattr(sys, streamName, six.StringIO())
  try:
    yield getattr(sys, streamName)
  finally:
    setattr(sys, streamName, origStdout)


def capturedStdout():
  """Capture the output of sys.stdout:

    with capturedStdout() as stdout:
      print("hello")
    self.assertEqual(stdout.getvalue(), "hello\n")
  """
  return capturedOutput("stdout")


def capturedStderr():
  """Capture the output of sys.stderr:

    with capturedStderr() as stderr:
      print("hello", file=sys.stderr)
    self.assertEqual(stderr.getvalue(), "hello\n")
  """
  return capturedOutput("stderr")


def capturedStdin():
  """Capture the input to sys.stdin:

    with capturedStdin() as stdin:
      stdin.write('hello\n')
      stdin.seek(0)
      # call test code that consumes from sys.stdin
      captured = input()
    self.assertEqual(captured, "hello")
  """
  return capturedOutput("stdin")


def resetWarningRegistry():
  """
  Clear warning registry for all modules. This is required in some tests
  because of a bug in Python that prevents warnings.simplefilter("always")
  from always making warnings appear: http://bugs.python.org/issue4180

  The bug was fixed in Python 3.4.2.
  """
  key = "__warningregistry__"
  for mod in sys.modules.values():
    if hasattr(mod, key):
      getattr(mod, key).clear()


@contextmanager
def freezeTime(t):
  """
  Context manager to temporarily freeze time.time(). This temporarily
  modifies the time function of the time module. Modules which import the
  time function directly (e.g. `from time import time`) won't be affected
  This isn't meant as a public API, but helps reduce some repetitive code in
  Django's test suite.
  """
  _real_time = time.time
  time.time = lambda: t
  try:
    yield
  finally:
    time.time = _real_time


def requireJinja2(testFunc):
  """
  Decorator to enable a Jinja2 template engine in addition to the regular
  Django template engine for a test or skip it if Jinja2 isn't available.
  """
  testFunc = skipIf(jinja2 is None, "this test requires jinja2")(testFunc)
  testFunc = overrideSettings(TEMPLATES=[{
    'BACKEND': 'django.template.backends.django.DjangoTemplates',
    'APP_DIRS': True,
  }, {
    'BACKEND': 'django.template.backends.jinja2.Jinja2',
    'APP_DIRS': True,
    'OPTIONS': {'keepTrailingNewline': True},
  }])(testFunc)
  return testFunc


#class overrideScriptPrefix(TestContextDecorator):
#  """
#  Decorator or context manager to temporary override the script prefix.
#  """
#  def __init__(self, prefix):
#    self.prefix = prefix
#    super(overrideScriptPrefix, self).__init__()
#
#  def enable(self):
#    self.oldPrefix = getScriptPrefix()
#    setScriptPrefix(self.prefix)
#
#  def disable(self):
#    setScriptPrefix(self.oldPrefix)


class LoggingCaptureMixin(object):
  """
  Capture the output from the 'django' logger and store it on the class's
  loggerOutput attribute.
  """
  def setUp(self):
    self.logger = logging.getLogger('django')
    self.oldStream = self.logger.handlers[0].stream
    self.loggerOutput = six.StringIO()
    self.logger.handlers[0].stream = self.loggerOutput

  def tearDown(self):
    self.logger.handlers[0].stream = self.oldStream


class isolateApps(TestContextDecorator):
  """
  Act as either a decorator or a context manager to register models defined
  in its wrapped context to an isolated registry.

  The list of installed apps the isolated registry should contain must be
  passed as arguments.

  Two optional keyword arguments can be specified:

  `attrName`: attribute assigned the isolated registry if used as a class
         decorator.

  `kwargName`: keyword argument passing the isolated registry if used as a
         function decorator.
  """

  def __init__(self, *installedApps, **kwargs):
    self.installedApps = installedApps
    super(isolateApps, self).__init__(**kwargs)

  def enable(self):
    self.oldApps = Options.defaultApps
    apps = Apps(self.installedApps)
    setattr(Options, 'defaultApps', apps)
    return apps

  def disable(self):
    setattr(Options, 'defaultApps', self.oldApps)


def tag(*tagLst):
  """
  Decorator to add tagLst to a test class or method.
  """
  def decorator(obj):
    setattr(obj, 'tagLst', set(tagLst))
    return obj
  return decorator

class ObjectDumper(object):
  def __init__(self, includeTermLst=[], excludeTermLst=[], absorbTermLst=[]):
    self.includeTermLst = includeTermLst
    self.excludeTermLst = excludeTermLst
    self.absorbTermSet = set(absorbTermLst)
    if(len(self.includeTermLst)==0):
      self._filterFxn = self._filterByExcludeTerm
    else:
      self._filterFxn = self._filterByIncludeTerm

  def _filterFxn(self, key):
    pass

  def _filterByIncludeTerm(self, key):
    return key in self.includeTermLst

  def _filterByExcludeTerm(self, key):
    return key not in self.excludeTermLst

  def filterNestedDict(self, node):
    if isinstance(node, list):
      r = []
      for i in node:
        r.append(self.filterNestedDict(i))
      return r
    elif isinstance(node, dict):
      r = {}
      nodeKeySet = set((node.keys()))
      intersetAbsorbTermSet = nodeKeySet.intersection(self.absorbTermSet)
      if(
          len(nodeKeySet)==1
          and len(self.absorbTermSet)>0
          and self.absorbTermSet.issubset(nodeKeySet)
          ):
        loopFxn = node[intersetAbsorbTermSet.pop()].items
      else:
        loopFxn = node.items
      for key, val in loopFxn():
        if(self._filterFxn(key)):
          curNode = self.filterNestedDict(val)
          if curNode is not None:
            r[key] = curNode
      return r or None
    else:
      return node

  def jsonifyObjToStr(self, obj):
    """Return a str in JSON format from a given object. Feel free to override
    this fxn if necessary."""
    TheoryTestEncoder.includeTermLst = self.includeTermLst
    TheoryTestEncoder.excludeTermLst = self.excludeTermLst
    return json.dumps(
        obj,
        cls=TheoryTestEncoder,
        indent=2,
        )

  def cleanupJsonifyObj(self, obj):
    return self.filterNestedDict(
        obj,
        )

class ObjectComparator(object):
  def __init__(self, objectDumper):
    self.objectDumper = objectDumper

  def _convertObjToJson(self, obj):
    objInStr = self.objectDumper.jsonifyObjToStr(obj)
    return self.objectDumper.cleanupJsonifyObj(json.loads(objInStr))

  def _convertObjToStr(self, obj):
    return json.dumps(self._convertObjToJson(obj), indent=2, sort_keys=True)

  def _getFilePathForTestcase(self, testFilePath, testFxnName):
    path, filename = os.path.split(testFilePath)
    filename = filename.split(".")[0]
    path = os.path.join(
        os.path.dirname(path),
        "files",
        filename,
        )
    if not os.path.exists(path):
      os.makedirs(path)
    return os.path.join(path, testFxnName)

  def compare(self, testFilePath, testFxnName, obj):
    """
    :param testFilePath: The file path of test file, get it from "__file__"
    :type testFilePath: String
    :param testFxnName: The test function name, get it from
                        "self._testMethodName"
    :type testFxnName: String
    :param obj: The object being compared"
    :type obj: Python Object
    """
    sampleFilePath = self._getFilePathForTestcase(testFilePath, testFxnName)
    with open(sampleFilePath, "r") as fd:
      sampledDataInJson = json.loads(fd.read())
    objInJson = self._convertObjToJson(obj)

    diff1 = JsonDiff(sampledDataInJson, objInJson, True).difference
    diff2 = JsonDiff(objInJson, sampledDataInJson, False).difference
    diffs = []
    for type, message in diff1:
      newType = 'CHANGED'
      if type == JsonDiff.PATH:
        newType = 'REMOVED'
      diffs.append({'type': newType, 'message': message})
    for type, message in diff2:
      diffs.append({'type': 'ADDED', 'message': message})
    return diffs

  def serializeSample(self, testFilePath, testFxnName, obj):
    """
    :param testFilePath: The file path of test file, get it from "__file__"
    :type testFilePath: String
    :param testFxnName: The test function name, get it from
                        "self._testMethodName"
    :type testFxnName: String
    :param obj: The object being serialized"
    :type obj: Python Object
    """
    sampleFilePath = self._getFilePathForTestcase(testFilePath, testFxnName)
    with open(sampleFilePath, "w") as fd:
      fd.write(self._convertObjToStr(obj))



