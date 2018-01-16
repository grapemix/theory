# -*- coding: utf-8 -*-
##### System wide lib #####
import os
from uuid import uuid4

##### Theory lib #####
from theory.test.testcases import TestCase
from theory.utils.importlib import importClass

##### Theory third-party lib #####

##### Local app #####

##### Theory app #####

##### Misc #####

__all__ = (
    'GenerateFixtureTestCase'
    )

class GenerateFixtureTestCase(TestCase):
  def testGenerateFixture(self):
    from theory.core.resourceScan import ModelScanManager
    from theory.core.loader.util import ModuleLoader

    moduleLoader = ModuleLoader(ModelScanManager, "model", ["theory.apps",])
    moduleLoader.lstPackFxn = \
        lambda lst, appName, path: [".".join([appName, i]) for i in lst]
    moduleLoader.load(False)

    filePath = os.path.join("/tmp", "{0}.json".format(uuid4()))
    from theory.apps.command.dumpdata import Dumpdata
    cmd = Dumpdata()
    cmd.paramForm = cmd.ParamForm()
    cmd.paramForm.fields["appLabelLst"].finalData = ["theory.apps",]
    cmd.paramForm.fields["output"].finalData = filePath
    cmd.paramForm.isValid()
    try:
      cmd.run()
    except Exception as e:
      raise e
    finally:
      try:
        os.remove(filePath)
      except:
        pass
