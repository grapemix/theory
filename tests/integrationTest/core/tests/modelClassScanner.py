# -*- coding: utf-8 -*-
##### System wide lib #####
from ludibrio import Stub

##### Theory lib #####
from theory.model import AppModel
from theory.test.util import ObjectComparator, ObjectDumper
from theory.utils import unittest

##### Theory third-party lib #####

##### Local app #####

##### Theory app #####

##### Misc #####

__all__ = (
    'ModelClassScannerTestCase',
    )

class ModelClassScannerTestCase(unittest.TestCase):
  def testFieldParamMapWithAppModel(self):
    model = AppModel.objects.get(
        app="theory",
        name="AppModel",
        )

    objectDumper = ObjectDumper(
        excludeTermLst=("_created", "_changed_fields", "_initialised"),
        absorbTermLst=("_data",)
        )
    objectComparator = ObjectComparator(objectDumper)

    diff = objectComparator.compare(
        __file__,
        self._testMethodName,
        model.fieldParamMap
        )
    self.assertEqual(diff, [], msg=diff)

  def testFieldParamMapWithCombinatoryModelWithDefaultValue(self):
    model = AppModel.objects.get(
        app="testBase",
        name="CombinatoryModelWithDefaultValue"
        )

    objectDumper = ObjectDumper(
        excludeTermLst=("_created", "_changed_fields", "_initialised"),
        absorbTermLst=("_data",)
        )
    objectComparator = ObjectComparator(objectDumper)

    diff = objectComparator.compare(
        __file__,
        self._testMethodName,
        model.fieldParamMap
        )
    self.assertEqual(diff, [], msg=diff)
