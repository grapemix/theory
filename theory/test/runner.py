import ipdb
from importlib import import_module
import os
import unittest
from unittest import TestSuite, defaultTestLoader

from theory.conf import settings
from theory.core.exceptions import ImproperlyConfigured
from theory.db import connections, DEFAULT_DB_ALIAS
from theory.test import SimpleTestCase, TestCase
from theory.test.util import setupTestEnvironment, teardownTestEnvironment


class DiscoverRunner(object):
  """
  A Theory test runner that uses unittest2 test discovery.
  """

  testSuite = TestSuite
  testRunner = unittest.TextTestRunner
  testLoader = defaultTestLoader
  reorderBy = (TestCase, SimpleTestCase)

  def __init__(self, pattern=None, topLevel=None,
         verbosity=1, interactive=True, failfast=False, keepdb=False,
         **kwargs):

    self.pattern = pattern
    self.topLevel = topLevel

    self.verbosity = verbosity
    self.interactive = interactive
    self.failfast = failfast
    self.keepdb = keepdb

  @classmethod
  def addArguments(cls, parser):
    parser.addArgument('-t', '--top-level-directory',
      action='store', dest='topLevel', default=None,
      help='Top level of project for unittest discovery.')
    parser.addArgument('-p', '--pattern', action='store', dest='pattern',
      default="test*.py",
      help='The test matching pattern. Defaults to test*.py.')
    parser.addArgument('-k', '--keepdb', action='storeTrue', dest='keepdb',
      default=False,
      help='Preserve the test DB between runs. Defaults to False')

  def setupTestEnvironment(self, **kwargs):
    setupTestEnvironment()
    settings.DEBUG = False
    unittest.installHandler()

  def buildSuite(self, testLabels=None, extraTests=None, **kwargs):
    suite = self.testSuite()
    testLabels = testLabels or ['.']
    extraTests = extraTests or []

    discoverKwargs = {}
    if self.pattern is not None:
      discoverKwargs['pattern'] = self.pattern
    if self.topLevel is not None:
      discoverKwargs['topLevelDir'] = self.topLevel

    for label in testLabels:
      kwargs = discoverKwargs.copy()
      tests = None

      labelAsPath = os.path.abspath(label)

      # if a module, or "module.ClassName[.methodName]", just run those
      if not os.path.exists(labelAsPath):
        tests = self.testLoader.loadTestsFromName(label)
      elif os.path.isdir(labelAsPath) and not self.topLevel:
        # Try to be a bit smarter than unittest about finding the
        # default top-level for a given directory path, to avoid
        # breaking relative imports. (Unittest's default is to set
        # top-level equal to the path, which means relative imports
        # will result in "Attempted relative import in non-package.").

        # We'd be happy to skip this and require dotted module paths
        # (which don't cause this problem) instead of file paths (which
        # do), but in the case of a directory in the cwd, which would
        # be equally valid if considered as a top-level module or as a
        # directory path, unittest unfortunately prefers the latter.

        topLevel = labelAsPath
        while True:
          initPy = os.path.join(topLevel, '__init__.py')
          if os.path.exists(initPy):
            tryNext = os.path.dirname(topLevel)
            if tryNext == topLevel:
              # __init__.py all the way down? give up.
              break
            topLevel = tryNext
            continue
          break
        kwargs['topLevelDir'] = topLevel

      if not (tests and tests.countTestCases()) and isDiscoverable(label):
        if kwargs.has_key("topLevelDir"):
          kwargs["top_level_dir"] = kwargs["topLevelDir"]
          del kwargs["topLevelDir"]
        # Try discovery if path is a package or directory
        tests = self.testLoader.discover(start_dir=label, **kwargs)

        # Make unittest forget the top-level dir it calculated from this
        # run, to support running tests from two different top-levels.
        self.testLoader._topLevelDir = None

      suite.addTests(tests)

    for test in extraTests:
      suite.addTest(test)

    return reorderSuite(suite, self.reorderBy)

  def setupDatabases(self, **kwargs):
    return setupDatabases(self.verbosity, self.interactive, self.keepdb, **kwargs)

  def runSuite(self, suite, **kwargs):
    return self.testRunner(
      verbosity=self.verbosity,
      failfast=self.failfast,
    ).run(suite)

  def teardownDatabases(self, oldConfig, **kwargs):
    """
    Destroys all the non-mirror databases.
    """
    oldNames, mirrors = oldConfig
    for connection, oldName, destroy in oldNames:
      if destroy:
        connection.creation.destroyTestDb(
            oldName,
            self.verbosity,
            #self.keepdb
            )

  def teardownTestEnvironment(self, **kwargs):
    unittest.removeHandler()
    teardownTestEnvironment()

  def suiteResult(self, suite, result, **kwargs):
    return len(result.failures) + len(result.errors)

  def runTests(self, testLabels, extraTests=None, **kwargs):
    """
    Run the unit tests for all the test labels in the provided list.

    Test labels should be dotted Python paths to test modules, test
    classes, or test methods.

    A list of 'extra' tests may also be provided; these tests
    will be added to the test suite.

    Returns the number of tests that failed.
    """
    self.setupTestEnvironment()
    suite = self.buildSuite(testLabels, extraTests)
    oldConfig = self.setupDatabases()
    result = self.runSuite(suite)
    self.teardownDatabases(oldConfig)
    self.teardownTestEnvironment()

    # We have to add this line
    oldConfig[0][0][0].settingsDict["NAME"] = oldConfig[0][0][1]
    return self.suiteResult(suite, result)


def isDiscoverable(label):
  """
  Check if a test label points to a python package or file directory.

  Relative labels like "." and ".." are seen as directories.
  """
  try:
    mod = import_module(label)
  except (ImportError, TypeError):
    pass
  else:
    return hasattr(mod, '__path__')

  return os.path.isdir(os.path.abspath(label))


def dependencyOrdered(testDatabases, dependencies):
  """
  Reorder testDatabases into an order that honors the dependencies
  described in TEST[DEPENDENCIES].
  """
  orderedTestDatabases = []
  resolvedDatabases = set()

  # Maps db signature to dependencies of all it's aliases
  dependenciesMap = {}

  # sanity check - no DB can depend on its own alias
  for sig, (_, aliases) in testDatabases:
    allDeps = set()
    for alias in aliases:
      allDeps.update(dependencies.get(alias, []))
    if not allDeps.isdisjoint(aliases):
      raise ImproperlyConfigured(
        "Circular dependency: databases %r depend on each other, "
        "but are aliases." % aliases)
    dependenciesMap[sig] = allDeps

  while testDatabases:
    changed = False
    deferred = []

    # Try to find a DB that has all it's dependencies met
    for signature, (dbName, aliases) in testDatabases:
      if dependenciesMap[signature].issubset(resolvedDatabases):
        resolvedDatabases.update(aliases)
        orderedTestDatabases.append((signature, (dbName, aliases)))
        changed = True
      else:
        deferred.append((signature, (dbName, aliases)))

    if not changed:
      raise ImproperlyConfigured(
        "Circular dependency in TEST[DEPENDENCIES]")
    testDatabases = deferred
  return orderedTestDatabases


def reorderSuite(suite, classes):
  """
  Reorders a test suite by test type.

  `classes` is a sequence of types

  All tests of type classes[0] are placed first, then tests of type
  classes[1], etc. Tests with no match in classes are placed last.
  """
  classCount = len(classes)
  suiteClass = type(suite)
  bins = [suiteClass() for i in range(classCount + 1)]
  partitionSuite(suite, classes, bins)
  for i in range(classCount):
    bins[0].addTests(bins[i + 1])
  return bins[0]


def partitionSuite(suite, classes, bins):
  """
  Partitions a test suite by test type.

  classes is a sequence of types
  bins is a sequence of TestSuites, one more than classes

  Tests of type classes[i] are added to bins[i],
  tests with no match found in classes are place in bins[-1]
  """
  suiteClass = type(suite)
  for test in suite:
    if isinstance(test, suiteClass):
      partitionSuite(test, classes, bins)
    else:
      for i in range(len(classes)):
        if isinstance(test, classes[i]):
          bins[i].addTest(test)
          break
      else:
        bins[-1].addTest(test)


def setupDatabases(verbosity, interactive, keepdb=False, **kwargs):
  # First pass -- work out which databases actually need to be created,
  # and which ones are test mirrors or duplicate entries in DATABASES
  mirroredAliases = {}
  testDatabases = {}
  dependencies = {}
  defaultSig = connections[DEFAULT_DB_ALIAS].creation.testDbSignature()
  for alias in connections:
    connection = connections[alias]
    testSettings = connection.settingsDict['TEST']
    if testSettings['MIRROR']:
      # If the database is marked as a test mirror, save
      # the alias.
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

  # Second pass -- actually create the databases.
  oldNames = []
  mirrors = []

  for signature, (dbName, aliases) in dependencyOrdered(
      testDatabases.items(), dependencies):
    testDbName = None
    # Actually create the database for the first connection
    for alias in aliases:
      connection = connections[alias]
      if testDbName is None:
        testDbName = connection.creation.createTestDb(
          verbosity,
          autoclobber=not interactive,
          #keepdb=keepdb,
          serialize=connection.settingsDict.get("TEST_SERIALIZE", True),
        )
        destroy = True
      else:
        connection.settingsDict['NAME'] = testDbName
        destroy = False
      oldNames.append((connection, dbName, destroy))

  for alias, mirrorAlias in mirroredAliases.items():
    mirrors.append((alias, connections[alias].settingsDict['NAME']))
    connections[alias].settingsDict['NAME'] = (
      connections[mirrorAlias].settingsDict['NAME'])

  return oldNames, mirrors
