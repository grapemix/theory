# -*- coding: utf-8 -*-
#!/usr/bin/env python
##### System wide lib #####
import inspect
from copy import deepcopy

##### Theory lib #####
from theory.apps.adapter import BaseAdapter
from theory.conf import settings
from theory.apps.model import Command

##### Theory third-party lib #####

##### Local app #####
from .baseClassScanner import BaseClassScanner

##### Theory app #####

##### Misc #####

class AdapterClassScanner(BaseClassScanner):
  _adapterLst = []
  @property
  def adapterList(self):
    return self._adapterLst

  @property
  def adapterTemplate(self):
    return self._adapterTemplate

  @adapterTemplate.setter
  def adapterTemplate(self, adapterTemplate):
    self._adapterTemplate = adapterTemplate

  def _loadAdapterClass(self, importPath):
    packageName = ".".join(importPath.split(".")[:-1])
    submoduleName = importPath.split(".")[-1]
    module = self._loadSubModuleCommandClass(packageName, "adapter", submoduleName)

    classLst = []
    if(module!=None):
      for _property in dir(module):
        property = getattr(module, _property)

        if(inspect.isclass(property) and issubclass(property, BaseAdapter)):
          if(hasattr(property, "ABCMeta")):
            continue
          else:
            # Only load the property iff property is a class name and the
            # class is not abstract
            classLst.append((_property, property))
    return classLst


  def scan(self):
    adapterClassLst = self._loadAdapterClass(self.adapterTemplate.importPath)
    for adapterClassName, adapterClass in adapterClassLst:
      # Should add debug flag checking and dump to log file instead
      adapter = deepcopy(self.adapterTemplate)
      adapter.name = adapterClassName[:-7]
      if(adapter.importPath.endswith("__init__")):
        # if the class locates at __init__.py, __init__ shoule not be included
        # in the import path
        adapter.importPath = adapter.importPath[:-9]
      elif(not adapter.importPath.endswith(adapterClassName[0].lower()
          + adapterClassName[1:])):
        # Except for __init__ or singular adapter.py, all other files can
        # only contain a class which match its filename.
        # E.x: sampleClass.py shoule be only import SampleClass.
        # During class probing in a file using meta-programming technique,
        # the import class will also be regarded as a class in the file.
        # To avoid complicated mechanism to match classes and filesnames,
        # one file contained one class applied.
        continue

      token = adapter.importPath.split(".")

      if(adapter.importPath.endswith("theory.apps")):
        adapter.importPath += ".adapter." + adapterClassName
      elif(len(token)>1):
        token.insert(-1, "adapter")
        token.append(adapterClassName)
        adapter.importPath =".".join(token)

      buffer = [] # del me when arrayField is supported
      # Don't use __dict__.items() which unable to retrieve property
      # inheritate from parents
      for k in dir(adapterClass):
        v = getattr(adapterClass, k)
        if(isinstance(v, property)):
          # propert without setting won't be counted
          if(getattr(getattr(adapterClass, k), "fset")!=None):
            buffer.append(k)
      adapter.propertyLst = buffer
      self._adapterLst.append(adapter)

  '''
  def _loadAdapterClass(self):
    """
    Given a command name and an application name, returns the Command
    class instance. All errors raised by the import process
    (ImportError, AttributeError) are allowed to propagate.
    """
    print '%s.adapter' % (self.adapterTemplate.importPath)
    classLst = []
    try:
      module = import_module('%s.adapter' % (self.adapterTemplate.importPath))
    except ImportError:
      module = None
    if(module!=None):
      print dir(module)
      for _property in dir(module):
        property = getattr(module, _property)

        print _property, property, inspect.isclass(property)
        if(inspect.isclass(property) and issubclass(property, BaseAdapter)):
          #klass = import_module('%s.adapter.%s' % (self.adapterTemplate.importPath, property))
          if(hasattr(property, "ABCMeta")):
            continue
          else:
            # in this case, property is a class name and the class is not abstract
            classLst.append((_property, property))
    return classLst

  def scan(self):
    adapterClassLst = self._loadAdapterClass()
    for adapterClassName, adapterClass in adapterClassLst:
      # Should add debug flag checking and dump to log file instead
      print adapterClassName
      adapter = deepcopy(self.adapterTemplate)
      adapter.name = adapterClassName
      adapter.importPath += ".adapter." + adapterClassName

      for k,v in adapterClass.__dict__.items():
        if(isinstance(v, property)):
          if(getattr(getattr(adapterClass, k), "fset")!=None):
            adapter.property.append(k)
      self._adapterLst.append(adapter)
  '''
