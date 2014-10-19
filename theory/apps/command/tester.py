# -*- coding: utf-8 -*-
#!/usr/bin/env python
##### System wide lib #####

##### Theory lib #####
from theory.conf import settings
from theory.apps.command.baseCommand import SimpleCommand
from theory.gui import field
from theory.test.util import getRunner

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

  class ParamForm(SimpleCommand.ParamForm):
    #appName = field.TextField(label="Application Name", \
    #    helpText="The name of application being tested", maxLength=32, \
    #    required=False)
    #testSuite = field.PythonClassField(label="Test Suite", \
    #    helpText="The python class of testcase suite being used", \
    #    required=False)
    isTestTheory = field.BooleanField(
        label="Is test Theory",
        helpText="The testcase of Theory is being runned or not",
        initData=1
        )
    testRunner = field.PythonClassField(
        label="Test Runner",
        helpText="The python class of testcase runner being used",
        initData="",
        autoImport=True,
        required=False
        )
    testLabel = field.ListField(
        field.TextField(maxLength=64),
        label="Test Label",
        helpText="""Labels must be of the form:
     - app.TestClass.test_method
         Run a single specific test method
     - app.TestClass
         Run all the test methods in a given class
     - app
         Search for doctests and unittests in the named application.""",
        initData=[],
        required=False
        )
    testRunnerClassParam = field.DictField(
        field.TextField(),
        field.TextField(),
        label="Test Runner Class Parameter",
        helpText="The parameter passed to the test runner class constructor",
        required=False,
        )

  def run(self):
    formData = self.paramForm.clean()
    if(formData["isTestTheory"]=='1' or formData["isTestTheory"]):
      import imp
      import os
      theoryTestRoot = os.path.join(
          os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.dirname(os.path.abspath(__file__))
            ))),
          "tests"
          )
      (file, filename, data) = imp.find_module("runtests", [theoryTestRoot])
      print file, theoryTestRoot, data
      thoeryTestCaseClass = imp.load_module(
          "runtests",
          file,
          theoryTestRoot,
          data
          )
      thoeryTestCaseClass.registerTestApp()

    #testRunnerClass = get_runner(settings, formData["testRunner"])
    #testRunner = testRunnerClass(formData["testRunnerClassParam"])
    #testRunner.run_tests(formData["testLabel"])

    testRunnerClass = getRunner(settings, "")
    testRunner = testRunnerClass(verbosity=formData["verbosity"])
    testRunner.runTests(formData["testLabel"])
