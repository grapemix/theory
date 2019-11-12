import ctypes
import itertools
import logging
import multiprocessing
import os
import pickle
import textwrap
import unittest
import warnings
from importlib import import_module

#from theory.core.management import callCommand
from theory.db import connections
from theory.test import SimpleTestCase, TestCase
from theory.test.util import (
  setupDatabases as _setupDatabases, setupTestEnvironment,
  teardownDatabases as _teardownDatabases, teardownTestEnvironment,
)
from theory.utils.datastructures import OrderedSet
from theory.utils.deprecation import RemovedInTheory20Warning
from theory.utils.six import StringIO

try:
  import tblib.pickling_support
except ImportError:
  tblib = None


class DebugSQLTextTestResult(unittest.TextTestResult):
  def __init__(self, stream, descriptions, verbosity):
    self.logger = logging.getLogger('django.db.backends')
    self.logger.setLevel(logging.DEBUG)
    super(DebugSQLTextTestResult, self).__init__(stream, descriptions, verbosity)

  def startTest(self, test):
    self.debugSqlStream = StringIO()
    self.handler = logging.StreamHandler(self.debugSqlStream)
    self.logger.addHandler(self.handler)
    super(DebugSQLTextTestResult, self).startTest(test)

  def stopTest(self, test):
    super(DebugSQLTextTestResult, self).stopTest(test)
    self.logger.removeHandler(self.handler)
    if self.showAll:
      self.debugSqlStream.seek(0)
      self.stream.write(self.debugSqlStream.read())
      self.stream.writeln(self.separator2)

  def addError(self, test, err):
    super(DebugSQLTextTestResult, self).addError(test, err)
    self.debugSqlStream.seek(0)
    self.errors[-1] = self.errors[-1] + (self.debugSqlStream.read(),)

  def addFailure(self, test, err):
    super(DebugSQLTextTestResult, self).addFailure(test, err)
    self.debugSqlStream.seek(0)
    self.failures[-1] = self.failures[-1] + (self.debugSqlStream.read(),)

  def printErrorList(self, flavour, errors):
    for test, err, sqlDebug in errors:
      self.stream.writeln(self.separator1)
      self.stream.writeln("%s: %s" % (flavour, self.getDescription(test)))
      self.stream.writeln(self.separator2)
      self.stream.writeln("%s" % err)
      self.stream.writeln(self.separator2)
      self.stream.writeln("%s" % sqlDebug)


class RemoteTestResult(object):
  """
  Record information about which tests have succeeded and which have failed.

  The sole purpose of this class is to record events in the child processes
  so they can be replayed in the master process. As a consequence it doesn't
  inherit unittest.TestResult and doesn't attempt to implement all its API.

  The implementation matches the unpythonic coding style of unittest2.
  """

  def __init__(self):
    if tblib is not None:
      tblib.pickling_support.install()

    self.events = []
    self.failfast = False
    self.shouldStop = False
    self.testsRun = 0

  @property
  def testIndex(self):
    return self.testsRun - 1

  def _confirmPicklable(self, obj):
    """
    Confirm that obj can be pickled and unpickled as multiprocessing will
    need to pickle the exception in the child process and unpickle it in
    the parent process. Let the exception rise, if not.
    """
    pickle.loads(pickle.dumps(obj))

  def _printUnpicklableSubtest(self, test, subtest, pickleExc):
    print("""
Subtest failed:

  test: {}
 subtest: {}

Unfortunately, the subtest that failed cannot be pickled, so the parallel
test runner cannot handle it cleanly. Here is the pickling error:

> {}

You should re-run this test with --parallel=1 to reproduce the failure
with a cleaner failure message.
""".format(test, subtest, pickleExc))

  def checkPicklable(self, test, err):
    # Ensure that sys.exc_info() tuples are picklable. This displays a
    # clear multiprocessing.pool.RemoteTraceback generated in the child
    # process instead of a multiprocessing.pool.MaybeEncodingError, making
    # the root cause easier to figure out for users who aren't familiar
    # with the multiprocessing module. Since we're in a forked process,
    # our best chance to communicate with them is to print to stdout.
    try:
      self._confirmPicklable(err)
    except Exception as exc:
      originalExcTxt = repr(err[1])
      originalExcTxt = textwrap.fill(originalExcTxt, 75, initialIndent='  ', subsequentIndent='  ')
      pickleExcTxt = repr(exc)
      pickleExcTxt = textwrap.fill(pickleExcTxt, 75, initialIndent='  ', subsequentIndent='  ')
      if tblib is None:
        print("""

{} failed:

{}

Unfortunately, tracebacks cannot be pickled, making it impossible for the
parallel test runner to handle this exception cleanly.

In order to see the traceback, you should install tblib:

  pip install tblib
""".format(test, originalExcTxt))
      else:
        print("""

{} failed:

{}

Unfortunately, the exception it raised cannot be pickled, making it impossible
for the parallel test runner to handle it cleanly.

Here's the error encountered while trying to pickle the exception:

{}

You should re-run this test with the --parallel=1 option to reproduce the
failure and get a correct traceback.
""".format(test, originalExcTxt, pickleExcTxt))
      raise

  def checkSubtestPicklable(self, test, subtest):
    try:
      self._confirmPicklable(subtest)
    except Exception as exc:
      self._printUnpicklableSubtest(test, subtest, exc)
      raise

  def stopIfFailfast(self):
    if self.failfast:
      self.stop()

  def stop(self):
    self.shouldStop = True

  def startTestRun(self):
    self.events.append(('startTestRun',))

  def stopTestRun(self):
    self.events.append(('stopTestRun',))

  def startTest(self, test):
    self.testsRun += 1
    self.events.append(('startTest', self.testIndex))

  def stopTest(self, test):
    self.events.append(('stopTest', self.testIndex))

  def addError(self, test, err):
    self.checkPicklable(test, err)
    self.events.append(('addError', self.testIndex, err))
    self.stopIfFailfast()

  def addFailure(self, test, err):
    self.checkPicklable(test, err)
    self.events.append(('addFailure', self.testIndex, err))
    self.stopIfFailfast()

  def addSubTest(self, test, subtest, err):
    # Follow Python 3.5's implementation of unittest.TestResult.addSubTest()
    # by not doing anything when a subtest is successful.
    if err is not None:
      # Call checkPicklable() before checkSubtestPicklable() since
      # checkPicklable() performs the tblib check.
      self.checkPicklable(test, err)
      self.checkSubtestPicklable(test, subtest)
      self.events.append(('addSubTest', self.testIndex, subtest, err))
      self.stopIfFailfast()

  def addSuccess(self, test):
    self.events.append(('addSuccess', self.testIndex))

  def addSkip(self, test, reason):
    self.events.append(('addSkip', self.testIndex, reason))

  def addExpectedFailure(self, test, err):
    # If tblib isn't installed, pickling the traceback will always fail.
    # However we don't want tblib to be required for running the tests
    # when they pass or fail as expected. Drop the traceback when an
    # expected failure occurs.
    if tblib is None:
      err = err[0], err[1], None
    self.checkPicklable(test, err)
    self.events.append(('addExpectedFailure', self.testIndex, err))

  def addUnexpectedSuccess(self, test):
    self.events.append(('addUnexpectedSuccess', self.testIndex))
    self.stopIfFailfast()


class RemoteTestRunner(object):
  """
  Run tests and record everything but don't display anything.

  The implementation matches the unpythonic coding style of unittest2.
  """

  resultclass = RemoteTestResult

  def __init__(self, failfast=False, resultclass=None):
    self.failfast = failfast
    if resultclass is not None:
      self.resultclass = resultclass

  def run(self, test):
    result = self.resultclass()
    unittest.registerResult(result)
    result.failfast = self.failfast
    test(result)
    return result


def defaultTestProcesses():
  """
  Default number of test processes when using the --parallel option.
  """
  # The current implementation of the parallel test runner requires
  # multiprocessing to start subprocesses with fork().
  # On Python 3.4+: if multiprocessing.get_start_method() != 'fork':
  if not hasattr(os, 'fork'):
    return 1
  try:
    return int(os.environ['THEORY_TEST_PROCESSES'])
  except KeyError:
    return multiprocessing.cpu_count()


_workerId = 0


def _initWorker(counter):
  """
  Switch to databases dedicated to this worker.

  This helper lives at module-level because of the multiprocessing module's
  requirements.
  """

  global _workerId

  with counter.getLock():
    counter.value += 1
    _workerId = counter.value

  for alias in connections:
    connection = connections[alias]
    settingsDict = connection.creation.getTestDbCloneSettings(_workerId)
    # connection.settingsDict must be updated in place for changes to be
    # reflected in django.db.connections. If the following line assigned
    # connection.settingsDict = settingsDict, new threads would connect
    # to the default database instead of the appropriate clone.
    connection.settingsDict.update(settingsDict)
    connection.close()


def _runSubsuite(args):
  """
  Run a suite of tests with a RemoteTestRunner and return a RemoteTestResult.

  This helper lives at module-level and its arguments are wrapped in a tuple
  because of the multiprocessing module's requirements.
  """
  runnerClass, subsuiteIndex, subsuite, failfast = args
  runner = runnerClass(failfast=failfast)
  result = runner.run(subsuite)
  return subsuiteIndex, result.events


class ParallelTestSuite(unittest.TestSuite):
  """
  Run a series of tests in parallel in several processes.

  While the unittest module's documentation implies that orchestrating the
  execution of tests is the responsibility of the test runner, in practice,
  it appears that TestRunner classes are more concerned with formatting and
  displaying test results.

  Since there are fewer use cases for customizing TestSuite than TestRunner,
  implementing parallelization at the level of the TestSuite improves
  interoperability with existing custom test runners. A single instance of a
  test runner can still collect results from all tests without being aware
  that they have been run in parallel.
  """

  # In case someone wants to modify these in a subclass.
  initWorker = _initWorker
  runSubsuite = _runSubsuite
  runnerClass = RemoteTestRunner

  def __init__(self, suite, processes, failfast=False):
    self.subsuites = partitionSuiteByCase(suite)
    self.processes = processes
    self.failfast = failfast
    super(ParallelTestSuite, self).__init__()

  def run(self, result):
    """
    Distribute test cases across workers.

    Return an identifier of each test case with its result in order to use
    imap_unordered to show results as soon as they're available.

    To minimize pickling errors when getting results from workers:

    - pass back numeric indexes in self.subsuites instead of tests
    - make tracebacks picklable with tblib, if available

    Even with tblib, errors may still occur for dynamically created
    exception classes such Model.DoesNotExist which cannot be unpickled.
    """
    counter = multiprocessing.Value(ctypes.c_int, 0)
    pool = multiprocessing.Pool(
      processes=self.processes,
      initializer=self.initWorker.__func__,
      initargs=[counter])
    args = [
      (self.runnerClass, index, subsuite, self.failfast)
      for index, subsuite in enumerate(self.subsuites)
    ]
    testResults = pool.imap_unordered(self.runSubsuite.__func__, args)

    while True:
      if result.shouldStop:
        pool.terminate()
        break

      try:
        subsuiteIndex, events = testResults.next(timeout=0.1)
      except multiprocessing.TimeoutError:
        continue
      except StopIteration:
        pool.close()
        break

      tests = list(self.subsuites[subsuiteIndex])
      for event in events:
        eventName = event[0]
        handler = getattr(result, eventName, None)
        if handler is None:
          continue
        test = tests[event[1]]
        args = event[2:]
        handler(test, *args)

    pool.join()

    return result


class DiscoverRunner(object):
  """
  A Django test runner that uses unittest2 test discovery.
  """

  testSuite = unittest.TestSuite
  parallelTestSuite = ParallelTestSuite
  testRunner = unittest.TextTestRunner
  testLoader = unittest.defaultTestLoader
  reorderBy = (TestCase, SimpleTestCase)

  def __init__(self, pattern=None, topLevel=None, verbosity=1,
         interactive=True, failfast=False, keepdb=False,
         reverse=False, debugMode=False, debugSql=False, parallel=0,
         tagLst=None, excludeTagLst=None, **kwargs):

    self.pattern = pattern
    self.topLevel = topLevel
    self.verbosity = verbosity
    self.interactive = interactive
    self.failfast = failfast
    self.keepdb = keepdb
    self.reverse = reverse
    self.debugMode = debugMode
    self.debugSql = debugSql
    self.parallel = parallel
    self.tagLst = set(tagLst or [])
    self.excludeTagLst = set(excludeTagLst or [])

  @classmethod
  def addArguments(cls, parser):
    parser.addArgument(
      '-t', '--top-level-directory', action='store', dest='topLevel', default=None,
      help='Top level of project for unittest discovery.',
    )
    parser.addArgument(
      '-p', '--pattern', action='store', dest='pattern', default="test*.py",
      help='The test matching pattern. Defaults to test*.py.',
    )
    parser.addArgument(
      '-k', '--keepdb', action='storeTrue', dest='keepdb', default=False,
      help='Preserves the test DB between runs.'
    )
    parser.addArgument(
      '-r', '--reverse', action='storeTrue', dest='reverse', default=False,
      help='Reverses test cases order.',
    )
    parser.addArgument(
      '--debug-mode', action='storeTrue', dest='debugMode', default=False,
      help='Sets settings.DEBUG to True.',
    )
    parser.addArgument(
      '-d', '--debug-sql', action='storeTrue', dest='debugSql', default=False,
      help='Prints logged SQL queries on failure.',
    )
    parser.addArgument(
      '--parallel', dest='parallel', nargs='?', default=1, type=int,
      const=defaultTestProcesses(), metavar='N',
      help='Run tests using up to N parallel processes.',
    )
    parser.addArgument(
      '--tag', action='append', dest='tagLst',
      help='Run only tests with the specified tag. Can be used multiple times.',
    )
    parser.addArgument(
      '--exclude-tag', action='append', dest='excludeTagLst',
      help='Do not run tests with the specified tag. Can be used multiple times.',
    )

  def setupTestEnvironment(self, **kwargs):
    setupTestEnvironment(debug=self.debugMode)
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
        # Try discovery if path is a package or directory
        tests = self.testLoader.discover(start_dir=label, **kwargs)

        # Make unittest forget the top-level dir it calculated from this
        # run, to support running tests from two different top-levels.
        self.testLoader._topLevelDir = None

      suite.addTests(tests)

    for test in extraTests:
      suite.addTest(test)

    if self.tagLst or self.excludeTagLst:
      suite = filterTestsByTags(suite, self.tagLst, self.excludeTagLst)
    suite = reorderSuite(suite, self.reorderBy, self.reverse)

    if self.parallel > 1:
      parallelSuite = self.parallelTestSuite(suite, self.parallel, self.failfast)

      # Since tests are distributed across processes on a per-TestCase
      # basis, there's no need for more processes than TestCases.
      parallelUnits = len(parallelSuite.subsuites)
      if self.parallel > parallelUnits:
        self.parallel = parallelUnits

      # If there's only one TestCase, parallelization isn't needed.
      if self.parallel > 1:
        suite = parallelSuite

    return suite

  def setupDatabases(self, **kwargs):
    return _setupDatabases(
      self.verbosity, self.interactive, self.keepdb, self.debugSql,
      self.parallel, **kwargs
    )

  def getResultclass(self):
    return DebugSQLTextTestResult if self.debugSql else None

  def getTestRunnerKwargs(self):
    return {
      'failfast': self.failfast,
      'resultclass': self.getResultclass(),
      'verbosity': self.verbosity,
    }

  def runChecks(self):
    # Checks are run after database creation since some checks require
    # database access.
    #callCommand('check', verbosity=self.verbosity)
    pass

  def runSuite(self, suite, **kwargs):
    kwargs = self.getTestRunnerKwargs()
    runner = self.testRunner(**kwargs)
    return runner.run(suite)

  def teardownDatabases(self, oldConfig, **kwargs):
    """
    Destroys all the non-mirror databases.
    """
    _teardownDatabases(
      oldConfig,
      verbosity=self.verbosity,
      parallel=self.parallel,
      keepdb=self.keepdb,
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
    self.runChecks()
    result = self.runSuite(suite)
    self.teardownDatabases(oldConfig)
    self.teardownTestEnvironment()
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


def reorderSuite(suite, classes, reverse=False):
  """
  Reorders a test suite by test type.

  `classes` is a sequence of types

  All tests of type classes[0] are placed first, then tests of type
  classes[1], etc. Tests with no match in classes are placed last.

  If `reverse` is True, tests within classes are sorted in opposite order,
  but test classes are not reversed.
  """
  classCount = len(classes)
  suiteClass = type(suite)
  bins = [OrderedSet() for i in range(classCount + 1)]
  partitionSuiteByType(suite, classes, bins, reverse=reverse)
  reorderedSuite = suiteClass()
  for i in range(classCount + 1):
    reorderedSuite.addTests(bins[i])
  return reorderedSuite


def partitionSuiteByType(suite, classes, bins, reverse=False):
  """
  Partitions a test suite by test type. Also prevents duplicated tests.

  classes is a sequence of types
  bins is a sequence of TestSuites, one more than classes
  reverse changes the ordering of tests within bins

  Tests of type classes[i] are added to bins[i],
  tests with no match found in classes are place in bins[-1]
  """
  suiteClass = type(suite)
  if reverse:
    suite = reversed(tuple(suite))
  for test in suite:
    if isinstance(test, suiteClass):
      partitionSuiteByType(test, classes, bins, reverse=reverse)
    else:
      for i in range(len(classes)):
        if isinstance(test, classes[i]):
          bins[i].add(test)
          break
      else:
        bins[-1].add(test)


def partitionSuiteByCase(suite):
  """
  Partitions a test suite by test case, preserving the order of tests.
  """
  groups = []
  suiteClass = type(suite)
  for testType, testGroup in itertools.groupby(suite, type):
    if issubclass(testType, unittest.TestCase):
      groups.append(suiteClass(testGroup))
    else:
      for item in testGroup:
        groups.extend(partitionSuiteByCase(item))
  return groups


def setupDatabases(*args, **kwargs):
  warnings.warn(
    '`theory.test.runner.setupDatabases()` has moved to '
    '`theory.test.utils.setupDatabases()`.',
    RemovedInTheory20Warning,
    stacklevel=2,
  )
  return _setupDatabases(*args, **kwargs)


def filterTestsByTags(suite, tagLst, excludeTagLst):
  suiteClass = type(suite)
  filteredSuite = suiteClass()

  for test in suite:
    if isinstance(test, suiteClass):
      filteredSuite.addTests(filterTestsByTags(test, tagLst, excludeTagLst))
    else:
      testTags = set(getattr(test, 'tagLst', set()))
      testFnName = getattr(test, '_testMethodName', str(test))
      testFn = getattr(test, testFnName, test)
      testFnTags = set(getattr(testFn, 'tagLst', set()))
      allTags = testTags.union(testFnTags)
      matchedTagLst = allTags.intersection(tagLst)
      if (matchedTagLst or not tagLst) and not allTags.intersection(excludeTagLst):
        filteredSuite.addTest(test)

  return filteredSuite

