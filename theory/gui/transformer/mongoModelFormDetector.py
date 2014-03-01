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

  def choiceFieldHandler(self):
    # There is no choiceField in mongoengine, it is just intField with choices.
    # And we are just mocking this field.
    return field.ChoiceField

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

  def _getHandlerByFieldName(self, fieldTypeStr, fieldKwargs):
    handlerFxnTmpl = "{0}Handler"
    fieldTypeStr = fieldTypeStr[0].lower() + fieldTypeStr[1:]
    if(fieldTypeStr=="intField" and "choices" in fieldKwargs):
      fieldTypeStr = "choiceField"
    return getattr(self, handlerFxnTmpl.format(fieldTypeStr))()

  def _getChildParam(self, fieldParamLst, circularLvl, isRoot=False):
    """To get all args and kwargs ready recursively for a field to be initalize.
    """
    args = []
    kwargs = {}
    for fieldParam in fieldParamLst:
      if(fieldParam.isCircular):
        # Should be some other fields
        fieldParam.name="ReferenceField"
      if(fieldParam.isField):
        if(fieldParam.name=="ReferenceField"
            or fieldParam.name=="EmbeddedDocumentField"
            ):
          childArgs = [
              fieldParam.childParamLst[0].data,
              fieldParam.childParamLst[1].data,
              ]
          childKwargs = {}
        else:
          childArgs, childKwargs = self._getChildParam(
              fieldParam.childParamLst,
              circularLvl
              )
        childKwargs = self._convertKwargsName(childKwargs)
        childField = self._getHandlerByFieldName(fieldParam.name, childKwargs)
        if(isRoot):
          # We wanna initialize the childField in gui/model.py, so we have to
          # keep all parameters in the top level. For others level, we want to
          # initialize all of them
          args.extend(childArgs)
          kwargs = childKwargs
        else:
          args.append(childField(*childArgs, **childKwargs))
      else:
        kwargs[fieldParam.name] = fieldParam.data
    return (args, kwargs)

  def _convertKwargsName(self, kwargs):
    """To convert the mongoengine field keyword to theory field keyword"""
    newNameDict= {
        "verbose_name": "label",
        "help_text": "help_text",
        "choices": "choices",
        "default": "initData",
        "required": "required",
        "max_length": "max_length",
        "min_length": "min_length",
      }
    newDict = {}
    for k, v in kwargs.iteritems():
      if(k in newNameDict):
        newDict[newNameDict[k]] = v
    return newDict

  def run(self, modelImportPath="", appModelObj=None):
    if(modelImportPath=="" and appModelObj is None):
      raise
    fieldLst = []
    if(appModelObj is None):
      appModelObj = AppModel.objects\
          .only("app", "formField", "fieldParamMap")\
          .get(importPath=modelImportPath)
    for fieldName in appModelObj.formField:
      fieldParam = appModelObj.fieldParamMap[fieldName]
      args, kwargs = self._getChildParam([fieldParam], 0, True)
      fieldLst.append((
        fieldName,
        (self._getHandlerByFieldName(fieldParam.data, kwargs), args, kwargs)
        ))
    return SortedDict(fieldLst)
