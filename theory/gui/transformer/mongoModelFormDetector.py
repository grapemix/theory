# -*- coding: utf-8 -*-
#!/usr/bin/env python
##### System wide lib #####

##### Theory lib #####
from theory.gui import field
from theory.model import AppModel
from theory.utils.datastructures import SortedDict

##### Theory third-party lib #####

##### Local app #####

##### Theory app #####

##### Misc #####

__all__ = ("MongoModelFormDetector",)

class MongoModelFormDetector(object):
  """This class detect the data type from MongoDB fields specific for form,
  but it does not handle any data type."""

  def binaryFieldHandler(self):
    return field.BinaryField

  def dynamicFieldHandler(self):
    return field.BinaryField

  def fileFieldHandler(self):
    return field.FileField

  def imageFieldHandler(self):
    return field.ImageField

  def complexDateTimeFieldHandler(self):
    return field.DateTimeField

  def dateTimeFieldHandler(self):
    return field.DateTimeField

  def uUIDFieldHandler(self):
    return field.BinaryField

  def objectIdFieldHandler(self):
    return field.ObjectIdField

  def sequenceFieldHandler(self):
    return field.IntegerField

  def dictFieldHandler(self):
    return field.DictField

  def emailFieldHandler(self):
    return field.EmailField

  def uRLFieldHandler(self):
    return field.URLField

  def geoPointFieldHandler(self):
    return field.GeoPointField

  def booleanFieldHandler(self):
    return field.BooleanField

  def decimalFieldHandler(self):
    return field.DecimalField

  def floatFieldHandler(self):
    return field.FloatField

  def enumFieldHandler(self):
    return field.ChoiceField

  def intFieldHandler(self):
    return field.IntegerField

  def stringFieldHandler(self):
    return field.TextField

  def mapFieldHandler(self):
    return field.DictField

  def referenceFieldHandler(self):
    return field.ModelField

  def genericReferenceFieldHandler(self):
    #return field.ModelField
    return field.BinaryField

  def embeddedDocumentFieldHandler(self):
    return field.EmbeddedField

  def genericEmbeddedDocumentFieldHandler(self):
    #return field.EmbeddedField
    return field.BinaryField

  def listFieldHandler(self):
    return field.ListField

  def sortedListFieldHandler(self):
    return field.ListField

  def _getHandlerByFieldName(self, fieldTypeStr):
    handlerFxnTmpl = "{0}Handler"
    fieldTypeStr = fieldTypeStr[0].lower() + fieldTypeStr[1:]
    return getattr(self, handlerFxnTmpl.format(fieldTypeStr))()

  def run(self, modelImportPath="", appModelObj=None):
    if(modelImportPath=="" and appModelObj is None):
      raise
    fieldLst = []
    if(appModelObj is None):
      appModelObj = AppModel.objects\
          .only("app", "formField", "fieldNameTypeMap")\
          .get(importPath=modelImportPath)
    for fieldName in appModelObj.formField:
      fieldTypeStr = appModelObj.fieldNameTypeMap[fieldName]
      args = []
      if(fieldTypeStr.startswith("ListField")):
        (fieldTypeStr, childFieldTypeStr) = fieldTypeStr.split(".")
        args = [self._getHandlerByFieldName(childFieldTypeStr.split("_")[0])]

        if(
            childFieldTypeStr.startswith("Embedded") \
                or childFieldTypeStr.startswith("ReferenceField")
          ):
          args[0] = args[0](appModelObj.app, childFieldTypeStr.split("_")[1])
        else:
          args[0] = args[0]()

      elif(fieldTypeStr.startswith("MapField") \
          or fieldTypeStr.startswith("DictField")):
        (fieldTypeStr, valueFieldTypeStr) = fieldTypeStr.split(".")
        args = [
            self._getHandlerByFieldName("StringField")(),
            self._getHandlerByFieldName(valueFieldTypeStr.split("_")[0])
            ]

        if(valueFieldTypeStr.startswith("Embedded")):
          args[1] = args[1](appModelObj.app, valueFieldTypeStr.split("_")[1])
        else:
          args[1] = args[1]()
      elif(fieldTypeStr.startswith("EmbeddedDocumentField")
          or fieldTypeStr.startswith("ReferenceField")
          ):
        (fieldTypeStr, childFieldTypeStr) = fieldTypeStr.split("_")
        args = [appModelObj.app, childFieldTypeStr,]
      fieldType = self._getHandlerByFieldName(fieldTypeStr)
      fieldLst.append((fieldName, (fieldType, args)))
    return SortedDict(fieldLst)
