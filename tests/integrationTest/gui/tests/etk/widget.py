# -*- coding: utf-8 -*-
##### System wide lib #####

##### Theory lib #####
from theory.core.exceptions import ValidationError
from theory.gui import field
from theory.gui.etk.element import Multibuttonentry, Entry
from theory.model import Adapter
from theory.utils import unittest

##### Theory third-party lib #####

##### Local app #####
from tests.integrationTest.gui.tests.field import FieldTestCaseBase
from tests.integrationTest.gui.tests.field import *
from dummyEnv import getDummyEnv

##### Theory app #####

##### Misc #####

__all__ = ('AdapterFieldWidgetTestCase', 'BooleanFieldWidgetTestCase',
    'ChoiceFieldWidgetTestCase', 'DecimalFieldWidgetTestCase',
    'DictFieldWidgetTestCase', 'EmailFieldWidgetTestCase',
    'FileFieldWidgetTestCase', 'FilePathFieldWidgetTestCase',
    'DirPathFieldWidgetTestCase', 'ImagePathFieldTestCase',
    'FloatFieldWidgetTestCase', 'GenericIPAddressFieldWidgetTestCase',
    'IPAddressFieldWidgetTestCase', 'ImageFieldWidgetTestCase',
    'IntegerFieldWidgetTestCase', 'ListFieldWidgetTestCase',
    'ModelValidateGroupFieldWidgetTestCase',
    'MultipleChoiceFieldWidgetTestCase',
    'NullBooleanFieldWidgetTestCase', 'RegexFieldWidgetTestCase',
    'SlugFieldWidgetTestCase', 'StringGroupFilterFieldWidgetTestCase',
    'TextFieldWidgetTestCase',
    'TypedChoiceFieldWidgetTestCase', 'TypedMultipleChoiceFieldWidgetTestCase',
    'URLFieldWidgetTestCase', 'PythonModuleFieldWidgetTestCase',
    'PythonClassFieldWidgetTestCase', 'QuerysetFieldWidgetTestCase',
    )

class FieldWidgetTestCaseBase(FieldTestCaseBase):
  def extraWidgetParam(self):
    return {}

  def renderWidget(self, field, *args, **kwargs):
    (dummyWin, dummyBx) = getDummyEnv()

    dummyBx.generate()
    field.renderWidget(dummyWin, dummyBx.obj, **self.extraWidgetParam())
    dummyBx.addInput(field.widget)
    dummyBx.postGenerate()
    self.dummyWin = dummyWin

  def tearDown(self):
    if(self.dummyWin is not None):
      self.dummyWin.delete()
      del self.dummyWin
      self.dummyWin = None

class BooleanFieldWidgetTestCase(BooleanFieldTestCase, FieldWidgetTestCaseBase):
  pass

class DecimalFieldWidgetTestCase(DecimalFieldTestCase, FieldWidgetTestCaseBase):
  pass

class EmailFieldWidgetTestCase(EmailFieldTestCase, FieldWidgetTestCaseBase):
  pass

class DirPathFieldWidgetTestCase(
    DirPathFieldTestCase,
    FieldWidgetTestCaseBase
    ):
  pass

class FilePathFieldWidgetTestCase(
    FilePathFieldTestCase,
    FieldWidgetTestCaseBase
    ):
  pass

class ImagePathFieldWidgetTestCase(
    FilePathFieldTestCase,
    FieldWidgetTestCaseBase
    ):
  pass

class FileFieldWidgetTestCase(FileFieldTestCase, FieldWidgetTestCaseBase):
  pass

class FloatFieldWidgetTestCase(FloatFieldTestCase, FieldWidgetTestCaseBase):
  pass

class GenericIPAddressFieldWidgetTestCase(
    GenericIPAddressFieldTestCase,
    FieldWidgetTestCaseBase
    ):
  pass

class IPAddressFieldWidgetTestCase(
    IPAddressFieldTestCase,
    FieldWidgetTestCaseBase
    ):
  pass

class IntegerFieldWidgetTestCase(IntegerFieldTestCase, FieldWidgetTestCaseBase):
  def testInitDataInWidget(self):
    param = {
        "initData": 2
    }
    self.field = self.fieldKlass(**param)
    self.renderWidget(self.field)
    self.assertEqual(len(self.field.widget.widgetLst), 2)
    self.assertTrue(isinstance(self.field.widget.widgetLst[0], Entry))
    self.assertEqual(self.field.widget.widgetLst[0].finalData, "2")
    self.assertEqual(self.field.finalData, "2")
    self.assertEqual(self.field.clean(self.field.finalData), 2)

  def testInvalidInitDataInWidget(self):
    param = {
        "initData": "a"
    }
    self.field = self.fieldKlass(**param)
    self.renderWidget(self.field)
    with self.assertRaises(ValidationError):
      self.assertEqual(self.field.clean(self.field.finalData), "a")

  def testInvalidDataInWidget(self):
    self.field = self.fieldKlass()
    self.renderWidget(self.field)
    self.field.finalData = "a"
    with self.assertRaises(ValidationError):
      self.assertEqual(self.field.clean(self.field.finalData), "a")

  def testValidDataAssignmentInWidget(self):
    self.field = self.fieldKlass()
    self.renderWidget(self.field)
    self.field.finalData = 3
    self.assertEqual(self.field.clean(self.field.finalData), 3)

class TextFieldWidgetTestCase(TextFieldTestCase, FieldWidgetTestCaseBase):

  def testAssignFinalDataWithWidget(self):
    self.field = self.fieldKlass(initData="test")
    self.renderWidget(self.field)

    self.assertEqual(self.field.initData, "test")

    self.field.widget.reset(finalData="for real")
    self.assertEqual(self.field.initData, "test")
    self.assertEqual(self.field.finalData, "for real")
    self.assertEqual(self.field.clean(self.field.finalData), "for real")

    self.field.widget.reset(finalData="for real again")
    # formBase will set finalData as None if an error exists
    self.field.finalData = None
    self.assertEqual(self.field.initData, "test")
    self.assertEqual(self.field.finalData, "for real again")
    self.assertEqual(self.field.clean(self.field.finalData), "for real again")

  def testAccessEmptyFinalDataWithWidget(self):
    self.field = self.fieldKlass(initData="test")
    self.renderWidget(self.field)
    self.assertEqual(self.field.initData, "test")
    self.assertEqual(self.field.finalData, "test")

class URLFieldWidgetTestCase(URLFieldTestCase, FieldWidgetTestCaseBase):
  pass

class ChoiceFieldWidgetTestCase(ChoiceFieldTestCase, FieldWidgetTestCaseBase):
  pass

class MultipleChoiceFieldWidgetTestCase(
    MultipleChoiceFieldTestCase,
    FieldWidgetTestCaseBase
    ):
  pass


class TypedChoiceFieldWidgetTestCase(
    TypedChoiceFieldTestCase,
    MultipleChoiceFieldTestCase
    ):
  pass

class TypedMultipleChoiceFieldWidgetTestCase(
   TypedMultipleChoiceFieldTestCase,
   MultipleChoiceFieldTestCase
   ):
  pass

class AdapterFieldWidgetTestCase(
    AdapterFieldTestCase,
    FieldWidgetTestCaseBase
    ):

  def extraWidgetParam(self):
    #return self._getMockAdapterObject(Adapter(name="dummyAdapter"), "fake.path")
    try:
      Adapter.objects.get(name="DummyForTest").delete()
    except:
      pass
    adapter = Adapter(name="DummyForTest", importPath="fake.path")
    adapter.save()
    return {"attrs": {"choices": {"DummyForTest": True}}}

class SlugFieldWidgetTestCase(SlugFieldTestCase, FieldWidgetTestCaseBase):
  pass

class NullBooleanFieldWidgetTestCase(
    NullBooleanFieldTestCase,
    FieldWidgetTestCaseBase
    ):
  pass

class RegexFieldWidgetTestCase(RegexFieldTestCase, FieldWidgetTestCaseBase):
  pass

class ImageFieldWidgetTestCase(ImageFieldTestCase, FileFieldTestCase):
  pass

class StringGroupFilterFieldWidgetTestCase(
    StringGroupFilterFieldTestCase,
    FieldWidgetTestCaseBase
    ):
  pass

class ModelValidateGroupFieldWidgetTestCase(
    ModelValidateGroupFieldTestCase,
    FieldWidgetTestCaseBase
    ):
  pass

class ListFieldWidgetTestCase(ListFieldTestCase, FieldWidgetTestCaseBase):
  def testTextWidget(self):
    param = {
        "field": self._getFieldKlass("TextFieldTestCase")(max_length=200),
        "initData": ["aa", "bb"]
    }
    self.field = self.fieldKlass(**param)
    self.renderWidget(self.field)
    self.assertEqual(len(self.field.widget._inputLst), 1)
    self.assertTrue(isinstance(self.field.widget._inputLst[0], Entry))
    self.assertEqual(self.field.widget._inputLst[0].finalData, "aa<br/>bb")
    self.assertEqual(self.field.clean(self.field.finalData), ["aa", "bb"])

  def testTextWidgetWithShortString(self):
    param = {
        "field": self._getFieldKlass("TextFieldTestCase")(max_length=2),
        "initData": ["aa", "bb"]
        }
    self.field = self.fieldKlass(**param)
    self.renderWidget(self.field)
    self.assertTrue(
        isinstance(self.field.widget._inputLst[0], Multibuttonentry)
    )
    self.assertEqual(self.field.clean(self.field.finalData), ["aa", "bb"])

class DictFieldWidgetTestCase(DictFieldTestCase, FieldWidgetTestCaseBase):
  def testSingleElementInitValue(self):
    param = self.extraInitParam()
    param.update({"initData": {"1": "a"}})
    self.field = self.fieldKlass(**param)
    self.renderWidget(self.field)
    self.assertEqual(self.field.initData, {"1": "a"})
    self.assertEqual(self.field.clean(self.field.finalData), {"1": "a"})

  def testMultipleElementInitValue(self):
    param = self.extraInitParam()
    param.update({"initData": {"1": "a", "2": "b"}})
    self.field = self.fieldKlass(**param)
    self.renderWidget(self.field)
    self.assertEqual(self.field.initData, {"1": "a", "2": "b"})
    self.assertEqual(
        self.field.clean(self.field.finalData),
        {"1": "a", "2": "b"}
    )

class PythonModuleFieldWidgetTestCase(
    PythonModuleFieldTestCase,
    FieldWidgetTestCaseBase
    ):
  pass

class PythonClassFieldWidgetTestCase(
    PythonClassFieldTestCase,
    FieldWidgetTestCaseBase
    ):
  pass

class QuerysetFieldWidgetTestCase(
    QuerysetFieldTestCase,
    FieldWidgetTestCaseBase
    ):
  pass
