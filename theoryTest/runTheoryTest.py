# -*- coding: utf-8 -*-
#!/usr/bin/env python
##### System wide lib #####
import argparse
import os
import sys

sys.path.append(
    "/".join(
      os.path.dirname(os.path.abspath(__file__)).split("/")[:-1]
      )
    )
os.environ["THEORY_SETTINGS_MODULE"] = "testBase.settings"
import theory
theory.setup()

##### Theory lib #####
from theory.conf import settings
from theory.test.util import getRunner

##### Theory third-party lib #####

##### Local app #####

##### Theory app #####

##### Misc #####

if __name__ == "__main__":
  parser = argparse.ArgumentParser(description='Process some integers.')
  parser.add_argument('--verbosity', nargs='?', default=1, type=int)

  runnerKwargs = vars(parser.parse_args())
  testRunnerClass = getRunner(settings, "")
  testRunner = testRunnerClass(**runnerKwargs)
  testRunner.runTests([os.path.dirname(__file__),])
