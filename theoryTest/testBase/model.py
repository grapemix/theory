# -*- coding: utf-8 -*-
##### System wide lib #####
from collections import defaultdict
import datetime
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
  return b'10'

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
  return datetime.datetime(1970, 1, 1, 0, 0, 1, 999)

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
    "DateTime": datetime.datetime(1970, 1, 1, 0, 0, 1, 999),
    "Decimal": 1.0,
    "Float": 1.0,
    "Int": 1,
    "String": u"test",
    "Email": u"test@test.com",
    "URL": u"http://google.com/",
}

class DummyAppModelManager(object):
  def getCombinatoryQuerySet(self, modelLst):
    CombinatoryModelWithDefaultValue.objects.all().delete()
    for model in modelLst:
      model.save()
    return CombinatoryModelWithDefaultValue.objects.all()

  def getQuerySet(self):
    return CombinatoryModelWithDefaultValue.objects.all()

class ThruModel(model.Model):
  lhs = model.ForeignKey("CombinatoryModelWithDefaultValue", relatedName="lhs")
  rhs = model.ForeignKey("CombinatoryModelWithDefaultValue", relatedName="rhs")
  booleanField = model.BooleanField(default=defaultValueSet1["Boolean"])

class CombinatoryModelWithDefaultValue(model.Model):
  DUMMY_CHOICE_ONE = 1
  DUMMY_CHOICE_TWO = 2
  DUMMY_CHOICES = (
      (DUMMY_CHOICE_ONE, "Dummy Choice One"),
      (DUMMY_CHOICE_TWO, "Dummy Choice Two"),
      )
  binaryField = model.BinaryField(default=defaultValueSet1["Binary"])
  booleanField = model.BooleanField(default=defaultValueSet1["Boolean"])
  dateTimeField = model.DateTimeField(default=defaultValueSet1["DateTime"])
  decimalField = model.DecimalField(default=defaultValueSet1["Decimal"], maxDigits=5, decimalPlaces=3)
  floatField = model.FloatField(default=defaultValueSet1["Float"])
  intField = model.IntegerField(default=defaultValueSet1["Int"])
  stringField = model.TextField(default=defaultValueSet1["String"])
  emailField = model.EmailField(default=defaultValueSet1["Email"])
  uRLField = model.URLField(default=defaultValueSet1["URL"])
  choiceField = model.IntegerField(choices=DUMMY_CHOICES, default=DUMMY_CHOICE_ONE)

  referenceField = model.ForeignKey(
    'self',
    null=True,
    blank=True,
  )
  m2mField = model.ManyToManyField(
    'self',
    null=True,
    blank=True,
  )
  m2mThruField = model.ManyToManyField(
    'self',
    null=True,
    blank=True,
    through='ThruModel',
  )

  listFieldBooleanField = ArrayField(model.BooleanField(), default=[defaultValueSet1["Boolean"],])
  listFieldDateTimeField = ArrayField(model.DateTimeField(), default=[defaultValueSet1["DateTime"],])
  listFieldDecimalField = ArrayField(model.DecimalField(decimalPlaces=3, maxDigits=5), default=[defaultValueSet1["Decimal"],])
  listFieldEmailField = ArrayField(model.EmailField(), default=[defaultValueSet1["Email"],])
  listFieldFloatField = ArrayField(model.FloatField(), default=[defaultValueSet1["Float"],])
  listFieldIntegerField = ArrayField(model.IntegerField(), default=[defaultValueSet1["Int"],])
  listFieldTextField = ArrayField(model.TextField(), default=[defaultValueSet1["String"],])
  listFieldURLField = ArrayField(model.URLField(), default=[defaultValueSet1["URL"],])
