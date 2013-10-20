# -*- coding: utf-8 -*-
##### System wide lib #####
from collections import OrderedDict
import copy
from ludibrio import Stub
import os
import sys

##### Theory lib #####
from theory.conf import settings
from theory.core.exceptions import ValidationError
from theory.model import Adapter, BinaryClassifierHistory
from theory.gui import field
from theory.gui import widget
from theory.gui.form import *
from theory.utils import unittest

##### Theory third-party lib #####

##### Local app #####

##### Theory app #####

##### Misc #####

__all__ = ('AdapterFieldTestCase', 'BooleanFieldTestCase', \
    'ChoiceFieldTestCase', 'DecimalFieldTestCase', 'DictFieldTestCase', \
    'EmailFieldTestCase', 'FileFieldTestCase', 'FilePathFieldTestCase', \
    'FloatFieldTestCase', 'GenericIPAddressFieldTestCase', \
    'IPAddressFieldTestCase', 'ImageFieldTestCase', \
    'IntegerFieldTestCase', 'ListFieldTestCase', \
    'ModelValidateGroupFieldTestCase', 'MultipleChoiceFieldTestCase', \
    'NullBooleanFieldTestCase', 'RegexFieldTestCase', 'SlugFieldTestCase', \
    'StringGroupFilterFieldTestCase', 'TextFieldTestCase', \
    'TypedChoiceFieldTestCase', 'TypedMultipleChoiceFieldTestCase', \
    'URLFieldTestCase', 'PythonModuleFieldTestCase', \
    'PythonClassFieldTestCase', \
    )

class FieldTestCaseBase(unittest.TestCase):
  complexField = ["ListFieldTestCase", "DictFieldTestCase", ]

  def __init__(self, *args, **kwargs):
    super(FieldTestCaseBase, self).__init__(*args, **kwargs)
    self.testCaseFileAbsPath = os.path.join(os.path.dirname(os.path.dirname(__file__)), "testsFile", "field")

  def setUp(self):
    pass

  def _getMockAdapterObject(self, adapter, classImportPath):
    with Stub(proxy=adapter) as adapter:
      adapter.classImportPath >> "%s.%s" % (self.__module__, classImportPath)
    return adapter

  def _getMockModelValidateGroupObject(self, modelValidateGroup, classImportPath):
    with Stub(proxy=modelValidateGroup) as modelValidateGroup:
      modelValidateGroup.classImportPath >> "%s.%s" % (self.__module__, classImportPath)
    return modelValidateGroup

  def extraInitParam(self):
    return {}

  def testInitDataInOneLine(self):
    initParam = self.extraInitParam()
    initParam.update({"initData": self.getInitData()})

    self.field = self.fieldKlass(**initParam)

class BooleanFieldTestCase(FieldTestCaseBase):
  fieldKlass = field.BooleanField
  def getInitData(self):
    return True

class DecimalFieldTestCase(FieldTestCaseBase):
  fieldKlass = field.DecimalField
  def getInitData(self):
    return 1

class EmailFieldTestCase(FieldTestCaseBase):
  fieldKlass = field.EmailField
  def getInitData(self):
    return "test@grape.mx"

class FilePathFieldTestCase(FieldTestCaseBase):
  fieldKlass = field.FilePathField
  def getInitData(self):
    return "/tmp/test"

  def extraInitParam(self):
    return {"path": "/tmp"}

class FloatFieldTestCase(FieldTestCaseBase):
  fieldKlass = field.FloatField
  def getInitData(self):
    return 1.0

class GenericIPAddressFieldTestCase(FieldTestCaseBase):
  fieldKlass = field.GenericIPAddressField
  def getInitData(self):
    return "192.168.0.1"

class IPAddressFieldTestCase(FieldTestCaseBase):
  fieldKlass = field.IPAddressField
  def getInitData(self):
    return "192.168.0.1"

class IntegerFieldTestCase(FieldTestCaseBase):
  fieldKlass = field.IntegerField
  def getInitData(self):
    return 1

class TextFieldTestCase(FieldTestCaseBase):
  fieldKlass = field.TextField
  def getInitData(self):
    return "test"

class URLFieldTestCase(FieldTestCaseBase):
  fieldKlass = field.URLField
  def getInitData(self):
    return "http://grape.mx"

class ChoiceFieldTestCase(FieldTestCaseBase):
  fieldKlass = field.ChoiceField
  def getInitData(self):
    return 1

  def extraInitParam(self):
    return {"choices": ((0, "A"), (1, "B"),)}

  def initInMultipleLine(self):
    field = self.initInOneLine()
    field.attrs["choices"] = ((0, "A"), (1, "B"),)
    return field

  def testInitValueAsInteger(self):
    self.field = self.fieldKlass(choices=((1, "A"), (2, "B"), ), \
        initData=1)
    self.assertEqual(self.field.initData, 1)
    self.assertEqual(self.field.finalData, 1)
    self.field.finalData = 2
    self.assertEqual(self.field.clean(self.field.finalData), '2')

  def testRequiredValidation(self):
    self.field = self.fieldKlass(choices=((1, "A"), (2, "B"), ))
    with self.assertRaises(ValidationError):
      self.assertEqual(self.field.clean(self.field.finalData), '')
    self.field.required = False
    self.assertEqual(self.field.clean(self.field.finalData), '')

class MultipleChoiceFieldTestCase(FieldTestCaseBase):
  fieldKlass = field.MultipleChoiceField

  def getInitData(self):
    return [1]

  def extraInitParam(self):
    return {"choices": ((0, "A"), (1, "B"),)}


class TypedChoiceFieldTestCase(MultipleChoiceFieldTestCase):
  fieldKlass = field.TypedChoiceField

class TypedMultipleChoiceFieldTestCase(MultipleChoiceFieldTestCase):
  fieldKlass = field.TypedMultipleChoiceField

class AdapterFieldTestCase(FieldTestCaseBase):
  fieldKlass = field.AdapterField
  def getInitData(self):
    return self._getMockAdapterObject(Adapter(name="dummyAdapter"), "fake.path")

class SlugFieldTestCase(FieldTestCaseBase):
  fieldKlass = field.SlugField
  def getInitData(self):
    return "SlugTest"

class NullBooleanFieldTestCase(FieldTestCaseBase):
  fieldKlass = field.NullBooleanField
  # check null
  def getInitData(self):
    return True

class RegexFieldTestCase(FieldTestCaseBase):
  fieldKlass = field.RegexField
  def getInitData(self):
    return None

  def extraInitParam(self):
    return {"regex": "[Tt]estField*"}

class FileFieldTestCase(FieldTestCaseBase):
  fieldKlass = field.FileField

  def getInitData(self):
    return os.path.join(self.testCaseFileAbsPath, "jpeg.jpg")

class ImageFieldTestCase(FileFieldTestCase):
  fieldKlass = field.ImageField

class StringGroupFilterFieldTestCase(FieldTestCaseBase):
  fieldKlass = field.StringGroupFilterField
  def getInitData(self):
    return (("A", ("a", "b",)),("B", ("c", "d", "e")), ("C", ("f", "g",)))

class ModelValidateGroupFieldTestCase(FieldTestCaseBase):
  fieldKlass = field.ModelValidateGroupField
  def getInitData(self):
    return list(BinaryClassifierHistory(ref=None, initState=True, finalState=False))

class ListFieldTestCase(FieldTestCaseBase):
  fieldKlass = field.ListField
  thisModule = sys.modules[__name__]
  def _getFieldKlass(self, fieldName):
    return  getattr(getattr(self.thisModule, fieldName), "fieldKlass")

  def getInitData(self):
    return []
    #return [self._getFieldKlass(field) for field in __all__ if(field not in self.complexField)]

  def extraInitParam(self):
    return {"field": self._getFieldKlass("BooleanFieldTestCase")()}

  def testEmptyInitValue(self):
    self.field = self.fieldKlass(**self.extraInitParam())
    self.assertEqual(self.field.initData, [])

  def testEmptyFinalValue(self):
    self.field = self.fieldKlass(**self.extraInitParam())
    with self.assertRaises(ValidationError):
      self.assertEqual(self.field.clean(self.field.finalData), [])
    self.field.min_len = 0
    self.assertEqual(self.field.clean(self.field.finalData), [])

  def testSingleElementInitValue(self):
    param = self.extraInitParam()
    param.update({"initData": [True]})
    self.field = self.fieldKlass(**param)
    self.assertEqual(self.field.initData, [True])
    self.assertEqual(self.field.clean(self.field.finalData), [True])

  def testMultipleElementInitValue(self):
    param = self.extraInitParam()
    param.update({"initData": [True, False]})
    self.field = self.fieldKlass(**param)
    self.assertEqual(self.field.initData, [True, False])
    self.assertEqual(self.field.clean(self.field.finalData), [True, False])

class DictFieldTestCase(FieldTestCaseBase):
  fieldKlass = field.DictField

  thisModule = sys.modules[__name__]
  def _getFieldKlass(self, fieldName):
    return  getattr(getattr(self.thisModule, fieldName), "fieldKlass")

  def getInitData(self):
    return OrderedDict((("",""),))

  def extraInitParam(self):
    return {
        "keyField": self._getFieldKlass("TextFieldTestCase")(),
        "valueField": self._getFieldKlass("TextFieldTestCase")(),
        "initData": {},
    }
    #return dict((field, self._getFieldKlass(field)) for field in __all__ if(field not in self.complexField))

  def testEmptyFinalValue(self):
    self.field = self.fieldKlass(**self.extraInitParam())
    self.field.min_len = 5
    with self.assertRaises(ValidationError):
      self.field.clean(self.field.finalData)
    self.field.min_len = 0
    self.assertEqual(self.field.clean(self.field.finalData), {})

  #def testSingleElementInitValue(self):
  #  param = self.extraInitParam()
  #  param.update({"initData": {"1": "a"}})
  #  self.field = self.fieldKlass(**param)
  #  self.assertEqual(self.field.initData, {"1": "a"})
  #  self.assertEqual(self.field.clean(self.field.finalData), {"1": "a"})

  #def testMultipleElementInitValue(self):
  #  param = self.extraInitParam()
  #  param.update({"initData": {"1": "a", "2": "b"}})
  #  self.field = self.fieldKlass(**param)
  #  self.assertEqual(self.field.initData, {"1": "a", "2": "b"})
  #  self.assertEqual(self.field.clean(self.field.finalData), {"1": "a", "2": "b"})

class PythonModuleFieldTestCase(FieldTestCaseBase):
  fieldKlass = field.PythonModuleField

  def getInitData(self):
    return None

  def setUp(self):
    self.field = self.fieldKlass(auto_import=True)

  def testValidatePlain(self):
    self.field.auto_import = False
    self.assertEqual(self.field.validate("anything"), "anything")

  def testValidateAutoImport(self):
    from theory.utils.importlib import import_class
    expectedModule = import_class("theory.command")
    self.assertEqual(self.field.validate("theory.command"), expectedModule)
    self.assertRaises(ValidationError, self.field.validate, "theory.command.blah")
    self.assertRaises(ValidationError, self.field.validate, "theory.command.listCommand.ListCommand")

class PythonClassFieldTestCase(FieldTestCaseBase):
  fieldKlass = field.PythonClassField

  def getInitData(self):
    return None

  def setUp(self):
    self.field = self.fieldKlass(auto_import=True)

  def testValidatePlain(self):
    self.field.auto_import = False
    self.assertEqual(self.field.validate("anything"), "anything")

  def testValidateAutoImport(self):
    from theory.utils.importlib import import_class
    expectedKlass = import_class("theory.command.listCommand.ListCommand")

    with self.assertRaises(ValidationError):
      self.field.validate("theory.command")
      self.field.klass_type = "theory.command.baseCommand.SimpleCommand"
      self.field.validate("theory.command.blah")
    self.assertEqual(self.field.validate("theory.command.listCommand.ListCommand"), expectedKlass)


