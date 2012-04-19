# -*- coding: utf-8 -*-
##### System wide lib #####
import re

##### Theory lib #####
from theory.adapter.reactorAdapter import ReactorAdapter
from theory.model import Command, Adapter, History
from theory.core.exceptions import CommandSyntaxError
from theory.gui.terminal import Terminal
from theory.utils.importlib import import_module, import_class

##### Theory third-party lib #####

##### Local app #####

##### Theory app #####

##### Misc #####

# TODO: move this class to a single file
class TxtCmdParser(object):
  MODE_EMPTY = 0
  MODE_ERROR = 1
  MODE_COMMAND = 2
  MODE_ARGS = 3
  MODE_KWARGS = 4
  MODE_SINGLE_QUOTE = 5
  MODE_DOUBLE_QUOTE = 6
  MODE_DONE = 7

  MODE_CHOICE = (
      (MODE_EMPTY, "empty"),
      (MODE_ERROR, "error"),
      (MODE_COMMAND, "command"),
      (MODE_ARGS, "arguments"),
      (MODE_KWARGS, "keyword arguments"),
      (MODE_SINGLE_QUOTE, "single quote"),
      (MODE_DOUBLE_QUOTE, "double quote"),
      (MODE_DONE, "done"),
  )

  @property
  def cmdInTxt(self):
    return self._cmdInTxt

  @cmdInTxt.setter
  def cmdInTxt(self, cmdInTxt):
    self._lastCmdInTxt = self._cmdInTxt
    self._cmdInTxt = cmdInTxt

  @property
  def args(self):
    return self._args

  @property
  def kwargs(self):
    return self._kwargs

  @property
  def cmdName(self):
    return self._cmdName

  @property
  def mode(self):
    try:
      isInParen = self._openParenIdx[-1] > self._closeParenIdx[-1]
    except IndexError:
      isInParen = False

    if(self._cmdInTxt==""):
      return self.MODE_EMPTY
    elif(self._isDetectError):
      return self.MODE_ERROR
    elif(len(self._singleQuoteIdx) % 2 != 0):
      return self.MODE_SINGLE_QUOTE
    elif(len(self._doubleQuoteIdx) % 2 != 0):
      return self.MODE_DOUBLE_QUOTE
    elif(self._inKwargs):
      return self.MODE_KWARGS
    elif(len(self._openParenIdx)==1 and len(self._closeParenIdx)==0):
      return self.MODE_ARGS if self._cmdInTxt[-1] != "=" else self.MODE_KWARGS
    elif(isInParen):
      return self.MODE_ARGS if self._cmdInTxt[-1] != "=" else self.MODE_KWARGS
    else:
      return self.MODE_COMMAND

  @property
  def partialInput(self):
    mode = self.mode
    if(mode==self.MODE_SINGLE_QUOTE \
        or mode==self.MODE_DOUBLE_QUOTE \
        or mode==self.MODE_EMPTY \
        ):
      return (mode, "")
    elif(mode==self.MODE_COMMAND):
      return (mode, self._cmdName)
    elif(mode==self.MODE_ARGS):
      try:
        return (mode, self._cmdInTxt[self._commaIdx[-1]:])
      except IndexError:
        return (mode, self._cmdInTxt[self._openParenIdx[-1]:])

  def __init__(self):
    self.legitCmdNameRePattern = re.compile("^[A-z]+\w+$")
    self.initVar()

  def initVar(self):
    self._cmdName = ""
    #self._param = OrderedDict()
    self._args = []
    self._kwargs = {}
    self._singleQuoteIdx = []
    self._doubleQuoteIdx = []
    self._openParenIdx = []
    self._closeParenIdx = []
    self._commaIdx = []
    self._cmdInTxt = ""
    self._lastCmdInTxt = ""
    self._lastEqualSignIdx = 0
    self._inKwargs = False
    self._isDetectError = False

  def _checkFirstChar(self, c):
    pass

  def _buildSpecialCharIdx(self, cmdInTxt):
    mode = self.MODE_EMPTY
    for i in range(len(cmdInTxt)):
      c = cmdInTxt[i]
      if(mode!=self.MODE_SINGLE_QUOTE and c=="\""):
        self._doubleQuoteIdx.append(i)
        mode = self.MODE_DOUBLE_QUOTE if len(self._doubleQuoteIdx) % 2!=0 else self.MODE_EMPTY
      elif(mode!=self.MODE_DOUBLE_QUOTE and c=="'"):
        self._singleQuoteIdx.append(i)
        mode = self.MODE_SINGLE_QUOTE if len(self._singleQuoteIdx) % 2!=0 else self.MODE_EMPTY
      # Anything between single quote or double qoute will not be considered as special char
      elif(mode==self.MODE_SINGLE_QUOTE or mode==self.MODE_DOUBLE_QUOTE):
        continue
      elif(c==","):
        self._commaIdx.append(i)
      elif(c=="("):
        self._openParenIdx.append(i)
      elif(c==")"):
        self._closeParenIdx.append(i)
      elif(c=="="):
        self._lastEqualSignIdx = i

  # TODO: adding more rules
  def _validateCmdByIdx(self, cmdInTxt):
    if(self.mode() == self.MODE_COMMAND):
      if(self._cmdName.contains(",\"'")):
        raise CommandSyntaxError
    elif(self.mode() == self.MODE_DONE):
      #validate indexes
      if(self._closeParenIdx[-1]+1!=len(cmdInTxt)):
        raise CommandSyntaxError

      for idx in ["_doubleQuoteIdx", "_singleQuoteIdx", ]:
        if(len(getattr(self, idx)) % 2 != 0 ):
          raise CommandSyntaxError

      if((len(self._openParenIdx) + len(self._closeParenIdx)) % 2 != 0):
          raise CommandSyntaxError

  # TODO: support recursive cmd and chain cmd
  def _parseCmdInTxt(self):
    try:
      self._cmdName = self.cmdInTxt[0:self._openParenIdx[0]]
    except IndexError:
      self._cmdName = self.cmdInTxt
    if(not self.legitCmdNameRePattern.match(self._cmdName)):
      self._isDetectError = True
      return

    paramRegion = ""
    try:
      # for chain cmd, the idx should be replaced by for-loop kind structure
      paramStart = self._openParenIdx[0] + 1
      try:
        paramEnd = self._closeParenIdx[0]
      except IndexError:
        paramEnd = len(self.cmdInTxt)
    except IndexError:
      paramStart = 0
      paramEnd = 0
    (self._args, self._kwargs) = self._parseParamRegion(paramStart, paramEnd)

  def _locateIdxInRegion(self, idx, floor, ceiling):
    idxLen = len(idx)
    for i in range(idxLen):
      if(idx[i]>ceiling):
        return None
      elif(floor<idx[i]<ceiling):
        return idx[i]
    return None

  def _parseParamRegion(self, paramStart, paramEnd):
    args = []
    kwargs = {}
    if(paramStart!=0 and paramEnd!=0):
      lastCommaIdx = paramStart - 1
      while(True):
        commaIdx = self._locateIdxInRegion(self._commaIdx, lastCommaIdx, paramEnd)
        if(commaIdx==None):
          commaIdx = paramEnd
          break
        else:
          (args, kwargs) = self._parseParam(self._cmdInTxt[lastCommaIdx+1:commaIdx], args, kwargs)
          lastCommaIdx = commaIdx
      (args, kwargs) = self._parseParam(self._cmdInTxt[lastCommaIdx+1:commaIdx], args, kwargs)
    return (args, kwargs)

  def _parseParam(self, param, args, kwargs):
    param = param.strip()
    #r.append([i.strip() for i in param.split("=")])
    if(param==""):
      # for case like fxn()
      return (args, kwargs)
    elif(not param.startswith('"') and not param.startswith("'")):
      paramLen = 0
      param = param.split("=")
      for i in range(len(param)):
        paramLen += 1
        param[i] = param[i].strip().strip("'").strip('"')
      if(paramLen>1):
        kwargs[param[0]] = param[1]
      else:
        args.append(param[0])
    else:
      args.append(param.strip().strip("'").strip('"'))
    return (args, kwargs)

  def run(self):
    if(self.cmdInTxt==""):
      self.initVar()
      return
    self._checkFirstChar(self.cmdInTxt[0])
    self._buildSpecialCharIdx(self.cmdInTxt)
    self._parseCmdInTxt()

class Reactor(object):
  _mood = "norm"
  _avblCmd = None

  @property
  def mood(self):
    return self._mood

  @mood.setter
  def mood(self, mood):
    self._mood = mood

  @property
  def avblCmd(self):
    if(self._avblCmd!=None):
      return self._avblCmd
    else:
      self._avblCmd = Commands.objects.filter(mood=self.mood,)
    return self._avblCmd

  def __init__(self):
    self.parser = TxtCmdParser()
    self.ui = Terminal()
    self.adapter = ReactorAdapter({"cmdSubmit": self.parse})
    self.ui.adapter = self.adapter
    self.ui.drawAll()

  def parse(self):
    self.parser.cmdInTxt = self.adapter.cmdInTxt
    self.parser.run()
    # should change for chained command
    #if(self.parser.mode==self.parser.MODE_DONE):
    self.run()

  def test(self):
    self.parser.cmdName = "listCommand"
    self.run()

  # TODO: refactor this function, may be with bridge
  def run(self):
    cmdName = self.parser.cmdName
    # should change for chained command
    cmdModel = Command.objects.get(name=cmdName, mood=self.mood)
    cmdKlass = import_class(".".join([cmdModel.app, "command", cmdModel.name, cmdModel.className]))
    cmd = cmdKlass()
    #print self.parser.args, self.parser.kwargs
    if(self.parser.args!=[]):
      for i in range(len(cmdModel.param)):
        try:
          setattr(cmd, cmdModel.param[i].name, self.parser.args[i])
        except IndexError:
          # This means the number of param given unmatch the number of param register in *.command
          raise CommandSyntaxError
    if(self.parser.kwargs!={}):
      for k,v in self.parser.kwargs.iteritems():
        setattr(cmd, k, v)
    cmd.run()

    try:
      adapterName = cmd.gongs[0]
    except IndexError:
      adapterName = ""

    try:
      adapterModel = Adapter.objects.get(name=adapterName)
    except Adapter.DoesNotExist:
      adapterModel = None

    if(adapterModel!=None):
      adapterKlass = import_class(adapterModel.importPath)
      adapter = adapterKlass()
      for property in adapterModel.property:
        try:
          setattr(adapter, property, getattr(cmd, property))
        except AttributeError:
          try:
            setattr(adapter, property, getattr(cmd, "_" + property))
          except AttributeError:
            pass

      if(hasattr(adapter, "stdOut")):
        self.adapter.printTxt(adapter.stdOut)

    self.parser.initVar()
    History(command=self.parser.cmdInTxt, commandRef=cmdModel,
        mood=self.mood).save()
