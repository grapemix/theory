# -*- coding: utf-8 -*-
#!/usr/bin/env python
##### System wide lib #####
import codecs

##### Theory lib #####
from theory.conf import settings
from theory.model import Command, Parameter
from theory.utils.importlib import import_module

##### Theory third-party lib #####

##### Local app #####
from .baseClassScanner import BaseClassScanner

##### Theory app #####

##### Misc #####

class ParamScanner(object):
  _filePath = ""

  @property
  def paramModelLst(self):
    return self._paramModelLst

  @paramModelLst.setter
  def paramModelLst(self, paramModelLst):
    self._paramModelLst = paramModelLst

  @property
  def filePath(self):
    return self._filePath

  @filePath.setter
  def filePath(self, filePath):
    self._filePath = filePath

  def _loadCommandClassFile(self):
    lines = codecs.open(self._filePath, encoding='utf-8').read().split("\n")
    return lines

  def saveModel(self):
    if(self._cmdModel!=None):
      self._cmdModel.save()

  def scan(self):
    sourceLines = self._loadCommandClassFile()
    paramLabelDict = dict([(self.paramModelLst[i].name, self.paramModelLst[i]) for i in range(len(self.paramModelLst))])

    isParamComment = False
    isParamBlock = False
    for lineNum in range(len(sourceLines)):
      l = sourceLines[lineNum].strip(" ")
      if(isParamBlock and l.startswith(":param")):
        paramLabelDict[paramLabel].comment = l.split(":")[2].strip(" ")
      elif(isParamBlock and l.startswith(":type")):
        paramLabelDict[paramLabel].type = l.split(":")[2].strip(" ")
        paramLabelDict[paramLabel].type = paramLabelDict[paramLabel].type[0].upper() + paramLabelDict[paramLabel].type[1:]
        isParamBlock = False
      if((l.startswith("@") and l.endswith(".setter")) or
          l=="@property"):
        try:
          paramLabel = sourceLines[lineNum+1].strip(" ").split(" ")[1].split("(")[0]
        except (IndexError, KeyError), e:
          continue
        if(not paramLabelDict.has_key(paramLabel)):
          continue
        elif(paramLabelDict[paramLabel].type!=None):
          continue

        isParamBlock = True

    """
    if(hasattr(cmdFileClass, "ABCMeta")):
      self._cmdModel = None
      return
    try:
      cmdClass = getattr(cmdFileClass, self.cmdModel.name[0].upper() + self.cmdModel.name[1:])
      # Should add debug flag checking and dump to log file instead
    except AttributeError:
      self._cmdModel = None
      return

    # To reserve the order of mandatory parameters
    for paramName in getattr(cmdClass, "params"):
      v = getattr(cmdClass, paramName)
      if(isinstance(v, property)):
        param = Parameter(name=paramName, isOptional = False)
        self.cmdModel.param.append(param)

    for k,v in cmdClass.__dict__.iteritems():
      if(isinstance(v, property)):
        param = Parameter(name=k)
        if(getattr(getattr(cmdClass, k), "fset")==None):
          param.isReadOnly = True
        if(k in getattr(cmdClass, "params")):
          #param.isOptional = False
          # To avoid duplicate
          continue
        self.cmdModel.param.append(param)
    """
