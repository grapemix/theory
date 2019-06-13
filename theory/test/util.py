from contextlib import contextmanager
import logging
import re
import sys
import time
from unittest import skipUnless
import warnings
from functools import wraps
from xml.dom.minidom import parseString, Node

from theory.apps import apps
from theory.conf import settings, UserSettingsHolder
from theory.core.signals import requestStarted
from theory.db import resetQueries
from theory.test.signals import templateRendered, settingChanged
from theory.utils import six
from theory.utils.deprecation import RemovedInTheory19Warning, RemovedInTheory20Warning
from theory.utils.encoding import forceStr
from theory.utils.translation import deactivate


__all__ = (
  'Approximate', 'ContextList', 'getRunner',
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

def setupTestEnvironment():
  """Perform any global pre-test setup. This involves:

    - Set the email backend to the locmem email backend.
    - Setting the active locale to match the LANGUAGE_CODE setting.
  """
  # Storing previous values in the settings module itself is problematic.
  # Store them in arbitrary (but related) modules instead. See #20636.

  deactivate()


def teardownTestEnvironment():
  """Perform any global post-test teardown. This involves:
  """
  pass

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

class overrideSettings(object):
  """
  Acts as either a decorator, or a context manager. If it's a decorator it
  takes a function and returns a wrapped function. If it's a contextmanager
  it's used with the ``with`` statement. In either event entering/exiting
  are called before and after, respectively, the function/block is executed.
  """
  def __init__(self, **kwargs):
    self.options = kwargs

  def __enter__(self):
    self.enable()

  def __exit__(self, excType, excValue, traceback):
    self.disable()

  def __call__(self, testFunc):
    from theory.test import SimpleTestCase
    if isinstance(testFunc, type):
      if not issubclass(testFunc, SimpleTestCase):
        raise Exception(
          "Only subclasses of Theory SimpleTestCase can be decorated "
          "with overrideSettings")
      self.saveOptions(testFunc)
      return testFunc
    else:
      @wraps(testFunc)
      def inner(*args, **kwargs):
        with self:
          return testFunc(*args, **kwargs)
    return inner

  def saveOptions(self, testFunc):
    if testFunc._overriddenSettings is None:
      testFunc._overriddenSettings = self.options
    else:
      # Duplicate dict to prevent subclasses from altering their parent.
      testFunc._overriddenSettings = dict(
        testFunc._overriddenSettings, **self.options)

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


class modifySettings(overrideSettings):
  """
  Like overrideSettings, but makes it possible to append, prepend or remove
  items instead of redefining the entire list.
  """
  def __init__(self, *args, **kwargs):
    if args:
      # Hack used when instantiating from SimpleTestCase._preSetup.
      assert not kwargs
      self.operations = args[0]
    else:
      assert not args
      self.operations = list(kwargs.items())

  def saveOptions(self, testFunc):
    if testFunc._modifiedSettings is None:
      testFunc._modifiedSettings = self.operations
    else:
      # Duplicate list to prevent subclasses from altering their parent.
      testFunc._modifiedSettings = list(
        testFunc._modifiedSettings) + self.operations

  def enable(self):
    self.options = {}
    for name, operations in self.operations:
      try:
        # When called from SimpleTestCase._preSetup, values may be
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


def overrideSystemChecks(newChecks):
  """ Acts as a decorator. Overrides list of registered system checks.
  Useful when you override `INSTALLED_APPS`, e.g. if you exclude `auth` app,
  you also need to exclude its system checks. """

  from theory.core.checks.registry import registry

  def outer(testFunc):
    @wraps(testFunc)
    def inner(*args, **kwargs):
      oldChecks = registry.registeredChecks
      registry.registeredChecks = newChecks
      try:
        return testFunc(*args, **kwargs)
      finally:
        registry.registeredChecks = oldChecks
    return inner
  return outer


def compareXml(want, got):
  """Tries to do a 'xml-comparison' of want and got.  Plain string
  comparison doesn't always work because, for example, attribute
  ordering should not be important. Comment nodes are not considered in the
  comparison.

  Based on http://codespeak.net/svn/lxml/trunk/src/lxml/doctestcompare.py
  """
  _normWhitespaceRe = re.compile(r'[ \t\n][ \t\n]+')

  def normWhitespace(v):
    return _normWhitespaceRe.sub(' ', v)

  def childText(element):
    return ''.join([c.data for c in element.childNodes
            if c.nodeType == Node.TEXT_NODE])

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
  want = want.replace('\\n', '\n')
  got = got.replace('\\n', '\n')

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
    return (len(s) >= 2
        and s[0] == s[-1]
        and s[0] in ('"', "'"))

  def isQuotedUnicode(s):
    s = s.strip()
    return (len(s) >= 3
        and s[0] == 'u'
        and s[1] == s[-1]
        and s[1] in ('"', "'"))

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
    self.useDebugCursor = self.connection.useDebugCursor
    self.connection.useDebugCursor = True
    self.initialQueries = len(self.connection.queriesLog)
    self.finalQueries = None
    requestStarted.disconnect(resetQueries)
    return self

  def __exit__(self, excType, excValue, traceback):
    self.connection.useDebugCursor = self.useDebugCursor
    requestStarted.connect(resetQueries)
    if excType is not None:
      return
    self.finalQueries = len(self.connection.queriesLog)


class IgnoreDeprecationWarningsMixin(object):
  warningClasses = [RemovedInTheory19Warning]

  def setUp(self):
    super(IgnoreDeprecationWarningsMixin, self).setUp()
    self.catchWarnings = warnings.catchWarnings()
    self.catchWarnings.__enter__()
    for warningClass in self.warningClasses:
      warnings.filterwarnings("ignore", category=warningClass)

  def tearDown(self):
    self.catchWarnings.__exit__(*sys.excInfo())
    super(IgnoreDeprecationWarningsMixin, self).tearDown()


class IgnorePendingDeprecationWarningsMixin(IgnoreDeprecationWarningsMixin):
    warningClasses = [RemovedInTheory20Warning]


class IgnoreAllDeprecationWarningsMixin(IgnoreDeprecationWarningsMixin):
    warningClasses = [RemovedInTheory20Warning, RemovedInTheory19Warning]


@contextmanager
def patchLogger(loggerName, logLevel):
  """
  Context manager that takes a named logger and the logging level
  and provides a simple mock-like list of messages received
  """
  calls = []

  def replacement(msg, *args, **kwargs):
    calls.append(msg % args)
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

requiresTzSupport = skipUnless(TZ_SUPPORT,
    "This test relies on the ability to run a program in an arbitrary "
    "time zone, but your operating system isn't able to do that.")


@contextmanager
def extendSysPath(*paths):
  """Context manager to temporarily add paths to sys.path."""
  _origSysPath = sys.path[:]
  sys.path.extend(paths)
  try:
    yield
  finally:
    sys.path = _origSysPath

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
          cur_node = self.filterNestedDict(val)
          if cur_node is not None:
            r[key] = cur_node
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
