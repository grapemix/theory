# -*- coding: utf-8 -*-
##### System wide lib #####
from elementary import Window, ELM_WIN_BASIC

##### Theory lib #####
from theory.conf import settings
from theory.core.exceptions import ValidationError
from theory.model import Adapter, BinaryClassifierHistory
from theory.gui import field
from theory.gui import widget
from theory.gui.etk.element import Box
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
  pass

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
  pass

class DictFieldWidgetTestCase(DictFieldTestCase, FieldWidgetTestCaseBase):
  pass

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
