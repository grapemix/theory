# -*- coding: utf-8 -*-
##### System wide lib #####
from mongoengine import *

##### Theory lib #####
from theory.conf import settings
from theory.model import Command, Parameter
from theory.utils.importlib import import_module

##### Theory third-party lib #####

##### Local app #####

##### Theory app #####

##### Misc #####

class ClassScanner(object):
  @property
  def cmdModel(self):
    return self._cmdModel

  @cmdModel.setter
  def cmdModel(self, cmdModel):
    self._cmdModel = cmdModel

  """
  @property
  def cmdProperties(self):
    return self._cmdProperties

  @property
  def cmdOnlyProperties(self):
    return self._cmdOnlyProperties
  """

  def _loadCommandClass(self):
    """
    Given a command name and an application name, returns the Command
    class instance. All errors raised by the import process
    (ImportError, AttributeError) are allowed to propagate.
    """
    module = import_module('%s.command.%s' % (self.cmdModel.app, self.cmdModel.name))
    return module
    #return module.Command()


  def scan(self):
    cmdFileClass = self._loadCommandClass()
    if(hasattr(cmdFileClass, "ABCMeta")):
      return
    cmdClass = getattr(cmdFileClass, self.cmdModel.name[0].upper() + self.cmdModel.name[1:])

    for k,v in cmdClass.__dict__.iteritems():
      if(isinstance(v, property)):
        param = Parameter(name=k)
        if(getattr(getattr(cmdClass, k), "fset")==None):
          param.isReadOnly = True
        self.cmdModel.param.append(param)

    #self._cmdReadOnlyProperties = [i for i in cmdProperties \

    #self._cmdProperties = [k for k,v in cmdClass.__dict__.iteritems()\
    #    if(isinstance(v, property))]
    #self._cmdReadOnlyProperties = [i for i in cmdProperties \
    #    if(getattr(getattr(cmdClass, i), "fset")==None)]

    #print [i for i in vars(cmdClass).keys() if(isinstance(i, property))]
    #print dir(cmdClass)
