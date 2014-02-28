# -*- coding: utf-8 -*-
#!/usr/bin/env python
##### System wide lib #####
import datetime
import inspect
from collections import OrderedDict
from copy import deepcopy
from mongoengine import fields as MongoEngineField
from mongoengine.base import ObjectIdField as MongoEngineObjectId

##### Theory lib #####
from theory.model import Model
from theory.db.models import EmbeddedDocument as TheoryEmbeddedModel
from theory.conf import settings
from theory.model import Command, Parameter, FieldParameter
from theory.utils.functional import Promise

##### Theory third-party lib #####

##### Local app #####
from .baseClassScanner import BaseClassScanner

##### Theory app #####

##### Misc #####

class ModelClassScanner(BaseClassScanner):
  """This class is mongoengine specific"""
  _modelLst = []

  fieldKwargsLst = ("default", "verbose_name", "help_text", "choices",
      "unique_with", "unique", "required", "max_length", "min_length",
      "field",
      )

  @property
  def modelList(self):
    return self._modelLst

  @property
  def modelTemplate(self):
    return self._modelTemplate

  @modelTemplate.setter
  def modelTemplate(self, modelTemplate):
    self._modelTemplate = modelTemplate

  def _loadModelClass(self, importPath):
    packageName = ".".join(importPath.split(".")[:-1])
    submoduleName = importPath.split(".")[-1]
    module = self._loadSubModuleCommandClass(
        packageName,
        "model",
        submoduleName
        )

    classLst = []
    if(module!=None):
      for _property in dir(module):
        property = getattr(module, _property)

        if(inspect.isclass(property) and
            (issubclass(property, Model)
              or issubclass(property, TheoryEmbeddedModel))):
          if(hasattr(property, "ABCMeta")):
            continue
          else:
            # Only load the property iff property is a class name and the
            # class is not abstract
            classLst.append((_property, property))
    return classLst

  def _getMongoTypeDict(self):
    fieldnameLst = [
        "BinaryField", "FileField", "ImageField", "BooleanField",
        "DateTimeField","ComplexDateTimeField", "UUIDField", "SequenceField",
        "GeoPointField", "DecimalField", "FloatField", "IntField",
        "EmailField", "URLField", "DynamicField", "ReferenceField",
        "GenericReferenceField", "EmbeddedDocumentField",
        "GenericEmbeddedDocumentField", "ListField", "SortedListField",
        "MapField", "DictField", "StringField", "ObjectIdField",
    ]

    # The reason we needed OrderedDict in here instead of Dict is because
    # some fields like ComplexDateTimeField will return true for
    # isinstance(StringField) and hence we have to test those fields which
    # can be automatically casted as StringField first.
    r = OrderedDict()
    for fieldname in fieldnameLst:
      try:
        r[fieldname] = getattr(MongoEngineField, fieldname)
      except AttributeError:
        # for backword mongoengine compatability
        pass
    return r

  def _createFieldParamMap(self, modelFieldTypeDict):
    mongoTypeDict = self._getMongoTypeDict()
    r = {}
    for fieldName, fieldType in modelFieldTypeDict.iteritems():
      fieldParam = self._createFieldParam(fieldType, mongoTypeDict)
      if(fieldParam is not None):
        fieldParam.name = fieldParam.data = fieldType.__class__.__name__
        fieldParam.isField = True
        r[fieldName] = fieldParam
    return r

  def _createFieldParam(self, fieldType, mongoTypeDict):
    for typeName, typeKlass in mongoTypeDict.iteritems():
      if(isinstance(fieldType, typeKlass)
          or (inspect.isclass(fieldType) and issubclass(fieldType, typeKlass))
          ):

        fieldParam = FieldParameter(
              name=typeName,
              data=None,
              isField=True,
            )
        if(typeName in [
            "ListField",
            "SortedListField",
          ]):
          fieldParam.childParamLst.append(
              self._createFieldParam(
                fieldType.field,
                mongoTypeDict,
                )
              )
        elif(typeName in [
            "MapField",
            "DictField",
          ]):
          fieldParam.childParamLst.append(
                FieldParameter(name="StringField", isField=True)
            )
          fieldParam.childParamLst.append(
              self._createFieldParam(
                fieldType.field,
                mongoTypeDict,
                )
              )
        elif(typeName=="EmbeddedDocumentField"
            or typeName=="ReferenceField"
            ):
          fieldParam.isField = True
          fieldParam.data = typeName
          try:
            modelNameToken = fieldType.document_type\
                ._get_collection_name().split("_")
            # This is app name
            fieldParam.childParamLst.append(
                  FieldParameter(data=modelNameToken[0])
              )
            childFieldName = ""
            for i in range(1, len(modelNameToken)):
              childFieldName += modelNameToken[i].title()
            # This is model name
            fieldParam.childParamLst.append(FieldParameter(data=childFieldName))
          except AttributeError:
            # This is for Embedded model
            fieldParam.childParamLst.append(
              FieldParameter(data=self.modelAppName)
              )
            childFieldName = fieldType.document_type._types[0]
            childFieldName = childFieldName[0].upper() + childFieldName[1:]
            fieldParam.childParamLst.append(FieldParameter(data=childFieldName))

          # Declare dependency to check circular dependency later
          self.modelDepMap[self.modelAppClassName].append(fieldParam)

        # After getting all args, now fill up field's kwargs
        fieldParam.childParamLst.extend(
            self._getFieldParamKwargs(fieldType, typeName)
            )
        return fieldParam

  def _getFieldParamKwargs(self, fieldType, typeName):
    r = []

    for attrName in dir(fieldType):
      if(attrName not in self.fieldKwargsLst):
        continue
      if(attrName=="choices" and getattr(fieldType, attrName) is None):
        # In IntField, if choices are not provided, the default is None and we
        # do not want to store them
        continue
      if(callable(getattr(fieldType, attrName))):
        # We do not store any function
        continue
      if(attrName=="default" and typeName in ["FileField", "ImageField"]):
        # Data is stored as JSON, we cannot allow any binary data
        continue
      data = getattr(fieldType, attrName)
      isField = False

      if(isinstance(data, datetime.datetime)
          or isinstance(data, datetime.date)):
        if(data-datetime.datetime.utcnow()<datetime.timedelta(minutes=2)):
          data = "utcNow"
        else:
          data.isoformat()
      elif(isinstance(data, Promise)):
        # that's for lazy translation(_)
        data = unicode(data)
      elif(isinstance(data, MongoEngineField.BaseField)):
        if(attrName=="field"):
          continue
        # Get the Mongoengine Field class name
        data = data.__class__.__name__
        attrName = data
        isField = True

      f = FieldParameter(
            name=attrName,
            data=data,
            isField=isField
          )
      r.append(f)
    return r

  def _probeModelField(self, modelClassName, modelClass):
    # Should add debug flag checking and dump to log file instead
    model = deepcopy(self.modelTemplate)
    if(model.importPath.endswith("__init__")):
      # if the class locates at __init__.py, __init__ shoule not be included
      # in the import path
      model.importPath = model.importPath[:-9]
    elif(not model.importPath.endswith(modelClassName[0].lower()
        + modelClassName[1:])):
      # Except for __init__ or singular model.py, all other files can
      # only contain a class which match its filename.
      # E.x: sampleClass.py shoule be only import SampleClass.
      # During class probing in a file using meta-programming technique,
      # the import class will also be regarded as a class in the file.
      # To avoid complicated mechanism to match classes and filesnames,
      # one file contained one class applied.
      return None

    token = model.importPath.split(".")

    if(len(token)>1):
      token.insert(-1, "model")
      token.append(modelClassName)
      model.importPath = ".".join(token)
    elif(len(token)==1):
      model.importPath += ".model." + modelClassName

    self.modelAppClassName = "{0}|{1}".format(token[0], modelClassName)
    model.app = token[0]
    self.modelAppName = model.app
    model.name = modelClassName
    model.fieldParamMap = self._createFieldParamMap(modelClass._fields)
    model.tblField = model.formField = modelClass._fields.keys()
    model.isEmbedded = issubclass(modelClass, TheoryEmbeddedModel)
    return model

  def scan(self):
    modelClassLst = self._loadModelClass(self.modelTemplate.importPath)
    self.modelAppClassName = None
    for modelClassName, modelClass in modelClassLst:
      if(modelClassName=="Model"
          or modelClassName=="EmbeddedDocument"
          or modelClassName=="DynamicEmbeddedDocument"
          ):
        continue
      model = self._probeModelField(modelClassName, modelClass)
      if(model is not None):
        self._modelLst.append(model)

