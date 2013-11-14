# -*- coding: utf-8 -*-
#!/usr/bin/env python
##### System wide lib #####
import inspect
from collections import OrderedDict
from copy import deepcopy
from mongoengine import fields as MongoEngineField
from mongoengine.base import ObjectIdField as MongoEngineObjectId

##### Theory lib #####
from theory.model import Model
from theory.db.models import EmbeddedDocument as TheoryEmbeddedModel
from theory.conf import settings
from theory.model import Command, Parameter

##### Theory third-party lib #####

##### Local app #####
from .baseClassScanner import BaseClassScanner

##### Theory app #####

##### Misc #####

class ModelClassScanner(BaseClassScanner):
  _modelLst = []
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

  def _matchFieldType(self, modelFieldTypeDict):
    mongoTypeDict = self._getMongoTypeDict()
    r = {}
    for fieldName, fieldType in modelFieldTypeDict.iteritems():
      label = self._getKlassLabel(fieldType, mongoTypeDict)
      if(not label is None):
        r[fieldName] = label
    return r

  def _getKlassLabel(self, fieldType, mongoTypeDict, prefix=""):
    for typeName, typeKlass in mongoTypeDict.iteritems():
      if(isinstance(fieldType, typeKlass)):
        if(typeName in [
            "ListField",
            "SortedListField",
            "MapField",
            #"ReferenceField"
          ]):
          return self._getKlassLabel(
              fieldType.field,
              mongoTypeDict,
              typeName
              )
        elif(prefix!=""):
          return "{0}.{1}".format(prefix, typeName)
        else:
          return typeName
    return None

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
      model.importPath =".".join(token)
    elif(len(token)==1):
      model.importPath += ".model." + modelClassName

    model.app = token[0]
    model.name = modelClassName
    model.fieldNameTypeMap = self._matchFieldType(modelClass._fields)
    model.tblField = model.formField = modelClass._fields.keys()
    return model

  def scan(self):
    modelClassLst = self._loadModelClass(self.modelTemplate.importPath)
    for modelClassName, modelClass in modelClassLst:
      if(modelClassName=="Model"
          or modelClassName=="EmbeddedDocument"
          or modelClassName=="DynamicEmbeddedDocument"):
        continue
      model = self._probeModelField(modelClassName, modelClass)
      if(model is not None):
        self._modelLst.append(model)
