#!/usr/bin/env python
from argparse import ArgumentParser
import logging
import os
import shutil
import subprocess
import sys
import tempfile
import warnings

import theory
from theory import contrib
from theory.apps import apps
from theory.conf import settings
from theory.db import connection
from theory.test import TransactionTestCase, TestCase
from theory.test.util import getRunner
from theory.utils.deprecation import RemovedInTheory19Warning, RemovedInTheory20Warning
from theory.utils._os import upath
from theory.utils import six


warnings.simplefilter("default", RemovedInTheory19Warning)
warnings.simplefilter("default", RemovedInTheory20Warning)

CONTRIB_MODULE_PATH = 'theory.contrib'

CONTRIB_DIR = os.path.dirname(upath(contrib.__file__))
RUNTESTS_DIR = os.path.abspath(os.path.dirname(upath(__file__)))

TEMP_DIR = tempfile.mkdtemp(prefix='theory_')
os.environ['THEORY_TEST_TEMP_DIR'] = TEMP_DIR

SUBDIRS_TO_SKIP = [
  'data',
  'testDiscoverySample',
  'testDiscoverySample2',
  'testRunnerDeprecationApp',
]

ALWAYS_INSTALLED_APPS = [
  'theory.apps',
]

ALWAYS_MIDDLEWARE_CLASSES = (
)


def getTestModules():
  #from theory.contrib.gis.tests.utils import HAS_SPATIAL_DB
  modules = []
  discoveryPaths = [
    (None, RUNTESTS_DIR),
    (CONTRIB_MODULE_PATH, CONTRIB_DIR)
  ]
  #if HAS_SPATIAL_DB:
  #  discoveryPaths.append(
  #    ('theory.contrib.gis.tests', os.path.join(CONTRIB_DIR, 'gis', 'tests'))
  #  )

  for modpath, dirpath in discoveryPaths:
    for f in os.listdir(dirpath):
      if ('.' in f or
          f.startswith('sql') or
          os.path.basename(f) in SUBDIRS_TO_SKIP or
          os.path.isfile(f) or
          not os.path.exists(os.path.join(dirpath, f, '__init__.py'))):
        continue
      if not connection.vendor == 'postgresql' and f == 'postgresTests':
        continue
      modules.append((modpath, f))
  return modules


def getInstalled():
  return [appConfig.name for appConfig in apps.getAppConfigs()]


def setup(verbosity, testLabels):
  print("Testing against Theory installed in '%s'" % os.path.dirname(theory.__file__))

  # Force declaring availableApps in TransactionTestCase for faster tests.
  def noAvailableApps(self):
    raise Exception("Please define availableApps in TransactionTestCase "
            "and its subclasses.")
  TransactionTestCase.availableApps = property(noAvailableApps)
  TestCase.availableApps = None

  state = {
    'INSTALLED_APPS': settings.INSTALLED_APPS,
    'LANGUAGE_CODE': settings.LANGUAGE_CODE,
    'MIDDLEWARE_CLASSES': settings.MIDDLEWARE_CLASSES,
    'FIXTURE_DIRS': settings.FIXTURE_DIRS,
  }

  # Redirect some settings for the duration of these tests.
  settings.INSTALLED_APPS = ALWAYS_INSTALLED_APPS
  settings.LANGUAGE_CODE = 'en'
  settings.MIDDLEWARE_CLASSES = ALWAYS_MIDDLEWARE_CLASSES
  # Ensure the middleware classes are seen as overridden otherwise we get a compatibility warning.
  #settings._explicitSettings.add('MIDDLEWARE_CLASSES')
  settings.MIGRATION_MODULES = {
    # these 'tests.migrations' modules don't actually exist, but this lets
    # us skip creating migrations for the test models.
    #'auth': 'theory.contrib.auth.tests.migrations',
    #'contenttypes': 'theory.contrib.contenttypes.tests.migrations',
  }
  settings.FIXTURE_DIRS = [os.path.join(RUNTESTS_DIR, "testBase", "fixture"),]

  if verbosity > 0:
    # Ensure any warnings captured to logging are piped through a verbose
    # logging handler.  If any -W options were passed explicitly on command
    # line, warnings are not captured, and this has no effect.
    logger = logging.getLogger('py.warnings')
    handler = logging.StreamHandler()
    logger.addHandler(handler)

  warnings.filterwarnings(
    'ignore',
    'theory.contrib.webdesign will be removed in Theory 2.0.',
    RemovedInTheory20Warning
  )

  # Load all the ALWAYS_INSTALLED_APPS.
  theory.setup()

  # Load all the test model apps.
  testModules = getTestModules()

  # Reduce given test labels to just the app module path
  testLabelsSet = set()
  for label in testLabels:
    bits = label.split('.')
    if bits[:2] == ['theory', 'contrib']:
      bits = bits[:3]
    else:
      bits = bits[:1]
    testLabelsSet.add('.'.join(bits))

  installedAppNames = set(getInstalled())
  for modpath, moduleName in testModules:
    if modpath:
      moduleLabel = '.'.join([modpath, moduleName])
    else:
      moduleLabel = moduleName
    # if the module (or an ancestor) was named on the command line, or
    # no modules were named (i.e., run all), import
    # this module and add it to INSTALLED_APPS.
    if not testLabels:
      moduleFoundInLabels = True
    else:
      moduleFoundInLabels = any(
        # exact match or ancestor match
        moduleLabel == label or moduleLabel.startswith(label + '.')
        for label in testLabelsSet)

    if moduleFoundInLabels and moduleLabel not in installedAppNames:
      if verbosity >= 2:
        print("Importing application %s" % moduleName)
      settings.INSTALLED_APPS.append(moduleLabel)

  apps.setInstalledApps(settings.INSTALLED_APPS)

  return state


def teardown(state):
  try:
    # Removing the temporary TEMP_DIR. Ensure we pass in unicode
    # so that it will successfully remove temp trees containing
    # non-ASCII filenames on Windows. (We're assuming the temp dir
    # name itself does not contain non-ASCII characters.)
    shutil.rmtree(six.textType(TEMP_DIR))
  except OSError:
    print('Failed to remove temp directory: %s' % TEMP_DIR)

  # Restore the old settings.
  for key, value in state.items():
    setattr(settings, key, value)


def theoryTests(verbosity, interactive, failfast, testLabels):
  state = setup(verbosity, testLabels)
  extraTests = []

  # Run the test suite, including the extra validation tests.
  if not hasattr(settings, 'TEST_RUNNER'):
    settings.TEST_RUNNER = 'theory.test.runner.DiscoverRunner'
  TestRunner = getRunner(settings)

  testRunner = TestRunner(
    verbosity=verbosity,
    interactive=interactive,
    failfast=failfast,
  )
  # Catch warnings thrown in test DB setup -- remove in Theory 1.9
  with warnings.catch_warnings():
    warnings.filterwarnings(
      'ignore',
      "Custom SQL location '<appLabel>/models/sql' is deprecated, "
      "use '<appLabel>/sql' instead.",
      RemovedInTheory19Warning
    )
    failures = testRunner.runTests(
      [".",], extraTests=extraTests)

  teardown(state)
  return failures


def bisectTests(bisectionLabel, options, testLabels):
  state = setup(options.verbosity, testLabels)

  testLabels = testLabels or getInstalled()

  print('***** Bisecting test suite: %s' % ' '.join(testLabels))

  # Make sure the bisection point isn't in the test list
  # Also remove tests that need to be run in specific combinations
  for label in [bisectionLabel, 'modelInheritanceSameModelName']:
    try:
      testLabels.remove(label)
    except ValueError:
      pass

  subprocessArgs = [
    sys.executable, upath(__file__), '--settings=%s' % options.settings]
  if options.failfast:
    subprocessArgs.append('--failfast')
  if options.verbosity:
    subprocessArgs.append('--verbosity=%s' % options.verbosity)
  if not options.interactive:
    subprocessArgs.append('--noinput')

  iteration = 1
  while len(testLabels) > 1:
    midpoint = len(testLabels) // 2
    testLabelsA = testLabels[:midpoint] + [bisectionLabel]
    testLabelsB = testLabels[midpoint:] + [bisectionLabel]
    print('***** Pass %da: Running the first half of the test suite' % iteration)
    print('***** Test labels: %s' % ' '.join(testLabelsA))
    failuresA = subprocess.call(subprocessArgs + testLabelsA)

    print('***** Pass %db: Running the second half of the test suite' % iteration)
    print('***** Test labels: %s' % ' '.join(testLabelsB))
    print('')
    failuresB = subprocess.call(subprocessArgs + testLabelsB)

    if failuresA and not failuresB:
      print("***** Problem found in first half. Bisecting again...")
      iteration = iteration + 1
      testLabels = testLabelsA[:-1]
    elif failuresB and not failuresA:
      print("***** Problem found in second half. Bisecting again...")
      iteration = iteration + 1
      testLabels = testLabelsB[:-1]
    elif failuresA and failuresB:
      print("***** Multiple sources of failure found")
      break
    else:
      print("***** No source of failure found... try pair execution (--pair)")
      break

  if len(testLabels) == 1:
    print("***** Source of error: %s" % testLabels[0])
  teardown(state)


def pairedTests(pairedTest, options, testLabels):
  state = setup(options.verbosity, testLabels)

  testLabels = testLabels or getInstalled()

  print('***** Trying paired execution')

  # Make sure the constant member of the pair isn't in the test list
  # Also remove tests that need to be run in specific combinations
  for label in [pairedTest, 'modelInheritanceSameModelName']:
    try:
      testLabels.remove(label)
    except ValueError:
      pass

  subprocessArgs = [
    sys.executable, upath(__file__), '--settings=%s' % options.settings]
  if options.failfast:
    subprocessArgs.append('--failfast')
  if options.verbosity:
    subprocessArgs.append('--verbosity=%s' % options.verbosity)
  if not options.interactive:
    subprocessArgs.append('--noinput')

  for i, label in enumerate(testLabels):
    print('***** %d of %d: Check test pairing with %s' % (
       i + 1, len(testLabels), label))
    failures = subprocess.call(subprocessArgs + [label, pairedTest])
    if failures:
      print('***** Found problem pair with %s' % label)
      return

  print('***** No problem pair found')
  teardown(state)


if __name__ == "__main__":
  parser = ArgumentParser(description="Run the Theory test suite.")
  parser.add_argument('modules', nargs='*', metavar='module',
    help='Optional path(s) to test modules; e.g. "i18n" or '
       '"i18n.tests.TranslationTests.testLazyObjects".')
  parser.add_argument(
    '-v', '--verbosity', default=1, type=int, choices=[0, 1, 2, 3],
    help='Verbosity level; 0=minimal output, 1=normal output, 2=all output')
  parser.add_argument(
    '--noinput', action='store_false', dest='interactive', default=True,
    help='Tells Theory to NOT prompt the user for input of any kind.')
  parser.add_argument(
    '--failfast', action='store_true', dest='failfast', default=False,
    help='Tells Theory to stop running the test suite after first failed '
       'test.')
  parser.add_argument(
    '--settings',
    help='Python path to settings module, e.g. "myproject.settings". If '
       'this isn\'t provided, either the THEORY_SETTINGS_MODULE '
       'environment variable or "testSqlite" will be used.')
  parser.add_argument('--bisect',
    help='Bisect the test suite to discover a test that causes a test '
       'failure when combined with the named test.')
  parser.add_argument('--pair',
    help='Run the test suite in pairs with the named test to find problem '
       'pairs.')
  options = parser.parse_args()

  # Allow including a trailing slash on appLabels for tab completion convenience
  options.modules = [os.path.normpath(labels) for labels in options.modules]

  if options.settings:
    os.environ['THEORY_SETTINGS_MODULE'] = options.settings
  else:
    if "THEORY_SETTINGS_MODULE" not in os.environ:
      os.environ['THEORY_SETTINGS_MODULE'] = 'testSqlite'
    options.settings = os.environ['THEORY_SETTINGS_MODULE']

  if options.bisect:
    bisectTests(options.bisect, options, options.modules)
  elif options.pair:
    pairedTests(options.pair, options, options.modules)
  else:
    failures = theoryTests(options.verbosity, options.interactive,
                options.failfast, options.modules)
    if failures:
      sys.exit(bool(failures))
