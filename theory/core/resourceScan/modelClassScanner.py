# -*- coding: utf-8 -*-
#!/usr/bin/env python
##### System wide lib #####
import datetime
import inspect
from collections import OrderedDict
from copy import deepcopy
import json

##### Theory lib #####
from theory.db import model
from theory.conf import settings
from theory.contrib.postgres.fields import ArrayField
from theory.apps.model import Command, FieldParameter
from theory.utils.functional import Promise

##### Theory third-party lib #####

##### Local app #####
from .baseClassScanner import BaseClassScanner

##### Theory app #####

##### Misc #####

class ModelClassScanner(BaseClassScanner):
  """This class is theory orm specific"""

  fieldKwargsLst = ("default", "verboseName", "helpText", "choices",
      "uniqueWith", "unique", "required", "maxLength", "minLength",
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
    if(module is not None):
      for _property in dir(module):
        property = getattr(module, _property)

        if (
            inspect.isclass(property)
            and issubclass(property, model.Model)
            # make sure Model won't be include
            and hasattr(property, "_meta")
            ):
            #(issubclass(property, Model)
            #  or issubclass(property, TheoryEmbeddedModel))):
          if(hasattr(property, "ABCMeta")):
            continue
          else:
            # Only load the property iff property is a class name and the
            # class is not abstract
            classLst.append((_property, property))
    return classLst

  def _getTheoryTypeDict(self):
    fieldnameLst = [
        'AutoField', 'BinaryField', 'NullBooleanField', 'BooleanField',
        'PositiveIntegerField', 'PositiveSmallIntegerField', 'BigIntegerField',
        'SmallIntegerField', 'DecimalField', 'FloatField', 'IntegerField',
        'TimeField', 'DateField', 'DateTimeField',
        'CommaSeparatedIntegerField', 'EmailField', 'FilePathField',
        'GenericIPAddressField', 'IPAddressField', 'SlugField', 'URLField',
        'CharField', 'TextField',
        'OneToOneField', 'ManyToManyField', 'ForeignKey', 'ArrayField'
    ]

    # The reason we needed OrderedDict in here instead of Dict is because
    # some fields like ComplexDateTimeField will return true for
    # isinstance(StringField) and hence we have to test those fields which
    # can be automatically casted as StringField first.
    r = OrderedDict()
    for fieldname in fieldnameLst:
      if fieldname == "ArrayField":
        r[fieldname] = ArrayField
      else:
        r[fieldname] = getattr(model, fieldname)
    return r

  #def _getMongoTypeDict(self):
  #  fieldnameLst = [
  #      "BinaryField", "FileField", "ImageField", "BooleanField",
  #      "DateTimeField","ComplexDateTimeField", "UUIDField", "SequenceField",
  #      "GeoPointField", "DecimalField", "FloatField", "IntField",
  #      "EmailField", "URLField", "DynamicField", "ReferenceField",
  #      "GenericReferenceField", "EmbeddedDocumentField",
  #      "GenericEmbeddedDocumentField", "ListField", "SortedListField",
  #      "MapField", "DictField", "StringField", "ObjectIdField",
  #  ]

  #  # The reason we needed OrderedDict in here instead of Dict is because
  #  # some fields like ComplexDateTimeField will return true for
  #  # isinstance(StringField) and hence we have to test those fields which
  #  # can be automatically casted as StringField first.
  #  r = OrderedDict()
  #  for fieldname in fieldnameLst:
  #    try:
  #      r[fieldname] = getattr(MongoEngineField, fieldname)
  #    except AttributeError:
  #      # for backword mongoengine compatability
  #      pass
  #  return r

  #def _createFieldParamMap(self, modelFieldTypeDict):
  #  mongoTypeDict = self._getMongoTypeDict()
  #  r = {}
  #  for fieldName, fieldType in modelFieldTypeDict.items():
  #    fieldParam = self._createFieldParam(fieldType, mongoTypeDict)
  #    if(fieldParam is not None):
  #      fieldParam.name = fieldParam.data = fieldType.__class__.__name__
  #      fieldParam.isField = True
  #      r[fieldName] = fieldParam
  #  return r

  #def _createFieldParam(self, fieldType, mongoTypeDict):
  #  for typeName, typeKlass in mongoTypeDict.items():
  #    if(isinstance(fieldType, typeKlass)
  #        or (inspect.isclass(fieldType) and issubclass(fieldType, typeKlass))
  #        ):

  #      fieldParam = FieldParameter(
  #            name=typeName,
  #            data=None,
  #            isField=True,
  #          )
  #      if(typeName in [
  #          "ListField",
  #          "SortedListField",
  #        ]):
  #        fieldParam.childParamLst.append(
  #            self._createFieldParam(
  #              fieldType.field,
  #              mongoTypeDict,
  #              )
  #            )
  #      elif(typeName in [
  #          "MapField",
  #          "DictField",
  #        ]):
  #        fieldParam.childParamLst.append(
  #              FieldParameter(name="StringField", isField=True)
  #          )
  #        fieldParam.childParamLst.append(
  #            self._createFieldParam(
  #              fieldType.field,
  #              mongoTypeDict,
  #              )
  #            )
  #      elif(typeName=="EmbeddedDocumentField"
  #          or typeName=="ReferenceField"
  #          ):
  #        fieldParam.isField = True
  #        fieldParam.data = typeName
  #        try:
  #          modelNameToken = fieldType.document_type\
  #              ._get_collection_name().split("_")
  #          # This is app name
  #          fieldParam.childParamLst.append(
  #                FieldParameter(data=modelNameToken[0])
  #            )
  #          childFieldName = ""
  #          for i in range(1, len(modelNameToken)):
  #            childFieldName += modelNameToken[i].title()
  #          # This is model name
  #          fieldParam.childParamLst.append(FieldParameter(data=childFieldName))
  #        except AttributeError:
  #          # This is for Embedded model
  #          fieldParam.childParamLst.append(
  #            FieldParameter(data=self.modelAppName)
  #            )
  #          childFieldName = fieldType.document_type._types[0]
  #          childFieldName = childFieldName[0].upper() + childFieldName[1:]
  #          fieldParam.childParamLst.append(FieldParameter(data=childFieldName))

  #        # Declare dependency to check circular dependency later
  #        self.modelDepMap[self.modelAppClassName].append(fieldParam)

  #      # After getting all args, now fill up field's kwargs
  #      fieldParam.childParamLst.extend(
  #          self._getFieldParamKwargs(fieldType, typeName)
  #          )
  #      return fieldParam

  #def _getFieldParamKwargs(self, fieldType, typeName):
  #  r = []

  #  for attrName in dir(fieldType):
  #    if(attrName not in self.fieldKwargsLst):
  #      continue
  #    if(attrName=="choices" and getattr(fieldType, attrName) is None):
  #      # In IntField, if choices are not provided, the default is None and we
  #      # do not want to store them
  #      continue
  #    if(callable(getattr(fieldType, attrName))):
  #      # We do not store any function
  #      continue
  #    if(attrName=="default" and typeName in ["FileField", "ImageField"]):
  #      # Data is stored as JSON, we cannot allow any binary data
  #      continue
  #    data = getattr(fieldType, attrName)
  #    isField = False

  #    if(isinstance(data, datetime.datetime)
  #        or isinstance(data, datetime.date)):
  #      if(data-datetime.datetime.utcnow()<datetime.timedelta(minutes=2)):
  #        data = "utcNow"
  #      else:
  #        data.isoformat()
  #    elif(isinstance(data, Promise)):
  #      # that's for lazy translation(_)
  #      data = unicode(data)
  #    elif(isinstance(data, MongoEngineField.BaseField)):
  #      if(attrName=="field"):
  #        continue
  #      # Get the Mongoengine Field class name
  #      data = data.__class__.__name__
  #      attrName = data
  #      isField = True

  #    f = FieldParameter(
  #          name=attrName,
  #          data=data,
  #          isField=isField
  #        )
  #    r.append(f)
  #  return r

  #def _probeModelFieldOrg(self, modelClassName, modelClass):
  #  # Should add debug flag checking and dump to log file instead
  #  model = deepcopy(self.modelTemplate)
  #  if(model.importPath.endswith("__init__")):
  #    # if the class locates at __init__.py, __init__ shoule not be included
  #    # in the import path
  #    model.importPath = model.importPath[:-9]
  #  elif(not model.importPath.endswith(modelClassName[0].lower()
  #      + modelClassName[1:])):
  #    # Except for __init__ or singular model.py, all other files can
  #    # only contain a class which match its filename.
  #    # E.x: sampleClass.py shoule be only import SampleClass.
  #    # During class probing in a file using meta-programming technique,
  #    # the import class will also be regarded as a class in the file.
  #    # To avoid complicated mechanism to match classes and filesnames,
  #    # one file contained one class applied.
  #    return None

  #  token = model.importPath.split(".")

  #  if(len(token)>1):
  #    token.insert(-1, "model")
  #    token.append(modelClassName)
  #    model.importPath = ".".join(token)
  #  elif(len(token)==1):
  #    model.importPath += ".model." + modelClassName

  #  self.modelAppClassName = "{0}|{1}".format(token[0], modelClassName)
  #  model.app = token[0]
  #  self.modelAppName = model.app
  #  model.name = modelClassName
  #  model.fieldParamMap = self._createFieldParamMap(modelClass._fields)
  #  model.tblField = model.formField = modelClass._fields.keys()
  #  model.isEmbedded = issubclass(modelClass, TheoryEmbeddedModel)
  #  return model

  # -----------------------------------------------------------------------

  def _createFieldParamMap(self, modelFieldTypeLst, appModel):
    theoryTypeDict = self._getTheoryTypeDict()
    r = []
    for fieldType in modelFieldTypeLst:
      fieldName = fieldType.name
      fieldParam = self._createFieldParam(
          fieldType,
          theoryTypeDict,
          appModel
          )
      if(fieldParam is not None):
        fieldParam.name = fieldName
        fieldParam.data = fieldType.__class__.__name__
        fieldParam.isField = True
        #r[fieldName] = fieldParam
        r.append(fieldParam)
    return r

  def _createFieldParam(self, fieldType, theoryTypeDict, appModel):
    for typeName, typeKlass in theoryTypeDict.items():
      if (isinstance(fieldType, typeKlass)
          or (
            inspect.isclass(fieldType)
            and issubclass(fieldType, typeKlass)
            )
          ):
        fieldParam = FieldParameter(
              name=typeName,
              data=None,
              isField=True,
              appModel=appModel,
            )
        if(typeName in [
            "ArrayField",
          ]):
          r = self._createFieldParam(
                fieldType.baseField,
                theoryTypeDict,
                appModel,
                )
          r.data = r.name
          r.name = typeName
          fieldParam.data = typeName
          fieldParam.isField = True
          fieldParam.save()
          fieldParam.childParamLst.add(r)
        elif(typeName == "ForeignKey"):
          fieldParam.isField = True
          fieldParam.data = typeName

          meta = fieldType.relatedFields[0][1].modal._meta
          try:
            appName = meta.appConfig.module.__name__,
            appName = appName[0]
          except AttributeError:
            appName = meta.appLabel

          # This is app name
          fieldParam.save()
          FieldParameter(
              name="foreignApp",
              data=appName,
              parent=fieldParam,
              appModel=appModel,
              ).save()

          # This is model name
          FieldParameter(
              name="foreignModel",
              data=meta.objectName,
              parent=fieldParam,
              appModel=appModel,
              ).save()

          # Declare dependency to check circular dependency later
          self.modelDepMap[self.modelAppClassName].append(fieldParam)
        elif(typeName in [
            "ManyToManyField",
            "OneToOneField",
          ]):
          fieldParam.isField = True
          fieldParam.data = typeName

          meta = fieldType.related.parentModel._meta
          try:
            appName = meta.appConfig.module.__name__,
            appName = appName[0]
          except AttributeError:
            appName = meta.appLabel

          # This is app name
          fieldParam.save()
          FieldParameter(
              name="foreignApp",
              data=appName,
              parent=fieldParam,
              appModel=appModel,
              ).save()

          # This is model name
          FieldParameter(
              name="foreignModel",
              data=meta.objectName,
              parent=fieldParam,
              appModel=appModel,
              ).save()

          # Declare dependency to check circular dependency later
          self.modelDepMap[self.modelAppClassName].append(fieldParam)
        elif(typeName == "IntegerField"):
          if hasattr(fieldType, "choices") and len(fieldType.choices) > 0:
            # For enum field
            fieldParam.isField = True
            fieldParam.data = fieldParam.name
            fieldParam.save()
            FieldParameter(
                name="choices",
                data=json.dumps(fieldType.choices),
                parent=fieldParam,
                appModel=appModel,
                ).save()


        # After getting all args, now fill up field's kwargs
        for i in self._getFieldParamKwargs(fieldType, typeName):
          i.parent = fieldParam
          i.appModel = appModel
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
        data = str(data)
      #elif(isinstance(data, MongoEngineField.BaseField)):
      #  if(attrName=="field"):
      #    continue
      #  # Get the Mongoengine Field class name
      #  data = data.__class__.__name__
      #  attrName = data
      #  isField = True

      f = FieldParameter(
            name=attrName,
            data=data,
            isField=isField
          )
      r.append(f)
    return r


  def _probeModelField(self, modelClassName, modelClass):
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

    model.app = ".".join(token)
    if(len(token)>1):
      token.append("model")
      #token.insert(-1, "model")
      token.append(modelClassName)
      model.importPath = ".".join(token)
    elif(len(token)==1):
      model.importPath += ".model." + modelClassName

    self.modelAppClassName = "{0}|{1}".format(token[0], modelClassName)
    self.modelAppName = model.app
    model.name = modelClassName
    model.tblField = model.formField = []
    model.save()
    model.fieldParamMap = self._createFieldParamMap(
        modelClass._meta.fields + modelClass._meta.manyToMany,
        model
        )
    model.tblField = model.formField = \
        [i.name for i in modelClass._meta.fields]
    # It might cause FieldError: Unknown field(s)
    #model.tblField = model.formField = modelClass._meta.getAllFieldNames()
    return model

  def scan(self):
    self._modelLst = []
    modelClassLst = self._loadModelClass(
        self.modelTemplate.importPath
        )
    self.modelAppClassName = None
    for modelClassName, modelClass in modelClassLst:
      model = self._probeModelField(modelClassName, modelClass)
      if(model is not None):
        self._modelLst.append(model)

