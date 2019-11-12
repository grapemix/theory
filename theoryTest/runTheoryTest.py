# -*- coding: utf-8 -*-
#!/usr/bin/env python
##### System wide lib #####
import argparse
from copy import deepcopy
import os

if __name__ == "__main__":
  parser = argparse.ArgumentParser(description='Process some integers.')
  parser.add_argument('--verbosity', nargs='?', default=1, type=int)

  runnerKwargs = vars(parser.parse_args())

  import sys
  sys.path.append(
      "/".join(os.path.dirname(os.path.abspath(__file__)).split("/")[:-1])
      )

  os.environ["THEORY_SETTINGS_MODULE"] = "testBase.settings"
  testLabelLst = ["theoryTest.core",]

  # To temp fix for grpc's failure on handling multiple libprotobuf problem
  # which is compounded with ubuntu's outdated libprotobuf dependency
  from google.protobuf.pyext import _message
  import theory
  theory.setup()

  from theory.conf import settings
  from theory.test.util import getRunner

  testRunnerClass = getRunner(settings, "")
  runnerKwargs["tagLst"] = ["gevent",]

  testRunner = testRunnerClass(**runnerKwargs)
  testRunner.runTests(testLabelLst)

  del runnerKwargs["tagLst"]
  runnerKwargs["excludeTagLst"] = ["gevent",]
  testLabelLst = ["theoryTest",]
  testRunner = testRunnerClass(**runnerKwargs)
  testRunner.runTests(testLabelLst)
