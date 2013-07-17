# -*- coding: utf-8 -*-
#!/usr/bin/env python
##### System wide lib #####
import inspect
from copy import deepcopy
from mongoengine import *

##### Theory lib #####
from theory.model import Model
from theory.db.models import EmbeddedDocument as TheoryEmbeddedModel
from theory.conf import settings
from theory.model import Command, Parameter
from theory.utils.importlib import import_module, import_class

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


  def scan(self):
    modelClassLst = self._loadModelClass(self.modelTemplate.importPath)
    for modelClassName, modelClass in modelClassLst:
      if(modelClassName=="Model"
          or modelClassName=="EmbeddedDocument"
          or modelClassName=="DynamicEmbeddedDocument"):
        continue

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
        continue

      token = model.importPath.split(".")

      if(len(token)>1):
        token.insert(-1, "model")
        token.append(modelClassName)
        model.importPath =".".join(token)
      elif(len(token)==1):
        model.importPath += ".model." + modelClassName

      model.app = token[0]
      model.name = modelClassName
      model.paramName = modelClass._fields.keys()

      self._modelLst.append(model)
