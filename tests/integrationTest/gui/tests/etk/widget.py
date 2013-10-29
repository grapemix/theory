# -*- coding: utf-8 -*-
##### System wide lib #####
from elementary import Window, ELM_WIN_BASIC

##### Theory lib #####
from theory.conf import settings
from theory.core.exceptions import ValidationError
from theory.model import Adapter, BinaryClassifierHistory
from theory.gui import field
from theory.gui import widget
from theory.gui.etk.element import Box, Multibuttonentry, Entry
from theory.gui.form import *
from theory.utils import unittest

##### Theory third-party lib #####

##### Local app #####
from tests.integrationTest.gui.tests.field import FieldTestCaseBase
from tests.integrationTest.gui.tests.field import *

##### Theory app #####

##### Misc #####

__all__ = ('AdapterFieldWidgetTestCase', 'BooleanFieldWidgetTestCase',
    'ChoiceFieldWidgetTestCase', 'DecimalFieldWidgetTestCase',
    'DictFieldWidgetTestCase', 'EmailFieldWidgetTestCase',
    #'FileFieldWidgetTestCase', 'FilePathFieldWidgetTestCase',
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
    'PythonClassFieldWidgetTestCase',
    )

class FieldWidgetTestCaseBase(FieldTestCaseBase):
  def renderWidget(self, field, *args, **kwargs):
    dummyWin = Window("theory", ELM_WIN_BASIC)

    # Copied from gui.etk.widget._createContainer
    dummyBx = Box()
    dummyBx.win = dummyWin

    dummyBx.generate()
    field.renderWidget(dummyWin, dummyBx.obj)
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

#class FilePathFieldWidgetTestCase(
#    FilePathFieldTestCase,
#    FieldWidgetTestCaseBase
#    ):
#  pass
#
#class FileFieldWidgetTestCase(FileFieldTestCase, FieldWidgetTestCaseBase):
#  pass

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
  pass

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
  pass

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
