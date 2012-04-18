# -*- coding: utf-8 -*-
##### System wide lib #####

##### Theory lib #####
from theory.conf import settings
from theory.command.baseCommand import BaseCommand
from theory.test.utils import get_runner

##### Theory third-party lib #####

##### Local app #####

##### Theory app #####

##### Misc #####

class Test(BaseCommand):
  """
  Run the test case. In this version, only theory's testcase will be run.
  In the future, you can run a specific app's testcase as well as all apps'
  testcase.
  """
  name = "test"
  verboseName = "test"
  params = []
  _app = None
  _testRunner = None
  _testLabel = ""
  _testTheory = False

  @property
  def app(self):
    return self._app

  @app.setter
  def app(self, app):
    self._app = app

  @property
  def testSuite(self):
    return self._testSuite

  @testSuite.setter
  def testSuite(self, testSuite):
    self._testSuite = testSuite

  @property
  def testTheory(self):
    return self._testTheory

  @testTheory.setter
  def testTheory(self, testTheory):
    self._testTheory = testTheory

  @property
  def testRunner(self):
    return self._testRunner

  @testRunner.setter
  def testRunner(self, testRunner):
    self._testRunner = testRunner

  @property
  def testLabel(self):
    return self._testLabel

  @testLabel.setter
  def testLabel(self, testLabel):
    """
    Labels must be of the form:
     - app.TestClass.test_method
      Run a single specific test method
     - app.TestClass
      Run all the test methods in a given class
     - app
      Search for doctests and unittests in the named application.
    """
    self._testLabel = testLabel


  def run(self, *args, **kwargs):
    options = {}
    if(self.testTheory):
      import imp
      import os
      theoryTestRoot = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "tests")
      (file, filename, data) = imp.find_module("runtests", [theoryTestRoot])
      thoeryTestCaseClass = imp.load_module("runtests", file, theoryTestRoot, data)
      thoeryTestCaseClass.registerTestApp()

    testRunnerClass = get_runner(settings, self.testRunner)
    testRunner = testRunnerClass(**options)
    testRunner.run_tests(self.testLabel)
