# -*- coding: utf-8 -*-
#!/usr/bin/env python
##### System wide lib #####

##### Theory lib #####
from theory.conf import settings
from theory.command.baseCommand import SimpleCommand
from theory.test.utils import get_runner

##### Theory third-party lib #####

##### Local app #####

##### Theory app #####

##### Misc #####

class Tester(SimpleCommand):
  """
  Run the test case. In this version, only theory's testcase will be run.
  In the future, you can run a specific app's testcase as well as all apps'
  testcase.
  """
  name = "tester"
  verboseName = "tester"
  params = []
  _appName = None
  _testRunner = None
  _testLabel = ""
  _testTheory = True

  @property
  def appName(self):
    return self._appName

  @appName.setter
  def appName(self, appName):
    """
    :param appName: The name of application being used
    :type appName: string
    """
    self._appName = appName

  @property
  def testSuite(self):
    return self._testSuite

  @testSuite.setter
  def testSuite(self, testSuite):
    """
    :param testSuite: The python module of testcase suite being used
    :type testSuite: pythonModule
    """
    self._testSuite = testSuite

  @property
  def testTheory(self):
    return self._testTheory

  @testTheory.setter
  def testTheory(self, testTheory):
    """
    :param testTheory: Toogle if theory testcase is inclueded
    :type testTheory: boolean
    """
    self._testTheory = testTheory

  @property
  def testRunner(self):
    return self._testRunner

  @testRunner.setter
  def testRunner(self, testRunner):
    """
    :param testRunner: The python module of testcase runner being used
    :type testRunner: pythonModule
    """
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

    :param testLabel: The python module path of testcase being used
    :type testLabel: string
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
