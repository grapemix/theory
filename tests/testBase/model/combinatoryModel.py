# -*- coding: utf-8 -*-
##### System wide lib #####
from datetime import datetime
import os
import uuid

##### Theory lib #####
from theory.core.resourceScan.modelClassScanner import ModelClassScanner
from theory.db import models
from theory.model import AppModel

##### Theory third-party lib #####

##### Local app #####

##### Theory app #####

##### Misc #####

__all__ = (
    'CombinatoryModelWithDefaultValue',
    'CombinatoryEmbeddedModelWithDefaultValue',
    'DummyAppModelManager',
    )

def getTestCaseFileAbsPath():
  return os.path.join(
      os.path.dirname(os.path.dirname(__file__)),
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

def getComplexDateTimeDefault():
  return datetime(1970, 01, 01, 00, 00, 01, 999)

def getUUIDDefault():
  return uuid.uuid3(uuid.NAMESPACE_DNS, "google.com")

def getSequenceDefault():
  return 1

def getGeoPointDefault():
  return [1.0, 1.0]

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
    "ComplexDateTime": datetime(1970, 01, 01, 00, 00, 01, 999),
    "UUID": getUUIDDefault(),
    "Sequence": 1,
    "GeoPoint": [1.0, 1.0],
    "Decimal": 1.0,
    "Float": 1.0,
    "Int": 1,
    "String": u"test",
    "Email": u"test@test.com",
    "URL": u"http://google.com/",
}

class DummyAppModelManager(object):
  def registerModel(
      self,
      importPath,
      modelKlass,
      isEmbedded=False
      ):

    if(AppModel.objects.filter(importPath=importPath).count()==1):
      return

    modelKlassName = importPath.split(".")[-1]

    modelTemplate = AppModel(importPath=importPath + "__init__")
    o = ModelClassScanner()
    o.modelTemplate = modelTemplate
    model = o._probeModelField(modelKlassName, modelKlass)
    model.isEmbedded = isEmbedded
    model.importPath = importPath
    model.save()

  def registerAllModel(self):
    basePath = "testBase.model.combinatoryModel"

    klassNameLst = [
        (
          'CombinatoryModelWithDefaultValue',
          CombinatoryModelWithDefaultValue,
          False
          ),
        (
          'CombinatoryEmbeddedModelWithDefaultValue',
          CombinatoryEmbeddedModelWithDefaultValue,
          True
          ),
        (
          'CombinatoryModelLiteWithDefaultValue',
          CombinatoryModelLiteWithDefaultValue,
          False
          ),
        (
          'CombinatoryEmbeddedModelLiteWithDefaultValue',
          CombinatoryEmbeddedModelLiteWithDefaultValue,
          True
          ),
        ]

    for klassParam in klassNameLst:
      self.registerModel(
          basePath + "." + klassParam[0],
          klassParam[1],
          klassParam[2],
          )

  def getCombinatoryQuerySet(self, modelLst):
    CombinatoryModelWithDefaultValue.objects.all().delete()
    for model in modelLst:
      model.save()
    return CombinatoryModelWithDefaultValue.objects.all()

  def getCombinatoryModelWithDefaultValue(self):
    return CombinatoryModelWithDefaultValue()

  def getQuerySet(self):
    return CombinatoryModelWithDefaultValue.objects.all()


class CombinatoryEmbeddedModelLiteWithDefaultValue(models.EmbeddedDocument):
  binaryField = models.BinaryField(default=defaultValueSet1["Binary"])
  fileField = models.FileField(default=defaultValueSet1["File"])
  imageField = models.ImageField(default=defaultValueSet1["Image"])
  booleanField = models.BooleanField(default=defaultValueSet1["Boolean"])
  dateTimeField = models.DateTimeField(default=defaultValueSet1["DateTime"])
  #complexDateTimeField = models.ComplexDateTimeField(default=defaultValueSet1["ComplexDateTime"])
  uUIDField = models.UUIDField(default=defaultValueSet1["UUID"])
  sequenceField = models.SequenceField(default=defaultValueSet1["Sequence"])
  geoPointField = models.GeoPointField(default=defaultValueSet1["GeoPoint"])
  decimalField = models.DecimalField(default=defaultValueSet1["Decimal"])
  floatField = models.FloatField(default=defaultValueSet1["Float"])
  intField = models.IntField(default=defaultValueSet1["Int"])
  stringField = models.StringField(default=defaultValueSet1["String"])
  emailField = models.EmailField(default=defaultValueSet1["Email"])
  uRLField = models.URLField(default=defaultValueSet1["URL"])
  dynamicField = models.DynamicField()

  listFieldBinaryField = models.ListField(field=models.BinaryField(), default=[defaultValueSet1["Binary"],])
  listFieldBooleanField = models.ListField(field=models.BooleanField(), default=[defaultValueSet1["Boolean"],])
  #listFieldComplexDateTimeField = models.ListField(field=models.ComplexDateTimeField(), default=[defaultValueSet1["ComplexDateTime"],])
  listFieldDateTimeField = models.ListField(field=models.DateTimeField(), default=[defaultValueSet1["DateTime"],])
  listFieldDecimalField = models.ListField(field=models.DecimalField(), default=[defaultValueSet1["Decimal"],])
  listFieldEmailField = models.ListField(field=models.EmailField(), default=[defaultValueSet1["Email"],])
  listFieldFloatField = models.ListField(field=models.FloatField(), default=[defaultValueSet1["Float"],])
  listFieldGeoPointField = models.ListField(field=models.GeoPointField(), default=[defaultValueSet1["GeoPoint"],])
  #listFieldFileField = models.ListField(field=models.FileField(), default=[defaultValueSet1["File"],])
  #listFieldImageField = models.ListField(field=models.ImageField(), default=[defaultValueSet1["Image"],])
  listFieldIntField = models.ListField(field=models.IntField(), default=[defaultValueSet1["Int"],])
  listFieldSequenceField = models.ListField(field=models.SequenceField(), default=[defaultValueSet1["Sequence"],])
  listFieldStringField = models.ListField(field=models.StringField(), default=[defaultValueSet1["String"],])
  listFieldURLField = models.ListField(field=models.URLField(), default=[defaultValueSet1["URL"],])
  listFieldUUIDField = models.ListField(field=models.UUIDField(), default=[defaultValueSet1["UUID"],])

  sortedListFieldBinaryField = models.SortedListField(field=models.BinaryField(), default=[defaultValueSet1["Binary"],])
  sortedListFieldBooleanField = models.SortedListField(field=models.BooleanField(), default=[defaultValueSet1["Boolean"],])
  #sortedListFieldComplexDateTimeField = models.SortedListField(field=models.ComplexDateTimeField(), default=[defaultValueSet1["ComplexDateTime"],])
  sortedListFieldDateTimeField = models.SortedListField(field=models.DateTimeField(), default=[defaultValueSet1["DateTime"],])
  sortedListFieldDecimalField = models.SortedListField(field=models.DecimalField(), default=[defaultValueSet1["Decimal"],])
  sortedListFieldEmailField = models.SortedListField(field=models.EmailField(), default=[defaultValueSet1["Email"],])
  sortedListFieldFloatField = models.SortedListField(field=models.FloatField(), default=[defaultValueSet1["Float"],])
  sortedListFieldGeoPointField = models.SortedListField(field=models.GeoPointField(), default=[defaultValueSet1["GeoPoint"],])
  #sortedListFieldFileField = models.SortedListField(field=models.FileField(), default=[defaultValueSet1["File"],])
  #sortedListFieldImageField = models.SortedListField(field=models.ImageField(), default=[defaultValueSet1["Image"],])
  sortedListFieldIntField = models.SortedListField(field=models.IntField(), default=[defaultValueSet1["Int"],])
  sortedListFieldSequenceField = models.SortedListField(field=models.SequenceField(), default=[defaultValueSet1["Sequence"],])
  sortedListFieldStringField = models.SortedListField(field=models.StringField(), default=[defaultValueSet1["String"],])
  sortedListFieldURLField = models.SortedListField(field=models.URLField(), default=[defaultValueSet1["URL"],])
  sortedListFieldUUIDField = models.SortedListField(field=models.UUIDField(), default=[defaultValueSet1["UUID"],])

  #dictFieldBinaryField = models.DictField(field=models.BinaryField(), default={"keyLabel": defaultValueSet1["Binary"],})
  dictFieldBooleanField = models.DictField(field=models.BooleanField(), default={"keyLabel": defaultValueSet1["Boolean"],})
  #dictFieldComplexDateTimeField = models.DictField(field=models.ComplexDateTimeField(), default={"keyLabel": defaultValueSet1["ComplexDateTime"],})
  dictFieldDateTimeField = models.DictField(field=models.DateTimeField(), default={"keyLabel": defaultValueSet1["DateTime"],})
  dictFieldDecimalField = models.DictField(field=models.DecimalField(), default={"keyLabel": defaultValueSet1["Decimal"],})
  dictFieldEmailField = models.DictField(field=models.EmailField(), default={"keyLabel": defaultValueSet1["Email"],})
  dictFieldFloatField = models.DictField(field=models.FloatField(), default={"keyLabel": defaultValueSet1["Float"],})
  dictFieldGeoPointField = models.DictField(field=models.GeoPointField(), default={"keyLabel": defaultValueSet1["GeoPoint"],})
  #dictFieldFileField = models.DictField(field=models.FileField(), default={"keyLabel": defaultValueSet1["File"],})
  #dictFieldImageField = models.DictField(field=models.ImageField(), default={"keyLabel": defaultValueSet1["Image"],})
  dictFieldIntField = models.DictField(field=models.IntField(), default={"keyLabel": defaultValueSet1["Int"],})
  dictFieldSequenceField = models.DictField(field=models.SequenceField(), default={"keyLabel": defaultValueSet1["Sequence"],})
  dictFieldStringField = models.DictField(field=models.StringField(), default={"keyLabel": defaultValueSet1["String"],})
  dictFieldURLField = models.DictField(field=models.URLField(), default={"keyLabel": defaultValueSet1["URL"],})
  dictFieldUUIDField = models.DictField(field=models.UUIDField(), default={"keyLabel": defaultValueSet1["UUID"],})

  mapFieldBinaryField = models.MapField(field=models.BinaryField(), default={"keyLabel": defaultValueSet1["Binary"],})
  mapFieldBooleanField = models.MapField(field=models.BooleanField(), default={"keyLabel": defaultValueSet1["Boolean"],})
  #mapFieldComplexDateTimeField = models.MapField(field=models.ComplexDateTimeField(), default={"keyLabel": defaultValueSet1["ComplexDateTime"],})
  mapFieldDateTimeField = models.MapField(field=models.DateTimeField(), default={"keyLabel": defaultValueSet1["DateTime"],})
  mapFieldDecimalField = models.MapField(field=models.DecimalField(), default={"keyLabel": defaultValueSet1["Decimal"],})
  mapFieldEmailField = models.MapField(field=models.EmailField(), default={"keyLabel": defaultValueSet1["Email"],})
  mapFieldFloatField = models.MapField(field=models.FloatField(), default={"keyLabel": defaultValueSet1["Float"],})
  mapFieldGeoPointField = models.MapField(field=models.GeoPointField(), default={"keyLabel": defaultValueSet1["GeoPoint"],})
  #mapFieldFileField = models.MapField(field=models.FileField(), default={"keyLabel": defaultValueSet1["File"],})
  #mapFieldImageField = models.MapField(field=models.ImageField(), default={"keyLabel": defaultValueSet1["Image"],})
  mapFieldIntField = models.MapField(field=models.IntField(), default={"keyLabel": defaultValueSet1["Int"],})
  mapFieldSequenceField = models.MapField(field=models.SequenceField(), default={"keyLabel": defaultValueSet1["Sequence"],})
  mapFieldStringField = models.MapField(field=models.StringField(), default={"keyLabel": defaultValueSet1["String"],})
  mapFieldURLField = models.MapField(field=models.URLField(), default={"keyLabel": defaultValueSet1["URL"],})
  mapFieldUUIDField = models.MapField(field=models.UUIDField(), default={"keyLabel": defaultValueSet1["UUID"],})

class CombinatoryModelLiteWithDefaultValue(models.Model):
  binaryField = models.BinaryField(default=defaultValueSet1["Binary"])
  fileField = models.FileField(default=defaultValueSet1["File"])
  imageField = models.ImageField(default=defaultValueSet1["Image"])
  booleanField = models.BooleanField(default=defaultValueSet1["Boolean"])
  dateTimeField = models.DateTimeField(default=defaultValueSet1["DateTime"])
  #complexDateTimeField = models.ComplexDateTimeField(default=defaultValueSet1["ComplexDateTime"])
  uUIDField = models.UUIDField(default=defaultValueSet1["UUID"])
  sequenceField = models.SequenceField(default=defaultValueSet1["Sequence"])
  geoPointField = models.GeoPointField(default=defaultValueSet1["GeoPoint"])
  decimalField = models.DecimalField(default=defaultValueSet1["Decimal"])
  floatField = models.FloatField(default=defaultValueSet1["Float"])
  intField = models.IntField(default=defaultValueSet1["Int"])
  stringField = models.StringField(default=defaultValueSet1["String"])
  emailField = models.EmailField(default=defaultValueSet1["Email"])
  uRLField = models.URLField(default=defaultValueSet1["URL"])
  dynamicField = models.DynamicField()

  listFieldBinaryField = models.ListField(field=models.BinaryField(), default=[defaultValueSet1["Binary"],])
  listFieldBooleanField = models.ListField(field=models.BooleanField(), default=[defaultValueSet1["Boolean"],])
  #listFieldComplexDateTimeField = models.ListField(field=models.ComplexDateTimeField(), default=[defaultValueSet1["ComplexDateTime"],])
  listFieldDateTimeField = models.ListField(field=models.DateTimeField(), default=[defaultValueSet1["DateTime"],])
  listFieldDecimalField = models.ListField(field=models.DecimalField(), default=[defaultValueSet1["Decimal"],])
  listFieldEmailField = models.ListField(field=models.EmailField(), default=[defaultValueSet1["Email"],])
  listFieldFloatField = models.ListField(field=models.FloatField(), default=[defaultValueSet1["Float"],])
  listFieldGeoPointField = models.ListField(field=models.GeoPointField(), default=[defaultValueSet1["GeoPoint"],])
  #listFieldFileField = models.ListField(field=models.FileField(), default=[defaultValueSet1["File"],])
  #listFieldImageField = models.ListField(field=models.ImageField(), default=[defaultValueSet1["Image"],])
  listFieldIntField = models.ListField(field=models.IntField(), default=[defaultValueSet1["Int"],])
  listFieldSequenceField = models.ListField(field=models.SequenceField(), default=[defaultValueSet1["Sequence"],])
  listFieldStringField = models.ListField(field=models.StringField(), default=[defaultValueSet1["String"],])
  listFieldURLField = models.ListField(field=models.URLField(), default=[defaultValueSet1["URL"],])
  listFieldUUIDField = models.ListField(field=models.UUIDField(), default=[defaultValueSet1["UUID"],])

  sortedListFieldBinaryField = models.SortedListField(field=models.BinaryField(), default=[defaultValueSet1["Binary"],])
  sortedListFieldBooleanField = models.SortedListField(field=models.BooleanField(), default=[defaultValueSet1["Boolean"],])
  #sortedListFieldComplexDateTimeField = models.SortedListField(field=models.ComplexDateTimeField(), default=[defaultValueSet1["ComplexDateTime"],])
  sortedListFieldDateTimeField = models.SortedListField(field=models.DateTimeField(), default=[defaultValueSet1["DateTime"],])
  sortedListFieldDecimalField = models.SortedListField(field=models.DecimalField(), default=[defaultValueSet1["Decimal"],])
  sortedListFieldEmailField = models.SortedListField(field=models.EmailField(), default=[defaultValueSet1["Email"],])
  sortedListFieldFloatField = models.SortedListField(field=models.FloatField(), default=[defaultValueSet1["Float"],])
  sortedListFieldGeoPointField = models.SortedListField(field=models.GeoPointField(), default=[defaultValueSet1["GeoPoint"],])
  #sortedListFieldFileField = models.SortedListField(field=models.FileField(), default=[defaultValueSet1["File"],])
  #sortedListFieldImageField = models.SortedListField(field=models.ImageField(), default=[defaultValueSet1["Image"],])
  sortedListFieldIntField = models.SortedListField(field=models.IntField(), default=[defaultValueSet1["Int"],])
  sortedListFieldSequenceField = models.SortedListField(field=models.SequenceField(), default=[defaultValueSet1["Sequence"],])
  sortedListFieldStringField = models.SortedListField(field=models.StringField(), default=[defaultValueSet1["String"],])
  sortedListFieldURLField = models.SortedListField(field=models.URLField(), default=[defaultValueSet1["URL"],])
  sortedListFieldUUIDField = models.SortedListField(field=models.UUIDField(), default=[defaultValueSet1["UUID"],])

  #dictFieldBinaryField = models.DictField(field=models.BinaryField(), default={"keyLabel": defaultValueSet1["Binary"],})
  dictFieldBooleanField = models.DictField(field=models.BooleanField(), default={"keyLabel": defaultValueSet1["Boolean"],})
  #dictFieldComplexDateTimeField = models.DictField(field=models.ComplexDateTimeField(), default={"keyLabel": defaultValueSet1["ComplexDateTime"],})
  dictFieldDateTimeField = models.DictField(field=models.DateTimeField(), default={"keyLabel": defaultValueSet1["DateTime"],})
  dictFieldDecimalField = models.DictField(field=models.DecimalField(), default={"keyLabel": defaultValueSet1["Decimal"],})
  dictFieldEmailField = models.DictField(field=models.EmailField(), default={"keyLabel": defaultValueSet1["Email"],})
  dictFieldFloatField = models.DictField(field=models.FloatField(), default={"keyLabel": defaultValueSet1["Float"],})
  dictFieldGeoPointField = models.DictField(field=models.GeoPointField(), default={"keyLabel": defaultValueSet1["GeoPoint"],})
  #dictFieldFileField = models.DictField(field=models.FileField(), default={"keyLabel": defaultValueSet1["File"],})
  #dictFieldImageField = models.DictField(field=models.ImageField(), default={"keyLabel": defaultValueSet1["Image"],})
  dictFieldIntField = models.DictField(field=models.IntField(), default={"keyLabel": defaultValueSet1["Int"],})
  dictFieldSequenceField = models.DictField(field=models.SequenceField(), default={"keyLabel": defaultValueSet1["Sequence"],})
  dictFieldStringField = models.DictField(field=models.StringField(), default={"keyLabel": defaultValueSet1["String"],})
  dictFieldURLField = models.DictField(field=models.URLField(), default={"keyLabel": defaultValueSet1["URL"],})
  dictFieldUUIDField = models.DictField(field=models.UUIDField(), default={"keyLabel": defaultValueSet1["UUID"],})

  mapFieldBinaryField = models.MapField(field=models.BinaryField(), default={"keyLabel": defaultValueSet1["Binary"],})
  mapFieldBooleanField = models.MapField(field=models.BooleanField(), default={"keyLabel": defaultValueSet1["Boolean"],})
  #mapFieldComplexDateTimeField = models.MapField(field=models.ComplexDateTimeField(), default={"keyLabel": defaultValueSet1["ComplexDateTime"],})
  mapFieldDateTimeField = models.MapField(field=models.DateTimeField(), default={"keyLabel": defaultValueSet1["DateTime"],})
  mapFieldDecimalField = models.MapField(field=models.DecimalField(), default={"keyLabel": defaultValueSet1["Decimal"],})
  mapFieldEmailField = models.MapField(field=models.EmailField(), default={"keyLabel": defaultValueSet1["Email"],})
  mapFieldFloatField = models.MapField(field=models.FloatField(), default={"keyLabel": defaultValueSet1["Float"],})
  mapFieldGeoPointField = models.MapField(field=models.GeoPointField(), default={"keyLabel": defaultValueSet1["GeoPoint"],})
  #mapFieldFileField = models.MapField(field=models.FileField(), default={"keyLabel": defaultValueSet1["File"],})
  #mapFieldImageField = models.MapField(field=models.ImageField(), default={"keyLabel": defaultValueSet1["Image"],})
  mapFieldIntField = models.MapField(field=models.IntField(), default={"keyLabel": defaultValueSet1["Int"],})
  mapFieldSequenceField = models.MapField(field=models.SequenceField(), default={"keyLabel": defaultValueSet1["Sequence"],})
  mapFieldStringField = models.MapField(field=models.StringField(), default={"keyLabel": defaultValueSet1["String"],})
  mapFieldURLField = models.MapField(field=models.URLField(), default={"keyLabel": defaultValueSet1["URL"],})
  mapFieldUUIDField = models.MapField(field=models.UUIDField(), default={"keyLabel": defaultValueSet1["UUID"],})

  #meta = {'collection': 'tests_CombinatoryModelWithDefaultValue'}

class CombinatoryEmbeddedModelWithDefaultValue(models.EmbeddedDocument):
  binaryField = models.BinaryField(default=defaultValueSet1["Binary"])
  fileField = models.FileField(default=defaultValueSet1["File"])
  imageField = models.ImageField(default=defaultValueSet1["Image"])
  booleanField = models.BooleanField(default=defaultValueSet1["Boolean"])
  dateTimeField = models.DateTimeField(default=defaultValueSet1["DateTime"])
  #complexDateTimeField = models.ComplexDateTimeField(default=defaultValueSet1["ComplexDateTime"])
  uUIDField = models.UUIDField(default=defaultValueSet1["UUID"])
  sequenceField = models.SequenceField(default=defaultValueSet1["Sequence"])
  geoPointField = models.GeoPointField(default=defaultValueSet1["GeoPoint"])
  decimalField = models.DecimalField(default=defaultValueSet1["Decimal"])
  floatField = models.FloatField(default=defaultValueSet1["Float"])
  intField = models.IntField(default=defaultValueSet1["Int"])
  stringField = models.StringField(default=defaultValueSet1["String"])
  emailField = models.EmailField(default=defaultValueSet1["Email"])
  uRLField = models.URLField(default=defaultValueSet1["URL"])
  dynamicField = models.DynamicField()

  referenceField = models.ReferenceField('CombinatoryModelLiteWithDefaultValue')
  genericReferenceField = models.GenericReferenceField()
  embeddedDocumentField = models.EmbeddedDocumentField('CombinatoryEmbeddedModelLiteWithDefaultValue')
  genericEmbeddedDocumentField = models.GenericEmbeddedDocumentField()

  listFieldBinaryField = models.ListField(field=models.BinaryField(), default=[defaultValueSet1["Binary"],])
  listFieldBooleanField = models.ListField(field=models.BooleanField(), default=[defaultValueSet1["Boolean"],])
  #listFieldComplexDateTimeField = models.ListField(field=models.ComplexDateTimeField(), default=[defaultValueSet1["ComplexDateTime"],])
  listFieldDateTimeField = models.ListField(field=models.DateTimeField(), default=[defaultValueSet1["DateTime"],])
  listFieldDecimalField = models.ListField(field=models.DecimalField(), default=[defaultValueSet1["Decimal"],])
  listFieldEmailField = models.ListField(field=models.EmailField(), default=[defaultValueSet1["Email"],])
  listFieldFloatField = models.ListField(field=models.FloatField(), default=[defaultValueSet1["Float"],])
  listFieldGeoPointField = models.ListField(field=models.GeoPointField(), default=[defaultValueSet1["GeoPoint"],])
  #listFieldFileField = models.ListField(field=models.FileField(), default=[defaultValueSet1["File"],])
  #listFieldImageField = models.ListField(field=models.ImageField(), default=[defaultValueSet1["Image"],])
  listFieldIntField = models.ListField(field=models.IntField(), default=[defaultValueSet1["Int"],])
  listFieldSequenceField = models.ListField(field=models.SequenceField(), default=[defaultValueSet1["Sequence"],])
  listFieldStringField = models.ListField(field=models.StringField(), default=[defaultValueSet1["String"],])
  listFieldURLField = models.ListField(field=models.URLField(), default=[defaultValueSet1["URL"],])
  listFieldUUIDField = models.ListField(field=models.UUIDField(), default=[defaultValueSet1["UUID"],])

  sortedListFieldBinaryField = models.SortedListField(field=models.BinaryField(), default=[defaultValueSet1["Binary"],])
  sortedListFieldBooleanField = models.SortedListField(field=models.BooleanField(), default=[defaultValueSet1["Boolean"],])
  #sortedListFieldComplexDateTimeField = models.SortedListField(field=models.ComplexDateTimeField(), default=[defaultValueSet1["ComplexDateTime"],])
  sortedListFieldDateTimeField = models.SortedListField(field=models.DateTimeField(), default=[defaultValueSet1["DateTime"],])
  sortedListFieldDecimalField = models.SortedListField(field=models.DecimalField(), default=[defaultValueSet1["Decimal"],])
  sortedListFieldEmailField = models.SortedListField(field=models.EmailField(), default=[defaultValueSet1["Email"],])
  sortedListFieldFloatField = models.SortedListField(field=models.FloatField(), default=[defaultValueSet1["Float"],])
  sortedListFieldGeoPointField = models.SortedListField(field=models.GeoPointField(), default=[defaultValueSet1["GeoPoint"],])
  #sortedListFieldFileField = models.SortedListField(field=models.FileField(), default=[defaultValueSet1["File"],])
  #sortedListFieldImageField = models.SortedListField(field=models.ImageField(), default=[defaultValueSet1["Image"],])
  sortedListFieldIntField = models.SortedListField(field=models.IntField(), default=[defaultValueSet1["Int"],])
  sortedListFieldSequenceField = models.SortedListField(field=models.SequenceField(), default=[defaultValueSet1["Sequence"],])
  sortedListFieldStringField = models.SortedListField(field=models.StringField(), default=[defaultValueSet1["String"],])
  sortedListFieldURLField = models.SortedListField(field=models.URLField(), default=[defaultValueSet1["URL"],])
  sortedListFieldUUIDField = models.SortedListField(field=models.UUIDField(), default=[defaultValueSet1["UUID"],])

  #dictFieldBinaryField = models.DictField(field=models.BinaryField(), default={"keyLabel": defaultValueSet1["Binary"],})
  dictFieldBooleanField = models.DictField(field=models.BooleanField(), default={"keyLabel": defaultValueSet1["Boolean"],})
  #dictFieldComplexDateTimeField = models.DictField(field=models.ComplexDateTimeField(), default={"keyLabel": defaultValueSet1["ComplexDateTime"],})
  dictFieldDateTimeField = models.DictField(field=models.DateTimeField(), default={"keyLabel": defaultValueSet1["DateTime"],})
  dictFieldDecimalField = models.DictField(field=models.DecimalField(), default={"keyLabel": defaultValueSet1["Decimal"],})
  dictFieldEmailField = models.DictField(field=models.EmailField(), default={"keyLabel": defaultValueSet1["Email"],})
  dictFieldFloatField = models.DictField(field=models.FloatField(), default={"keyLabel": defaultValueSet1["Float"],})
  dictFieldGeoPointField = models.DictField(field=models.GeoPointField(), default={"keyLabel": defaultValueSet1["GeoPoint"],})
  #dictFieldFileField = models.DictField(field=models.FileField(), default={"keyLabel": defaultValueSet1["File"],})
  #dictFieldImageField = models.DictField(field=models.ImageField(), default={"keyLabel": defaultValueSet1["Image"],})
  dictFieldIntField = models.DictField(field=models.IntField(), default={"keyLabel": defaultValueSet1["Int"],})
  dictFieldSequenceField = models.DictField(field=models.SequenceField(), default={"keyLabel": defaultValueSet1["Sequence"],})
  dictFieldStringField = models.DictField(field=models.StringField(), default={"keyLabel": defaultValueSet1["String"],})
  dictFieldURLField = models.DictField(field=models.URLField(), default={"keyLabel": defaultValueSet1["URL"],})
  dictFieldUUIDField = models.DictField(field=models.UUIDField(), default={"keyLabel": defaultValueSet1["UUID"],})

  mapFieldBinaryField = models.MapField(field=models.BinaryField(), default={"keyLabel": defaultValueSet1["Binary"],})
  mapFieldBooleanField = models.MapField(field=models.BooleanField(), default={"keyLabel": defaultValueSet1["Boolean"],})
  #mapFieldComplexDateTimeField = models.MapField(field=models.ComplexDateTimeField(), default={"keyLabel": defaultValueSet1["ComplexDateTime"],})
  mapFieldDateTimeField = models.MapField(field=models.DateTimeField(), default={"keyLabel": defaultValueSet1["DateTime"],})
  mapFieldDecimalField = models.MapField(field=models.DecimalField(), default={"keyLabel": defaultValueSet1["Decimal"],})
  mapFieldEmailField = models.MapField(field=models.EmailField(), default={"keyLabel": defaultValueSet1["Email"],})
  mapFieldFloatField = models.MapField(field=models.FloatField(), default={"keyLabel": defaultValueSet1["Float"],})
  mapFieldGeoPointField = models.MapField(field=models.GeoPointField(), default={"keyLabel": defaultValueSet1["GeoPoint"],})
  #mapFieldFileField = models.MapField(field=models.FileField(), default={"keyLabel": defaultValueSet1["File"],})
  #mapFieldImageField = models.MapField(field=models.ImageField(), default={"keyLabel": defaultValueSet1["Image"],})
  mapFieldIntField = models.MapField(field=models.IntField(), default={"keyLabel": defaultValueSet1["Int"],})
  mapFieldSequenceField = models.MapField(field=models.SequenceField(), default={"keyLabel": defaultValueSet1["Sequence"],})
  mapFieldStringField = models.MapField(field=models.StringField(), default={"keyLabel": defaultValueSet1["String"],})
  mapFieldURLField = models.MapField(field=models.URLField(), default={"keyLabel": defaultValueSet1["URL"],})
  mapFieldUUIDField = models.MapField(field=models.UUIDField(), default={"keyLabel": defaultValueSet1["UUID"],})

class CombinatoryModelWithDefaultValue(models.Model):
  binaryField = models.BinaryField(default=defaultValueSet1["Binary"])
  fileField = models.FileField(default=defaultValueSet1["File"])
  imageField = models.ImageField(default=defaultValueSet1["Image"])
  booleanField = models.BooleanField(default=defaultValueSet1["Boolean"])
  dateTimeField = models.DateTimeField(default=defaultValueSet1["DateTime"])
  #complexDateTimeField = models.ComplexDateTimeField(default=defaultValueSet1["ComplexDateTime"])
  uUIDField = models.UUIDField(default=defaultValueSet1["UUID"])
  sequenceField = models.SequenceField(default=defaultValueSet1["Sequence"])
  geoPointField = models.GeoPointField(default=defaultValueSet1["GeoPoint"])
  decimalField = models.DecimalField(default=defaultValueSet1["Decimal"])
  floatField = models.FloatField(default=defaultValueSet1["Float"])
  intField = models.IntField(default=defaultValueSet1["Int"])
  stringField = models.StringField(default=defaultValueSet1["String"])
  emailField = models.EmailField(default=defaultValueSet1["Email"])
  uRLField = models.URLField(default=defaultValueSet1["URL"])
  dynamicField = models.DynamicField()

  referenceField = models.ReferenceField('CombinatoryModelLiteWithDefaultValue')
  genericReferenceField = models.GenericReferenceField()
  embeddedDocumentField = models.EmbeddedDocumentField('CombinatoryEmbeddedModelWithDefaultValue', default=CombinatoryEmbeddedModelWithDefaultValue())
  genericEmbeddedDocumentField = models.GenericEmbeddedDocumentField(default=CombinatoryEmbeddedModelWithDefaultValue())

  listFieldBinaryField = models.ListField(field=models.BinaryField(), default=[defaultValueSet1["Binary"],])
  listFieldBooleanField = models.ListField(field=models.BooleanField(), default=[defaultValueSet1["Boolean"],])
  #listFieldComplexDateTimeField = models.ListField(field=models.ComplexDateTimeField(), default=[defaultValueSet1["ComplexDateTime"],])
  listFieldDateTimeField = models.ListField(field=models.DateTimeField(), default=[defaultValueSet1["DateTime"],])
  listFieldDecimalField = models.ListField(field=models.DecimalField(), default=[defaultValueSet1["Decimal"],])
  listFieldEmailField = models.ListField(field=models.EmailField(), default=[defaultValueSet1["Email"],])
  listFieldFloatField = models.ListField(field=models.FloatField(), default=[defaultValueSet1["Float"],])
  listFieldGeoPointField = models.ListField(field=models.GeoPointField(), default=[defaultValueSet1["GeoPoint"],])
  #listFieldFileField = models.ListField(field=models.FileField(), default=[defaultValueSet1["File"],])
  #listFieldImageField = models.ListField(field=models.ImageField(), default=[defaultValueSet1["Image"],])
  listFieldIntField = models.ListField(field=models.IntField(), default=[defaultValueSet1["Int"],])
  listFieldSequenceField = models.ListField(field=models.SequenceField(), default=[defaultValueSet1["Sequence"],])
  listFieldStringField = models.ListField(field=models.StringField(), default=[defaultValueSet1["String"],])
  listFieldURLField = models.ListField(field=models.URLField(), default=[defaultValueSet1["URL"],])
  listFieldUUIDField = models.ListField(field=models.UUIDField(), default=[defaultValueSet1["UUID"],])
  listFieldEmbeddedField = models.ListField(field=models.EmbeddedDocumentField("CombinatoryEmbeddedModelWithDefaultValue"), default=[CombinatoryEmbeddedModelWithDefaultValue(),])

  sortedListFieldBinaryField = models.SortedListField(field=models.BinaryField(), default=[defaultValueSet1["Binary"],])
  sortedListFieldBooleanField = models.SortedListField(field=models.BooleanField(), default=[defaultValueSet1["Boolean"],])
  #sortedListFieldComplexDateTimeField = models.SortedListField(field=models.ComplexDateTimeField(), default=[defaultValueSet1["ComplexDateTime"],])
  sortedListFieldDateTimeField = models.SortedListField(field=models.DateTimeField(), default=[defaultValueSet1["DateTime"],])
  sortedListFieldDecimalField = models.SortedListField(field=models.DecimalField(), default=[defaultValueSet1["Decimal"],])
  sortedListFieldEmailField = models.SortedListField(field=models.EmailField(), default=[defaultValueSet1["Email"],])
  sortedListFieldFloatField = models.SortedListField(field=models.FloatField(), default=[defaultValueSet1["Float"],])
  sortedListFieldGeoPointField = models.SortedListField(field=models.GeoPointField(), default=[defaultValueSet1["GeoPoint"],])
  #sortedListFieldFileField = models.SortedListField(field=models.FileField(), default=[defaultValueSet1["File"],])
  #sortedListFieldImageField = models.SortedListField(field=models.ImageField(), default=[defaultValueSet1["Image"],])
  sortedListFieldIntField = models.SortedListField(field=models.IntField(), default=[defaultValueSet1["Int"],])
  sortedListFieldSequenceField = models.SortedListField(field=models.SequenceField(), default=[defaultValueSet1["Sequence"],])
  sortedListFieldStringField = models.SortedListField(field=models.StringField(), default=[defaultValueSet1["String"],])
  sortedListFieldURLField = models.SortedListField(field=models.URLField(), default=[defaultValueSet1["URL"],])
  sortedListFieldUUIDField = models.SortedListField(field=models.UUIDField(), default=[defaultValueSet1["UUID"],])
  sortedListFieldEmbeddedField = models.SortedListField(field=models.EmbeddedDocumentField("CombinatoryEmbeddedModelWithDefaultValue"), default=[CombinatoryEmbeddedModelWithDefaultValue(),])

  #dictFieldBinaryField = models.DictField(field=models.BinaryField(), default={"keyLabel": defaultValueSet1["Binary"],})
  dictFieldBooleanField = models.DictField(field=models.BooleanField(), default={"keyLabel": defaultValueSet1["Boolean"],})
  #dictFieldComplexDateTimeField = models.DictField(field=models.ComplexDateTimeField(), default={"keyLabel": defaultValueSet1["ComplexDateTime"],})
  dictFieldDateTimeField = models.DictField(field=models.DateTimeField(), default={"keyLabel": defaultValueSet1["DateTime"],})
  dictFieldDecimalField = models.DictField(field=models.DecimalField(), default={"keyLabel": defaultValueSet1["Decimal"],})
  dictFieldEmailField = models.DictField(field=models.EmailField(), default={"keyLabel": defaultValueSet1["Email"],})
  dictFieldFloatField = models.DictField(field=models.FloatField(), default={"keyLabel": defaultValueSet1["Float"],})
  dictFieldGeoPointField = models.DictField(field=models.GeoPointField(), default={"keyLabel": defaultValueSet1["GeoPoint"],})
  #dictFieldFileField = models.DictField(field=models.FileField(), default={"keyLabel": defaultValueSet1["File"],})
  #dictFieldImageField = models.DictField(field=models.ImageField(), default={"keyLabel": defaultValueSet1["Image"],})
  dictFieldIntField = models.DictField(field=models.IntField(), default={"keyLabel": defaultValueSet1["Int"],})
  dictFieldSequenceField = models.DictField(field=models.SequenceField(), default={"keyLabel": defaultValueSet1["Sequence"],})
  dictFieldStringField = models.DictField(field=models.StringField(), default={"keyLabel": defaultValueSet1["String"],})
  dictFieldURLField = models.DictField(field=models.URLField(), default={"keyLabel": defaultValueSet1["URL"],})
  dictFieldUUIDField = models.DictField(field=models.UUIDField(), default={"keyLabel": defaultValueSet1["UUID"],})
  dictFieldEmbeddedField = models.DictField(field=models.EmbeddedDocumentField("CombinatoryEmbeddedModelWithDefaultValue"), default={"keyLabel": CombinatoryEmbeddedModelWithDefaultValue(),})

  mapFieldBinaryField = models.MapField(field=models.BinaryField(), default={"keyLabel": defaultValueSet1["Binary"],})
  mapFieldBooleanField = models.MapField(field=models.BooleanField(), default={"keyLabel": defaultValueSet1["Boolean"],})
  #mapFieldComplexDateTimeField = models.MapField(field=models.ComplexDateTimeField(), default={"keyLabel": defaultValueSet1["ComplexDateTime"],})
  mapFieldDateTimeField = models.MapField(field=models.DateTimeField(), default={"keyLabel": defaultValueSet1["DateTime"],})
  mapFieldDecimalField = models.MapField(field=models.DecimalField(), default={"keyLabel": defaultValueSet1["Decimal"],})
  mapFieldEmailField = models.MapField(field=models.EmailField(), default={"keyLabel": defaultValueSet1["Email"],})
  mapFieldFloatField = models.MapField(field=models.FloatField(), default={"keyLabel": defaultValueSet1["Float"],})
  mapFieldGeoPointField = models.MapField(field=models.GeoPointField(), default={"keyLabel": defaultValueSet1["GeoPoint"],})
  #mapFieldFileField = models.MapField(field=models.FileField(), default={"keyLabel": defaultValueSet1["File"],})
  #mapFieldImageField = models.MapField(field=models.ImageField(), default={"keyLabel": defaultValueSet1["Image"],})
  mapFieldIntField = models.MapField(field=models.IntField(), default={"keyLabel": defaultValueSet1["Int"],})
  mapFieldSequenceField = models.MapField(field=models.SequenceField(), default={"keyLabel": defaultValueSet1["Sequence"],})
  mapFieldStringField = models.MapField(field=models.StringField(), default={"keyLabel": defaultValueSet1["String"],})
  mapFieldURLField = models.MapField(field=models.URLField(), default={"keyLabel": defaultValueSet1["URL"],})
  mapFieldUUIDField = models.MapField(field=models.UUIDField(), default={"keyLabel": defaultValueSet1["UUID"],})
  mapFieldEmbeddedField = models.MapField(field=models.EmbeddedDocumentField("CombinatoryEmbeddedModelWithDefaultValue"), default={"keyLabel": CombinatoryEmbeddedModelWithDefaultValue(),})

  #meta = {'collection': 'tests_CombinatoryModelWithDefaultValue'}

