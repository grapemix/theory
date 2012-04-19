# -*- coding: utf-8 -*-
#!/usr/bin/env python
##### System wide lib #####
from abc import ABCMeta, abstractmethod
##### Theory lib #####
from theory.utils.importlib import import_module

##### Theory third-party lib #####

##### Local app #####

##### Theory app #####

##### Misc #####

class BaseClassScanner(object):
  __metaclass__ = ABCMeta

  def _loadSubModuleCommandClass(self, packageName, moduleName, submoduleName):
    """
    Given a package name, module name and an submodule name, returns the
    class instance. All errors raised by the import process
    (ImportError, AttributeError) are allowed to propagate.
    """
    if(submoduleName=="__init__"):
      module = import_module('%s.%s' % (packageName, moduleName))
    else:
      #print packageName, moduleName, submoduleName
      module = import_module('%s.%s.%s' % (packageName, moduleName, submoduleName))
    return module

  @abstractmethod
  def scan(self, *args, **kwargs):
    pass


