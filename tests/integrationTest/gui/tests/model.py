# -*- coding: utf-8 -*-
##### System wide lib #####
from collections import OrderedDict
from ludibrio import Stub

##### Theory lib #####
from theory.gui import field
from theory.gui import widget
from theory.gui.etk.form import StepFormBase
from theory.gui.model import *
from theory.model import Command, AppModel
from theory.utils import unittest

##### Theory third-party lib #####

##### Local app #####

##### Theory app #####

##### Misc #####
from tests.integrationTest.gui.tests.etk.dummyEnv import getDummyEnv
from tests.testBase.model.combinatoryModel import (
    CombinatoryModelWithDefaultValue,
    DummyAppModelManager,
    )

__all__ = ('ModelFormTestCase',)

modelObj = CombinatoryModelWithDefaultValue()

class ModelFormTestCase(unittest.TestCase):
  """
  To test the Formset.
  """
  def __init__(self, *args, **kwargs):
    super(ModelFormTestCase, self).__init__(*args, **kwargs)
    (dummyWin, dummyBx) = getDummyEnv()
    self.uiParam = OrderedDict([
        ("win", dummyWin),
        ("bx", dummyBx.obj),
        ("unFocusFxn", lambda: True)
        ])
    DummyAppModelManager().registerAllModel()

  def getModelFormKlass(self):
    class TestModelModelForm(ModelForm):
      class Meta:
        model = "testBase.model.combinatoryModel.CombinatoryModelWithDefaultValue"
    return TestModelModelForm

  def getGuiModelFormKlass(self, importPath):
    class DynamicModelForm(ModelForm, StepFormBase):
      class Meta:
        model = importPath
    return DynamicModelForm

  def _testEmbeddedObj(self, o1, o2):
    try:
      self.assertEqual(o1, o2)
    except AssertionError:
      self.assertEqual(o1._data, o2._data)

  def testSetup(self):
    form = self.getModelFormKlass()()
    for fieldName, v in form.fields.iteritems():
      fieldTypeStr = type(v).__name__
      if(len(fieldName)>len(fieldTypeStr)):
        if(fieldName.startswith("sortedList")):
          childFieldTypeStr = fieldName[15].lower() + fieldName[16:]
        elif(not fieldName.startswith("map")):
          childFieldTypeStr = fieldName[9].lower() + fieldName[10:]
        else:
          childFieldTypeStr = fieldName[8].lower() + fieldName[9:]
      else:
        childFieldTypeStr = ""

      if(childFieldTypeStr=="embeddedField"):
        childFieldTypeStr = "embeddedDocumentField"
      if(fieldTypeStr=="ListField"):
        self._testEmbeddedObj(
              v.fields[0].to_python(v.fields[0].initData),
              getattr(modelObj, childFieldTypeStr)
              )
      elif(fieldTypeStr=="DictField"):
        self._testEmbeddedObj(
              v.valueFields[0].to_python(v.valueFields[0].initData),
              getattr(modelObj, childFieldTypeStr)
              )
      else:
        if(fieldName not in ["fileField", "id", "imageField"]):
          self._testEmbeddedObj(
                v.to_python(v.initData), getattr(modelObj, fieldName)
                )

  def testFormGenenarate(self):
    form = self.getGuiModelFormKlass(
        "testBase.model.combinatoryModel.CombinatoryModelWithDefaultValue"
        )()

    # Del me after the bug form e17 which affect fileField widget has been fixed
    form.fields["fileField"].initData = "/tmp/a.jpg"
    form.fields["imageField"].initData = "/tmp/a.jpg"

    form.generateForm(**self.uiParam)
    form.generateStepControl()
