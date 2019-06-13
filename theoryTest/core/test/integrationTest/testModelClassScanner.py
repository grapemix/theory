# -*- coding: utf-8 -*-
##### System wide lib #####

##### Theory lib #####
from theory.apps.model import AppModel
from theory.core.resourceScan.modelScanManager import ModelScanManager
from theory.test.util import ObjectComparator, ObjectDumper
from theory.test.testcases import TestCase

##### Theory third-party lib #####

##### Local app #####
from testBase.patch import patchDumpdata

##### Theory app #####

##### Misc #####

__all__ = (
    'TestModelClassScannerTestCase',
    )

class TestModelClassScannerTestCase(TestCase):
  pass
  #def testFieldParamMapWithAppModel(self):
  #  model = AppModel.objects.get(
  #      app="theory",
  #      name="AppModel",
  #      )

  #  objectDumper = ObjectDumper(
  #      excludeTermLst=("_created", "_changed_fields", "_initialised"),
  #      absorbTermLst=("_data",)
  #      )
  #  objectComparator = ObjectComparator(objectDumper)

  #  diff = objectComparator.compare(
  #      __file__,
  #      self._testMethodName,
  #      model.fieldParamMap
  #      )
  #  self.assertEqual(diff, [], msg=diff)

  #def testFieldParamMapWithCombinatoryModelWithDefaultValue(self):
  #  model = AppModel.objects.get(
  #      app="testBase",
  #      name="CombinatoryModelWithDefaultValue"
  #      )

  #  objectDumper = ObjectDumper(
  #      excludeTermLst=("_created", "_changed_fields", "_initialised"),
  #      absorbTermLst=("_data",)
  #      )
  #  objectComparator = ObjectComparator(objectDumper)

  #  diff = objectComparator.compare(
  #      __file__,
  #      self._testMethodName,
  #      model.fieldParamMap
  #      )
  #  self.assertEqual(diff, [], msg=diff)

  def testFieldParamMapWithCombinatoryModelWithDefaultValue(self):
    # del me after arrayfield fixture bug is fixed
    AppModel.objects.all().delete()
    patchDumpdata()
    #if AppModel.objects.filter(
    #    name="CombinatoryModelWithDefaultValue"
    #    ).count() != 0:
    #  return
    #modelScanManager = ModelScanManager()
    #modelScanManager.paramList = [
    #    "testBase.__init__",
    #    ]
    #modelScanManager.scan()

    model = AppModel.objects.get(
        name="CombinatoryModelWithDefaultValue"
        )

    #import subprocess
    #subprocess.check_call([
    #  "pg_dump",
    #  "-d",
    #  "test_theory",
    #  "-h",
    #  "localhost",
    #  "-U",
    #  "theory",
    #  #"-a",
    #  "-v",
    #  "--inserts",
    #  "-f",
    #  "/tmp/c.sql"
    #  ])
    #from time import sleep
    #sleep(10)
    #from theory.apps.command.dumpdata import Dumpdata
    #cmd = Dumpdata()
    #cmd.paramForm = cmd.ParamForm()
    #cmd.paramForm.fields["output"].finalData = "/tmp/c.json"
    #cmd.paramForm.isValid()
    #cmd.run()
