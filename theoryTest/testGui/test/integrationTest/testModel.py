# -*- coding: utf-8 -*-
##### System wide lib #####
from collections import OrderedDict

##### Theory lib #####
from theory.apps.model import Command, AppModel
from theory.conf import settings
from theory.gui import field
from theory.gui import widget
from theory.gui.etk.form import StepFormBase
from theory.gui.model import *
from theory.test.testcases import TestCase

##### Theory third-party lib #####

##### Local app #####

##### Theory app #####

##### Misc #####
from testGui.test.integrationTest.etk.testDummyEnv import getDummyEnv
from testBase.model import (
    CombinatoryModelWithDefaultValue,
    )

__all__ = ('ModelFormTestCase',)

modelObj = CombinatoryModelWithDefaultValue()

class ModelFormTestCase(TestCase):
  """
  To test the Formset.
  """
  fixtures = ["combinatoryAppConfig",]
  def __init__(self, *args, **kwargs):
    super(ModelFormTestCase, self).__init__(*args, **kwargs)
    (dummyWin, dummyBx) = getDummyEnv()
    self.uiParam = OrderedDict([
        ("win", dummyWin),
        ("bx", dummyBx.obj),
        ("unFocusFxn", lambda: True)
        ])

  def getModelFormKlass(self):
    class TestModelModelForm(ModelForm):
      class Meta:
        model = CombinatoryModelWithDefaultValue
        exclude = []
    return TestModelModelForm

  def getGuiModelFormKlass(self, dynModel):
    class DynamicModelForm(ModelForm, StepFormBase):
      class Meta:
        model = dynModel
        exclude = []
    return DynamicModelForm

  #def _testEmbeddedObj(self, o1, o2):
  #  try:
  #    self.assertEqual(o1, o2)
  #  except AssertionError:
  #    self.assertEqual(o1._data, o2._data)

  def testSetup(self):
    form = self.getModelFormKlass()()
    for fieldName, v in form.fields.items():
      if fieldName in ["referenceField", "m2mField", "m2mThruField"]:
        pass
      else:
        self.assertEqual(v.initData, getattr(modelObj, fieldName))
    #for fieldName, v in form.fields.items():
    #  fieldTypeStr = type(v).__name__
    #  if(len(fieldName)>len(fieldTypeStr)):
    #    if(fieldName.startswith("sortedList")):
    #      childFieldTypeStr = fieldName[15].lower() + fieldName[16:]
    #    elif(not fieldName.startswith("map")):
    #      childFieldTypeStr = fieldName[9].lower() + fieldName[10:]
    #    else:
    #      childFieldTypeStr = fieldName[8].lower() + fieldName[9:]
    #  else:
    #    childFieldTypeStr = ""

    #  if(childFieldTypeStr=="embeddedField"):
    #    childFieldTypeStr = "embeddedDocumentField"
    #  if(fieldTypeStr=="ListField"):
    #    self._testEmbeddedObj(
    #          v.fields[0].to_python(v.fields[0].initData),
    #          getattr(modelObj, childFieldTypeStr)
    #          )
    #  elif(fieldTypeStr=="DictField"):
    #    self._testEmbeddedObj(
    #          v.valueFields[0].to_python(v.valueFields[0].initData),
    #          getattr(modelObj, childFieldTypeStr)
    #          )
    #  elif(fieldName=="choiceField"):
    #    self._testEmbeddedObj(
    #          str(v.to_python(v.initData)), str(getattr(modelObj, fieldName))
    #          )
    #  elif(fieldName=="referenceField"):
    #    pass
    #  elif(fieldName not in ["fileField", "id", "imageField"]):
    #    self._testEmbeddedObj(
    #          v.to_python(v.initData), getattr(modelObj, fieldName)
    #          )

  def testFormGenenarate(self):
    form = self.getGuiModelFormKlass(
        CombinatoryModelWithDefaultValue
        )()

    # Del me after the bug form e17 which affect fileField widget has been fixed
    #form.fields["fileField"].initData = "/tmp/a.jpg"
    #form.fields["imageField"].initData = "/tmp/a.jpg"
    if not hasattr(settings, "dimensionHints"):
      settings.dimensionHints = {
          "minWidth": 640,
          "minHeight":480,
          "maxWidth": 640,
          "maxHeight": 480
          }

    form.generateForm(**self.uiParam)
    form.generateStepControl()
