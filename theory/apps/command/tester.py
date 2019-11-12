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
    testRunner = field.PythonClassField(
        label="Test Runner",
        helpText="The python class of testcase runner being used",
        initData="",
        autoImport=True,
        required=False
        )
    testLabel = field.ListField(
        field.TextField(maxLen=64),
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

  @property
  def stdOut(self):
    return self._stdOut

  #def runOld(self):
  #  # Using subprocess to run theory testcase. deprecate
  #  formData = self.paramForm.clean()
  #  theoryDirPath = importModule("dev.config").THEORY_ROOT
  #  if formData["isTestTheory"]:
  #    settings_module = "testBase.settings"
  #    testLabelLst = theoryDirPath + "/theoryTest"
  #  else:
  #    settings_module = os.environ["THEORY_SETTINGS_MODULE"]
  #    testLabelLst = " ".join(formData["testLabel"])

  #  standardAloneTheoryTestScript = \
  #    theoryDirPath + "/theoryTest/runTheoryTest.py"
  #  from theory.thevent import gevent
  #  p1 = gevent.subprocess.Popen(
  #      [
  #        'python',
  #        standardAloneTheoryTestScript,
  #        "--verbosity",
  #        str(formData["verbosity"]),
  #        "--settings_module",
  #        settings_module,
  #        "--testLabelLst",
  #        testLabelLst
  #      ],
  #      #stdout=gevent.subprocess.PIPE
  #      )
  #  #gevent.wait([p1,], timeout=10)
  #  #while True:
  #  #  if p1.poll() is not None:
  #  #    self._stdOut += p1.stdout.read()
  #  #  else:
  #  #    self._stdOut += "\n Test is done."
  #  #    break

  def run(self):
    formData = self.paramForm.clean()
    # the original way. Since grpc dominated the main thread, using the
    # following method will yield
    # "ValueError: 'signal only works in main thread'"
    # So we have to disable unittest's sigint handler
    runnerKwargs = {"verbosity": formData["verbosity"], "sigintHandler": False}

    testRunnerClass = getRunner(settings, "")
    testRunner = testRunnerClass(**runnerKwargs)
    testRunner.runTests(formData["testLabel"])
