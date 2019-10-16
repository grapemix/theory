# -*- coding: utf-8 -*-
##### System wide lib #####
from collections import OrderedDict
import copy
from inspect import isclass
from unittest import mock
import os
import sys

##### Theory lib #####
from theory.apps.model import Adapter, BinaryClassifierHistory
from theory.conf import settings
from theory.core.exceptions import ValidationError
from theory.gui import field
from theory.gui import widget
from theory.gui.model import ModelChoiceField, ModelMultipleChoiceField
from theory.gui.form import *
from theory.gui.util import LocalFileObject
from theory.test.testcases import TestCase

##### Theory third-party lib #####

##### Local app #####

##### Theory app #####

##### Misc #####

__all__ = ('AdapterFieldTestCase', 'BooleanFieldTestCase',
    'ChoiceFieldTestCase', 'DecimalFieldTestCase', 'DictFieldTestCase',
    'EmailFieldTestCase', 'FileFieldTestCase', 'FilePathFieldTestCase',
    'ImageFieldTestCase', 'DirPathFieldTestCase', 'ImagePathFieldTestCase',
    'FloatFieldTestCase', 'GenericIPAddressFieldTestCase',
    'IPAddressFieldTestCase',     'IntegerFieldTestCase', 'ListFieldTestCase',
    'ModelValidateGroupFieldTestCase', 'MultipleChoiceFieldTestCase',
    'NullBooleanFieldTestCase', 'RegexFieldTestCase', 'SlugFieldTestCase',
    'StringGroupFilterFieldTestCase', 'TextFieldTestCase',
    'TypedChoiceFieldTestCase', 'TypedMultipleChoiceFieldTestCase',
    'URLFieldTestCase', 'PythonModuleFieldTestCase',
    'PythonClassFieldTestCase', 'ModelChoiceFieldTestCase',
    'ModelMultipleChoiceFieldTestCase',
    )

class FieldTestCaseBase(object):
  complexField = ["ListFieldTestCase", "DictFieldTestCase", ]
  fixtures = ["adapter",]

  def __init__(self, *args, **kwargs):
    super(FieldTestCaseBase, self).__init__(*args, **kwargs)
    self.testCaseFileAbsPath = os.path.join(
        os.path.dirname(
          os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        ),
        "testBase",
        "testsFile",
        "field"
        )
    self.dummyWin = None

  def extraInitParam(self):
    return {}

  def testInitDataInOneLine(self):
    initParam = self.extraInitParam()
    initParam.update({"initData": self.getInitData()})

    self.field = self.fieldKlass(**initParam)
    self.renderWidget(self.field)

  def renderWidget(self, field, *args, **kwargs):
    pass

class BooleanFieldTestCase(FieldTestCaseBase, TestCase):
  fieldKlass = field.BooleanField
  def getInitData(self):
    return True

class DecimalFieldTestCase(FieldTestCaseBase, TestCase):
  fieldKlass = field.DecimalField
  def getInitData(self):
    return 1.8

class EmailFieldTestCase(FieldTestCaseBase, TestCase):
  fieldKlass = field.EmailField
  def getInitData(self):
    return "test@grape.mx"

class FloatFieldTestCase(FieldTestCaseBase, TestCase):
  fieldKlass = field.FloatField
  def getInitData(self):
    return 1.3

class GenericIPAddressFieldTestCase(FieldTestCaseBase, TestCase):
  fieldKlass = field.GenericIPAddressField
  def getInitData(self):
    return "192.168.0.1"

class IPAddressFieldTestCase(FieldTestCaseBase, TestCase):
  fieldKlass = field.IPAddressField
  def getInitData(self):
    return "192.168.0.1"

class IntegerFieldTestCase(FieldTestCaseBase, TestCase):
  fieldKlass = field.IntegerField
  def getInitData(self):
    return 1

class TextFieldTestCase(FieldTestCaseBase, TestCase):
  fieldKlass = field.TextField
  def getInitData(self):
    return "test"

  def testAssignFinalData(self):
    self.field = self.fieldKlass(initData="test")
    self.renderWidget(self.field)
    self.assertEqual(self.field.initData, "test")

    self.field.finalData = "for real"
    self.assertEqual(self.field.initData, "test")
    self.assertEqual(self.field.finalData, "for real")
    self.assertEqual(self.field.clean(self.field.finalData), "for real")

    self.field.finalData = "for real again"
    self.assertEqual(self.field.initData, "test")
    self.assertEqual(self.field.finalData, "for real again")
    self.assertEqual(self.field.clean(self.field.finalData), "for real again")

  def testAccessEmptyFinalData(self):
    self.field = self.fieldKlass(initData="test")
    self.renderWidget(self.field)
    self.assertEqual(self.field.initData, "test")
    self.assertEqual(self.field.finalData, "test")

class URLFieldTestCase(FieldTestCaseBase, TestCase):
  fieldKlass = field.URLField
  def getInitData(self):
    return "http://grape.mx"

class ChoiceFieldTestCase(FieldTestCaseBase, TestCase):
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
    self.renderWidget(self.field)
    self.assertEqual(self.field.initData, 1)
    self.assertEqual(self.field.finalData, 1)
    self.field.finalData = 2
    self.assertEqual(self.field.clean(self.field.finalData), '2')

  def testRequiredValidation(self):
    self.field = self.fieldKlass(choices=((1, "A"), (2, "B"), ))
    #self.renderWidget(self.field)
    with self.assertRaises(ValidationError):
      self.assertEqual(self.field.clean(self.field.finalData), '')
    self.field.required = False
    self.assertEqual(self.field.clean(self.field.finalData), '')

class MultipleChoiceFieldTestCase(FieldTestCaseBase, TestCase):
  fieldKlass = field.MultipleChoiceField

  def getInitData(self):
    return [1]

  def extraInitParam(self):
    return {"choices": ((0, "A"), (1, "B"),)}


class TypedChoiceFieldTestCase(MultipleChoiceFieldTestCase):
  fieldKlass = field.TypedChoiceField

class TypedMultipleChoiceFieldTestCase(MultipleChoiceFieldTestCase):
  fieldKlass = field.TypedMultipleChoiceField

class AdapterFieldTestCase(FieldTestCaseBase, TestCase):
  fieldKlass = field.AdapterField
  def getInitData(self):
    return ["DummyForTest",]

  def testInitData(self):
    initData = self.getInitData()
    self.field = self.fieldKlass(**{"initData": initData})
    self.renderWidget(self.field)
    if not isinstance(widget, str):
      self.assertEqual(self.field.clean(self.field.finalData), initData)
    else:
      self.assertEqual(
          self.field.clean(self.field.finalData)[0].id,
          Adapter.objects.get(name__in=initData).id
      )

  def testEmptyData(self):
    self.field = self.fieldKlass()
    self.field.required = False
    self.renderWidget(self.field)
    # Note: self.field.clean(self.field.finalData) as mongoengine queryset
    self.assertEqual(list(self.field.clean(self.field.finalData)), [])

class SlugFieldTestCase(FieldTestCaseBase, TestCase):
  fieldKlass = field.SlugField
  def getInitData(self):
    return "SlugTest"

class NullBooleanFieldTestCase(FieldTestCaseBase, TestCase):
  fieldKlass = field.NullBooleanField
  # check null
  def getInitData(self):
    return True

class RegexFieldTestCase(FieldTestCaseBase, TestCase):
  fieldKlass = field.RegexField
  def getInitData(self):
    return None

  def extraInitParam(self):
    return {"regex": "[Tt]estField*"}

class FileFieldTestCase(FieldTestCaseBase, TestCase):
  fieldKlass = field.FileField

  def getInitData(self):
    return os.path.join(self.testCaseFileAbsPath, "jpeg.jpg")

  def testEmptyFinalValue(self):
    self.field = self.fieldKlass()
    self.renderWidget(self.field)

    with self.assertRaises(ValidationError):
      self.assertEqual(self.field.clean(self.field.finalData), None)

    self.field.required = False
    self.assertEqual(self.field.clean(self.field.finalData), None)

  def testInvalidFile(self):
    self.field = self.fieldKlass(
        initData=os.path.join(self.testCaseFileAbsPath, "invalid.jpg"),
        )
    self.renderWidget(self.field)

    with self.assertRaises(ValidationError):
      self.assertEqual(self.field.clean(self.field.finalData), {})

  def testMaxLength(self):
    initData=os.path.join(self.testCaseFileAbsPath, "jpeg.jpg")
    self.field = self.fieldKlass(
        initData=initData,
        maxLen=1,
        )
    self.renderWidget(self.field)

    with self.assertRaises(ValidationError):
      self.assertEqual(self.field.clean(self.field.finalData), {})

    self.field.maxLen = 99999
    self.assertEqual(
        self.field.clean(self.field.finalData).filepath,
        LocalFileObject(initData).filepath
        )

class ImageFieldTestCase(FileFieldTestCase):
  fieldKlass = field.ImageField

class FilePathFieldTestCase(FieldTestCaseBase, TestCase):
  fieldKlass = field.FilePathField
  def getInitData(self):
    return os.path.join(self.testCaseFileAbsPath, "jpeg.jpg")

  def testEmptyFinalValue(self):
    self.field = self.fieldKlass()
    self.renderWidget(self.field)

    with self.assertRaises(ValidationError):
      self.assertEqual(self.field.clean(self.field.finalData), None)

    self.field.required = False
    self.assertEqual(self.field.clean(self.field.finalData), None)

  def testInvalidFile(self):
    self.field = self.fieldKlass(
        initData=os.path.join(self.testCaseFileAbsPath, "invalid.jpg"),
        )
    self.renderWidget(self.field)

    with self.assertRaises(ValidationError):
      self.assertEqual(self.field.clean(self.field.finalData), {})

  def testMaxLength(self):
    initData=os.path.join(self.testCaseFileAbsPath, "jpeg.jpg")
    self.field = self.fieldKlass(
        initData=initData,
        maxLen=1,
        )
    self.renderWidget(self.field)

    with self.assertRaises(ValidationError):
      self.assertEqual(self.field.clean(self.field.finalData), {})

    self.field.maxLen = 99999
    self.assertEqual(
        self.field.clean(self.field.finalData).filepath,
        LocalFileObject(initData).filepath
        )

class ImagePathFieldTestCase(FileFieldTestCase):
  fieldKlass = field.ImageField

class DirPathFieldTestCase(FieldTestCaseBase, TestCase):
  fieldKlass = field.DirPathField
  def getInitData(self):
    return self.testCaseFileAbsPath

  def testInvalidDir(self):
    self.field = self.fieldKlass(
        initData=os.path.join(self.testCaseFileAbsPath, "invalid"),
        )
    self.renderWidget(self.field)

    with self.assertRaises(ValidationError):
      self.assertEqual(self.field.clean(self.field.finalData), {})

  def testInvalidFile(self):
    self.field = self.fieldKlass(
        initData=os.path.join(self.testCaseFileAbsPath, "jpeg.jpg"),
        )
    self.renderWidget(self.field)

    with self.assertRaises(ValidationError):
      self.assertEqual(self.field.clean(self.field.finalData), {})

  def testUnaccessableDir(self):
    self.field = self.fieldKlass(
        initData=os.path.join(self.testCaseFileAbsPath, "unaccessable"),
        )
    self.renderWidget(self.field)

    with self.assertRaises(ValidationError):
      self.assertEqual(self.field.clean(self.field.finalData), {})

class StringGroupFilterFieldTestCase(FieldTestCaseBase, TestCase):
  fieldKlass = field.StringGroupFilterField
  def getInitData(self):
    return (
        ("A", (("a", True), ("b", False))),
        ("B", (("c", False), ("d", False), ("e", False))),
        ("C", (("f", True), ("g", True)))
    )

class ModelValidateGroupFieldTestCase(FieldTestCaseBase, TestCase):
  fieldKlass = field.ModelValidateGroupField
  def getInitData(self):
    # Mocking a model which has links field
    dummyModel = Adapter.objects.all()[0]
    dummyModel.links = ["1"]
    return [
        BinaryClassifierHistory(
          ref=dummyModel,
          initState=[True],
          finalState=[False],
        )
    ]

class ListFieldTestCase(FieldTestCaseBase, TestCase):
  fieldKlass = field.ListField
  thisModule = sys.modules[__name__]
  def _getFieldKlass(self, fieldName):
    return  getattr(getattr(self.thisModule, fieldName), "fieldKlass")

  def getInitData(self):
    return []

  def extraInitParam(self):
    return {"field": self._getFieldKlass("BooleanFieldTestCase")()}

  def testEmptyInitValue(self):
    self.field = self.fieldKlass(**self.extraInitParam())
    self.renderWidget(self.field)
    self.assertEqual(self.field.initData, [])

  def testEmptyFinalValue(self):
    self.field = self.fieldKlass(**self.extraInitParam())
    self.renderWidget(self.field)
    self.field.minLen = 5
    with self.assertRaises(ValidationError):
      self.assertEqual(self.field.clean(self.field.finalData), [])
    self.field.minLen = 0
    self.assertEqual(self.field.clean(self.field.finalData), [])

  def testSingleElementInitValue(self):
    param = self.extraInitParam()
    param.update({"initData": [True]})
    self.field = self.fieldKlass(**param)
    self.renderWidget(self.field)
    self.assertEqual(self.field.initData, [True])
    self.assertEqual(self.field.clean(self.field.finalData), [True])

  def testMultipleElementInitValue(self):
    param = self.extraInitParam()
    param.update({"initData": [True, False]})
    self.field = self.fieldKlass(**param)
    self.renderWidget(self.field)
    self.assertEqual(self.field.initData, [True, False])
    self.assertEqual(self.field.clean(self.field.finalData), [True, False])

class DictFieldTestCase(FieldTestCaseBase, TestCase):
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

  def testEmptyFinalValue(self):
    self.field = self.fieldKlass(**self.extraInitParam())
    self.renderWidget(self.field)
    self.field.minLen = 5
    with self.assertRaises(ValidationError):
      self.field.clean(self.field.finalData)
    self.field.minLen = 0
    self.assertEqual(self.field.clean(self.field.finalData), {})

class PythonModuleFieldTestCase(FieldTestCaseBase, TestCase):
  fieldKlass = field.PythonModuleField

  def getInitData(self):
    return None

  def setUp(self):
    self.field = self.fieldKlass(autoImport=True)
    self.renderWidget(self.field)

  def testValidatePlain(self):
    self.field.autoImport = False
    self.assertEqual(self.field.validate("anything"), "anything")

  def testValidateAutoImport(self):
    from theory.utils.importlib import importClass
    expectedModule = importClass("theory.apps.command")
    self.assertEqual(self.field.validate("theory.apps.command"), expectedModule)
    self.assertRaises(ValidationError, self.field.validate, "theory.apps.command.blah")
    self.assertRaises(ValidationError, self.field.validate, "theory.apps.command.listCommand.ListCommand")

class PythonClassFieldTestCase(FieldTestCaseBase, TestCase):
  fieldKlass = field.PythonClassField

  def getInitData(self):
    return None

  def setUp(self):
    self.field = self.fieldKlass(autoImport=True)
    self.renderWidget(self.field)

  def testValidatePlain(self):
    self.field.autoImport = False
    self.assertEqual(self.field.validate("anything"), "anything")

  def testValidateAutoImport(self):
    from theory.utils.importlib import importClass
    expectedKlass = importClass("theory.apps.command.listCommand.ListCommand")

    with self.assertRaises(ValidationError):
      self.field.validate("theory.apps.command")
      self.field.klass_type = "theory.apps.command.baseCommand.SimpleCommand"
      self.field.validate("theory.apps.command.blah")
    self.assertEqual(self.field.validate("theory.apps.command.listCommand.ListCommand"), expectedKlass)

#class QuerysetFieldTestCase(FieldTestCaseBase, TestCase):
#  fieldKlass = field.QuerysetField
#
#  def getInitData(self):
#    return []
#
#  def setUp(self):
#    initParam = self.extraInitParam()
#    initParam.update({"initData": self.getInitData(), "autoImport": True})
#
#    self.field = self.fieldKlass(**initParam)
#    self.renderWidget(self.field)
#
#  def testValidData(self):
#    data = Adapter.objects.all()
#    self.field.finalData = data
#    self.assertEqual(self.field.finalData, data)
#
#    with self.assertRaises(ValidationError):
#      self.assertEqual(self.field.clean(self.field.finalData), data)
#
#  def testEmptyData(self):
#    self.field.required = False
#    self.assertEqual(self.field.finalData, [])
#
#    self.assertEqual(self.field.clean(self.field.finalData), [])
#
#  def testEmptyDataWithRequired(self):
#    with self.assertRaises(ValidationError):
#      self.assertEqual(self.field.clean(self.field.finalData), [])
#
#  def testValidDataWithNoAppAndNoModel(self):
#
#    initParam = self.extraInitParam()
#    initData = Adapter.objects.all()
#    initParam.update({"initData": initData, "autoImport": True})
#
#    self.field = self.fieldKlass(**initParam)
#
#    self.field.required = False
#    with self.assertRaises(ValidationError):
#      self.assertEqual(self.field.clean(self.field.finalData), initData)
#
#  def testEmptyDataWithFalseAutoImport(self):
#    self.field.autoImport = False
#    self.field.required = False
#    self.assertEqual(self.field.clean(self.field.finalData), [])
#
#  def testValidDataWithFalseAutoImport(self):
#    data = Adapter.objects.all()
#    self.field.finalData = data
#    self.field.autoImport = False
#    self.assertEqual(self.field.clean(self.field.finalData), data)
#
#  def testValidDataWithFalseAutoImportRequired(self):
#    self.field.finalData = []
#    self.field.autoImport = False
#    self.field.required = True
#    with self.assertRaises(ValidationError):
#      self.assertEqual(self.field.clean(self.field.finalData), [])
#
#  def testEmptyDataWithAppAndModelWithFalseAutoImport(self):
#    self.field.required = False
#    self.field.autoImport = False
#    self.field.app = "anything"
#    self.field.model = "anything"
#
#    self.assertEqual(self.field.clean(self.field.finalData), [])
#
#  def testValidInitData(self):
#    initData = Adapter.objects.all()
#    initParam = self.extraInitParam()
#    initParam.update(
#        {
#          "initData": initData,
#          "autoImport": True
#        })
#
#    self.field = self.fieldKlass(**initParam)
#    self.renderWidget(self.field)
#    self.assertEqual(self.field.finalData, initData)
#
#    with self.assertRaises(ValidationError):
#      self.assertEqual(self.field.clean(self.field.finalData), initData)
#
#    self.field.app = "theory.apps"
#    self.field.model = "Adapter"
#    # Mongoengine does not allow direct queryset comparison
#    self.assertEqual(
#        [i.id for i in self.field.clean(self.field.finalData)],
#        [i.id for i in initData],
#        )
#
#  def testInvalidInitData(self):
#    initData = [1234, 2345]
#    initParam = self.extraInitParam()
#    initParam.update(
#        {
#          "initData": initData,
#          "autoImport": True
#        })
#
#    self.field = self.fieldKlass(**initParam)
#    self.renderWidget(self.field)
#    self.assertEqual(
#        self.field.finalData,
#        initData
#        #[unicode(i) for i in initData]
#        )
#
#    with self.assertRaises(ValidationError):
#     self.assertEqual(self.field.clean(self.field.finalData), initData)
#
#    self.field.app = "theory"
#    self.field.model = "Adapter"
#    with self.assertRaises(ValidationError):
#      self.assertEqual(self.field.clean(self.field.finalData), initData)
#
#    self.field.autoImport = False
#    self.field.app = None
#    self.field.model = None
#    self.assertEqual(self.field.clean(self.field.finalData), initData)

class ModelChoiceFieldTestCase(FieldTestCaseBase, TestCase):
  # will NOT validate invalid data
  fieldKlass = ModelChoiceField

  def getInitData(self):
    return 1

  def testInitDataInOneLine(self):
    pass

  def setUp(self):
    initParam = self.extraInitParam()

    queryset = Adapter.objects.all()
    self.field = self.fieldKlass(queryset, **initParam)
    self.renderWidget(self.field)

  def testValidData(self):
    data = Adapter.objects.all()
    self.field.finalData = data
    self.assertEqual(self.field.finalData, data)

  def testEmptyData(self):
    # The field will be returned as None and modelTblFilterBase should
    # change it as []
    self.field.required = False
    self.assertEqual(self.field.finalData, None)

    self.assertEqual(self.field.clean(self.field.finalData), None)

  def testEmptyDataWithRequired(self):
    with self.assertRaises(ValidationError):
      self.assertEqual(self.field.clean(self.field.finalData), [])

  def testValidInitData(self):
    queryset = Adapter.objects.all()
    initData = queryset.valuesList('pk', flat=True)[0]
    initParam = self.extraInitParam()
    initParam.update(
        {
          "initData": initData,
          "queryset": queryset,
        })

    self.field = self.fieldKlass(**initParam)
    self.renderWidget(self.field)

    # Note: the finalData can be a id list or queryset
    self.assertEqual(self.field.finalData, initData)

    self.assertEqual(self.field.queryset, queryset)

class ModelMultipleChoiceFieldTestCase(FieldTestCaseBase, TestCase):
  fieldKlass = ModelMultipleChoiceField

  def getInitData(self):
    return []

  def testInitDataInOneLine(self):
    pass

  def setUp(self):
    initParam = self.extraInitParam()

    self.queryset = Adapter.objects.all()
    self.field = self.fieldKlass(self.queryset, **initParam)
    self.renderWidget(self.field)

  def testValidData(self):
    data = list(self.queryset.valuesList('pk', flat=True))
    self.field.finalData = data
    self.assertEqual(self.field.finalData, data)

    # will return queryset. The only way to compare queryset is compared as
    # list
    self.assertEqual(
        list(self.field.clean(self.field.finalData)),
        list(self.queryset)
        )

  def testEmptyData(self):
    # The field will be returned as None and modelTblFilterBase should
    # change it as []
    self.field.required = False
    self.assertEqual(self.field.finalData, None)

    self.assertEqual(
        # Is similar to Adapter.objects.none()
        list(self.field.clean(self.field.finalData)),
        []
        )

  def testEmptyDataWithRequired(self):
    with self.assertRaises(ValidationError):
        self.assertEqual(self.field.clean(self.field.finalData), [])

  def testInvalidInitData(self):
    initData = [999, 1000, 1001]
    initParam = self.extraInitParam()
    initParam.update(
        {
          "initData": initData,
          "queryset": self.queryset,
        })

    self.field = self.fieldKlass(**initParam)
    self.renderWidget(self.field)

    self.assertEqual(self.field.finalData, initData)
    with self.assertRaises(ValidationError):
      self.assertEqual(self.field.clean(self.field.finalData), initData)
