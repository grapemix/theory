# -*- coding: utf-8 -*-
##### System wide lib #####
import os
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
    'ObjectDumperTestCase',
    'ObjectComparatorTestCase',
    )

class DummyKlass(object):
  klassField = "Hidden"
  def __init__(self):
    self.field1Lbl = "field1"
    self.field2Lbl = "field2"
    self.field3Lbl = {"layer": {"sublayer": "field3"}}

class ObjectDumperTestCase(unittest.TestCase):
  def setUp(self):
    self.rawObj = DummyKlass()

  def testJsonifyObjToStrWithExcludeAbsorbParam(self):
    objectDumper = ObjectDumper(
        excludeTermLst=("field2Lbl",),
        absorbTermLst=("layer",)
        )
    r = objectDumper.jsonifyObjToStr(self.rawObj)
    ans = (
        '{\n'
        '  "field1Lbl": "field1", \n'
        '  "field3Lbl": {\n'
        '    "layer": {\n'
        '      "sublayer": "field3"\n'
        '    }\n'
        '  }\n'
        '}'
        )
    self.assertEqual(r, ans)

  def testJsonifyObjToStrWithExcludeSublayerAbsorbParam(self):
    objectDumper = ObjectDumper(
        excludeTermLst=("field2Lbl", "sublayer"),
        absorbTermLst=("layer",)
        )
    r = objectDumper.jsonifyObjToStr(self.rawObj)
    ans = (
        '{\n'
        '  "field1Lbl": "field1", \n'
        '  "field3Lbl": {\n'
        '    "layer": {\n'
        '      "sublayer": "field3"\n'
        '    }\n'
        '  }\n'
        '}'
        )
    self.assertEqual(r, ans)

  def testJsonifyObjToStrWithIncludeAbsorbParam(self):
    objectDumper = ObjectDumper(
        includeTermLst=("field1Lbl", "field3Lbl"),
        absorbTermLst=("layer",)
        )
    r = objectDumper.jsonifyObjToStr(self.rawObj)
    ans = (
        '{\n'
        '  "field1Lbl": "field1", \n'
        '  "field3Lbl": {\n'
        '    "layer": {\n'
        '      "sublayer": "field3"\n'
        '    }\n'
        '  }\n'
        '}'
        )
    self.assertEqual(r, ans)

class ObjectComparatorTestCase(unittest.TestCase):
  def setUp(self):
    self.rawObj = DummyKlass()

  def test_convertObjToStrWithExcludeAbsorbParam(self):
    objectComparator = ObjectComparator(
        ObjectDumper(
          excludeTermLst=("field2Lbl",),
          absorbTermLst=("layer",)
          )
        )
    r = objectComparator._convertObjToStr(self.rawObj)
    ans = (
        '{\n'
        '  "field1Lbl": "field1", \n'
        '  "field3Lbl": {\n'
        '    "sublayer": "field3"\n'
        '  }\n'
        '}'
        )
    self.assertEqual(r, ans)

  def test_convertObjToStrWithExcludeSublayerAbsorbParam(self):
    objectComparator = ObjectComparator(
        ObjectDumper(
          excludeTermLst=("field2Lbl", "sublayer"),
          absorbTermLst=("layer",)
          )
        )
    r = objectComparator._convertObjToStr(self.rawObj)
    ans = (
        '{\n'
        '  "field1Lbl": "field1"\n'
        '}'
        )
    self.assertEqual(r, ans)

  def test_convertObjToStrWithIncludeAbsorbParam(self):
    self.exf2ab = ObjectComparator(
        ObjectDumper(
          includeTermLst=("field1Lbl", "field3Lbl"),
          absorbTermLst=("layer",)
          )
        )
    r = self.exf2ab._convertObjToStr(self.rawObj)
    ans = (
        '{\n'
        '  "field1Lbl": "field1"\n'
        '}'
        )
    self.assertEqual(r, ans)


  def test_convertObjToStrWithIncludeSublayerAbsorbParam(self):
    self.exf2ab = ObjectComparator(
        ObjectDumper(
          includeTermLst=("field1Lbl", "field3Lbl", "sublayer"),
          absorbTermLst=("layer",)
          )
        )
    r = self.exf2ab._convertObjToStr(self.rawObj)
    ans = (
        '{\n'
        '  "field1Lbl": "field1", \n'
        '  "field3Lbl": {\n'
        '    "sublayer": "field3"\n'
        '  }\n'
        '}'
        )
    self.assertEqual(r, ans)

  def test_getFilePathForTestcase(self):
    r = ObjectComparator(ObjectDumper())._getFilePathForTestcase(
        __file__,
        self._testMethodName,
        )
    self.assertEqual(
        r,
        os.path.join(
          os.path.dirname(os.path.dirname(__file__)),
          "files",
          "util",
          self._testMethodName
          )
    )

  def testSerializeSample(self):
    objectComparator = ObjectComparator(ObjectDumper())
    objectComparator.serializeSample(
        __file__,
        self._testMethodName,
        self.rawObj
        )
    filePath = objectComparator._getFilePathForTestcase(
        __file__,
        self._testMethodName,
        )
    with open(filePath, "r") as fd:
      r = fd.read()
    ans = objectComparator._convertObjToStr(self.rawObj)
    self.assertEqual(r, ans)

  def testCompareWithNoDiff(self):
    objectComparator = ObjectComparator(ObjectDumper())
    diff = objectComparator.compare(
        __file__,
        "testSerializeSample",
        self.rawObj
        )
    self.assertEqual(diff, [], msg=diff)

  def testCompareWithAdd(self):
    objectComparator = ObjectComparator(ObjectDumper())
    self.rawObj.field4Lbl = "field4"
    diff = objectComparator.compare(
        __file__,
        "testSerializeSample",
        self.rawObj
        )
    self.assertEqual(diff, [{'message': 'field4Lbl', 'type': 'ADDED'}])

  def testCompareWithChange(self):
    objectComparator = ObjectComparator(ObjectDumper())
    self.rawObj.field2Lbl = "fieldNot2"
    diff = objectComparator.compare(
        __file__,
        "testSerializeSample",
        self.rawObj
        )
    self.assertEqual(
        diff,
        [{'message': 'field2Lbl - field2 | fieldNot2', 'type': 'CHANGED'}]
        )

  def testCompareWithRemove(self):
    objectComparator = ObjectComparator(ObjectDumper())
    del self.rawObj.field2Lbl
    diff = objectComparator.compare(
        __file__,
        "testSerializeSample",
        self.rawObj
        )
    self.assertEqual(diff, [{'message': 'field2Lbl', 'type': 'REMOVED'}])
