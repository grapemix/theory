# -*- coding: utf-8 -*-
#!/usr/bin/env python
##### System wide lib #####
import gevent
import os

##### Theory lib #####
from theory.apps import apps
from theory.conf import settings
from theory.apps.command.baseCommand import SimpleCommand
from theory.gui import field
from theory.test.util import getRunner
from theory.utils.importlib import importModule

##### Theory third-party lib #####

##### Local app #####

##### Theory app #####

##### Misc #####

__all__ = ("Tester",)

class Tester(SimpleCommand):
  """
  Run the test case of theory or other theory apps
  """
  name = "tester"
  verboseName = "tester"
  params = []

  _gongs = ["StdPipe", ]
  _drums = {"Terminal": 1,}

  class ParamForm(SimpleCommand.ParamForm):
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
        helpText=(
          "Labels must be of the form: - app.TestClass.test_method\n"
          "Run a single specific test method - app.TestClass\n"
          "Run all the test methods in a given class - app\n"
          "Search for doctests and unittests in the named application."
          ),
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
    verbosity = field.IntegerField(
        label="Verbosity",
        initData=1,
        )

  @property
  def stdOut(self):
    return self._stdOut

  def run(self):
    formData = self.paramForm.clean()
    if formData["isTestTheory"]:
      standardAloneTheoryTestScript = importModule(
          "dev.config"
          ).THEORY_ROOT + "/theoryTest/runTheoryTest.py"
      from gevent import subprocess
      p1 = subprocess.Popen(
          [
            'python',
            standardAloneTheoryTestScript,
            "--verbosity",
            str(formData["verbosity"])
          ],
          #stdout=subprocess.PIPE
          )
      #gevent.wait([p1,], timeout=10)
      #while True:
      #  if p1.poll() is not None:
      #    self._stdOut += p1.stdout.read()
      #  else:
      #    self._stdOut += "\n Test is done."
      #    break
    else:
      formData = self.paramForm.clean()
      runnerKwargs = {"verbosity": formData["verbosity"]}

      testRunnerClass = getRunner(settings, "")
      testRunner = testRunnerClass(**runnerKwargs)
      testRunner.runTests(formData["testLabel"])
