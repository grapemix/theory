# -*- coding: utf-8 -*-
##### System wide lib #####
from collections import defaultdict
from datetime import datetime
from ludibrio import Stub
import os

##### Theory lib #####
from theory.apps.model import AppModel
from theory.contrib.postgres.fields import ArrayField
from theory.core.resourceScan.modelClassScanner import ModelClassScanner
from theory.db import model

##### Theory third-party lib #####

##### Local app #####

##### Theory app #####

##### Misc #####

__all__ = (
    'CombinatoryModelWithDefaultValue',
    'DummyAppModelManager',
    )

def getTestCaseFileAbsPath():
  return os.path.join(
      os.path.dirname(__file__),
      "testsFile",
      "field"
  )

def getBinaryDefault():
  return bin(10)

def getImageDefault():
  # All errors should not be catched
  fileHandler = open(os.path.join(getTestCaseFileAbsPath(), "jpeg.jpg"), "rb")
  dummyImg = fileHandler.read()
  fileHandler.close()
  return dummyImg

def getFileDefault():
  return getImageDefault()

def getBooleanDefault():
  return True

def getDateTimeDefault():
  return datetime(1970, 01, 01, 00, 00, 01, 999),

def getDecimalDefault():
  return 1.0

def getFloatDefault():
  return 1.0

def getIntDefault():
  return 1

def getStringDefault():
  return u"test"

def getEmailDefault():
  return u"test@test.com"

def getURLDefault():
  return u"http://google.com"


defaultValueSet1 = {
    "Binary": getBinaryDefault(),
    "Image": getImageDefault(),
    "File": getImageDefault(),
    "Boolean": True,
    "DateTime": datetime(1970, 01, 01, 00, 00, 01, 999),
    "Decimal": 1.0,
    "Float": 1.0,
    "Int": 1,
    "String": u"test",
    "Email": u"test@test.com",
    "URL": u"http://google.com/",
}

class DummyAppModelManager(object):
  #def registerModel(
  #    self,
  #    importPath,
  #    modelKlass,
  #    ):

  #  if(AppModel.objects.filter(importPath=importPath).count()==1):
  #    return

  #  modelKlassName = importPath.split(".")[-1]

  #  modelTemplate = AppModel(importPath=importPath + "__init__")
  #  o = ModelClassScanner()
  #  o.modelTemplate = modelTemplate
  #  o.modelDepMap = defaultdict(list)
  #  model = o._probeModelField(modelKlassName, modelKlass)
  #  model.importPath = importPath
  #  model.save()

  #def registerAllModel(self):
  #  basePath = "testBase.model.combinatoryModel"

  #  klassNameLst = [
  #      (
  #        'CombinatoryModelWithDefaultValue',
  #        CombinatoryModelWithDefaultValue,
  #        False
  #        ),
  #      (
  #        'CombinatoryModelLiteWithDefaultValue',
  #        CombinatoryModelLiteWithDefaultValue,
  #        False
  #        ),
  #      ]

  #  for klassParam in klassNameLst:
  #    self.registerModel(
  #        basePath + "." + klassParam[0],
  #        klassParam[1],
  #        #klassParam[2],
  #        )

  def getCombinatoryQuerySet(self, modelLst):
    CombinatoryModelWithDefaultValue.objects.all().delete()
    for model in modelLst:
      model.save()
    return CombinatoryModelWithDefaultValue.objects.all()

  def getCombinatoryModelWithDefaultValue(self):
    child = CombinatoryModelLiteWithDefaultValue()
    child.save()
    o = CombinatoryModelWithDefaultValue()
    o.referenceField = child
    o.save()
    return o
    #return child

  def getQuerySet(self):
    return CombinatoryModelWithDefaultValue.objects.all()

class CombinatoryModelLiteWithDefaultValue(model.Model):
  DUMMY_CHOICE_ONE = 1
  DUMMY_CHOICE_TWO = 2
  DUMMY_CHOICES = (
      (DUMMY_CHOICE_ONE, "Dummy Choice One"),
      (DUMMY_CHOICE_TWO, "Dummy Choice Two"),
      )
  binaryField = model.BinaryField(default=defaultValueSet1["Binary"])
  #fileField = model.FileField(default=defaultValueSet1["File"])
  #imageField = model.ImageField(default=defaultValueSet1["Image"])
  booleanField = model.BooleanField(default=defaultValueSet1["Boolean"])
  dateTimeField = model.DateTimeField(default=defaultValueSet1["DateTime"])
  decimalField = model.DecimalField(default=defaultValueSet1["Decimal"], maxDigits=5, decimalPlaces=3)
  floatField = model.FloatField(default=defaultValueSet1["Float"])
  intField = model.IntegerField(default=defaultValueSet1["Int"])
  stringField = model.TextField(default=defaultValueSet1["String"])
  emailField = model.EmailField(default=defaultValueSet1["Email"])
  uRLField = model.URLField(default=defaultValueSet1["URL"])
  choiceField = model.IntegerField(choices=DUMMY_CHOICES, default=DUMMY_CHOICE_ONE)

  #listFieldBinaryField = ArrayField(model.BinaryField(), default=[defaultValueSet1["Binary"],])
  listFieldBooleanField = ArrayField(model.BooleanField(), default=[defaultValueSet1["Boolean"],])
  listFieldDateTimeField = ArrayField(model.DateTimeField(), default=[defaultValueSet1["DateTime"],])
  listFieldDecimalField = ArrayField(model.DecimalField(decimalPlaces=3, maxDigits=5), default=[defaultValueSet1["Decimal"],])
  listFieldEmailField = ArrayField(model.EmailField(), default=[defaultValueSet1["Email"],])
  listFieldFloatField = ArrayField(model.FloatField(), default=[defaultValueSet1["Float"],])
  #listFieldFileField = ArrayField(model.FileField(), default=[defaultValueSet1["File"],])
  #listFieldImageField = ArrayField(model.ImageField(), default=[defaultValueSet1["Image"],])
  listFieldIntegerField = ArrayField(model.IntegerField(), default=[defaultValueSet1["Int"],])
  listFieldTextField = ArrayField(model.TextField(), default=[defaultValueSet1["String"],])
  listFieldURLField = ArrayField(model.URLField(), default=[defaultValueSet1["URL"],])

  #meta = {'collection': 'tests_CombinatoryModelWithDefaultValue'}

class CombinatoryModelWithDefaultValue(model.Model):
  DUMMY_CHOICE_ONE = 1
  DUMMY_CHOICE_TWO = 2
  DUMMY_CHOICES = (
      (DUMMY_CHOICE_ONE, "Dummy Choice One"),
      (DUMMY_CHOICE_TWO, "Dummy Choice Two"),
      )
  binaryField = model.BinaryField(default=defaultValueSet1["Binary"])
  #fileField = model.FileField(default=defaultValueSet1["File"])
  #imageField = model.ImageField(default=defaultValueSet1["Image"])
  booleanField = model.BooleanField(default=defaultValueSet1["Boolean"])
  dateTimeField = model.DateTimeField(default=defaultValueSet1["DateTime"])
  decimalField = model.DecimalField(default=defaultValueSet1["Decimal"], maxDigits=5, decimalPlaces=3)
  floatField = model.FloatField(default=defaultValueSet1["Float"])
  intField = model.IntegerField(default=defaultValueSet1["Int"])
  stringField = model.TextField(default=defaultValueSet1["String"])
  emailField = model.EmailField(default=defaultValueSet1["Email"])
  uRLField = model.URLField(default=defaultValueSet1["URL"])
  choiceField = model.IntegerField(choices=DUMMY_CHOICES, default=DUMMY_CHOICE_ONE)

  referenceField = model.ForeignKey('CombinatoryModelLiteWithDefaultValue')

  #listFieldBinaryField = ArrayField(model.BinaryField(), default=[defaultValueSet1["Binary"],])
  listFieldBooleanField = ArrayField(model.BooleanField(), default=[defaultValueSet1["Boolean"],])
  listFieldDateTimeField = ArrayField(model.DateTimeField(), default=[defaultValueSet1["DateTime"],])
  listFieldDecimalField = ArrayField(model.DecimalField(decimalPlaces=3, maxDigits=5), default=[defaultValueSet1["Decimal"],])
  listFieldEmailField = ArrayField(model.EmailField(), default=[defaultValueSet1["Email"],])
  listFieldFloatField = ArrayField(model.FloatField(), default=[defaultValueSet1["Float"],])
  #listFieldFileField = ArrayField(model.FileField(), default=[defaultValueSet1["File"],])
  #listFieldImageField = ArrayField(model.ImageField(), default=[defaultValueSet1["Image"],])
  listFieldIntegerField = ArrayField(model.IntegerField(), default=[defaultValueSet1["Int"],])
  listFieldTextField = ArrayField(model.TextField(), default=[defaultValueSet1["String"],])
  listFieldURLField = ArrayField(model.URLField(), default=[defaultValueSet1["URL"],])

  #meta = {'collection': 'tests_CombinatoryModelWithDefaultValue'}

