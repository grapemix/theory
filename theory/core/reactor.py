# -*- coding: utf-8 -*-
#!/usr/bin/env python
##### System wide lib #####
from mongoengine import Q
import sys

##### Theory lib #####
from theory.adapter.reactorAdapter import ReactorAdapter
from theory.command.baseCommand import AsyncContainer
from theory.core.cmdParser.txtCmdParser import TxtCmdParser
from theory.core.exceptions import CommandSyntaxError
from theory.conf import settings
from theory.gui.terminal import Terminal
from theory.model import Command, Adapter, History
from theory.utils.importlib import  import_class

##### Theory third-party lib #####

##### Local app #####

##### Theory app #####

##### Misc #####

__all__ = ('reactor',)

class Reactor(object):
  _mood = settings.DEFAULT_MOOD
  _avblCmd = None
  autocompleteCounter = 0
  lastAutocompleteSuggest = ""
  originalQuest = ""

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
      self._avblCmd = Command.objects.filter(mood=self.mood,)
    return self._avblCmd

  def __init__(self):
    self.parser = TxtCmdParser()
    self.ui = Terminal()
    self.adapter = ReactorAdapter({"cmdSubmit": self.parse, "autocompleteRequest": self._autocompleteRequest})
    # The ui will generate its supported output function
    self.ui.adapter = self.adapter
    settings.CRTWIN = self.ui.win
    settings.CRT = self.ui.bxCrt

  def _queryCommandAutocomplete(self, frag):
    # which means user keeps tabbing
    if(self.lastAutocompleteSuggest==frag):
      frag = self.originalQuest
      self.autocompleteCounter += 1
    else:
      self.autocompleteCounter = 0
      self.lastAutocompleteSuggest = ""
      self.originalQuest = ""
    cmdModelQuery = Command.objects.filter(Q(name__startswith=frag) & (Q(mood=self.mood) | Q(mood="norm")))
    cmdModelQueryNum = cmdModelQuery.count()
    if(cmdModelQueryNum==0):
      return (self.parser.cmdInTxt, None)
    elif(cmdModelQueryNum==1):
      if(cmdModelQuery[0].name==frag):
        crtOutput = cmdModelQuery[0].getDetailAutocompleteHints(self.adapter.crlf)
      else:
        crtOutput = None
      return (cmdModelQuery[0].name, crtOutput)
    elif(cmdModelQueryNum>1):
      suggest = cmdModelQuery[self.autocompleteCounter % cmdModelQueryNum].name
      if(self.autocompleteCounter==0):
        self.originalQuest = frag
      self.lastAutocompleteSuggest = suggest
      crtOutput = self.adapter.crlf.join([i.getAutocompleteHints() for i in cmdModelQuery])
      # e.x: having commands like blah, blah1, blah2
      if(frag==suggest):
        crtOutput += self.adapter.crlf + self.adapter.crlf + cmdModelQuery[self.autocompleteCounter % cmdModelQueryNum]\
            .getDetailAutocompleteHints(self.adapter.crlf)
      return (suggest, crtOutput)

  def _autocompleteRequest(self, entrySetterFxn):
    self.parser.cmdInTxt = self.adapter.cmdInTxt
    self.parser.run()
    (mode, frag) = self.parser.partialInput
    if(mode==self.parser.MODE_COMMAND):
      (entryOutput, crtOutput)= self._queryCommandAutocomplete(frag)
      entrySetterFxn(entryOutput)
      if(crtOutput):
        self.adapter.printTxt(crtOutput)
    elif(mode==self.parser.MODE_ARGS):
      self._queryArgsAutocomplete(frag)
    self.parser.initVar()

  def _queryArgsAutocomplete(self, frag):
    return
    # TODO: complete this feature
    #argIdx = len(self.parser.args)
    #paramModel = Command.objects.get(name=self.parser.cmdName).param[argIdx]
    #argType = paramModel.type
    #classImportPathTempate = "theory.gui.field.%sField" % (argType)
    #fieldClass = import_class(classImportPathTempate)
    #print fieldClass


  def parse(self):
    self.parser.cmdInTxt = self.adapter.cmdInTxt
    self.parser.run()
    # should change for chained command
    #if(self.parser.mode==self.parser.MODE_DONE):
    self.run()

  def _objAssign(self, o, k, v):
    return setattr(o, k, v)

  def _dictAssign(self, o, k, v):
    o[k] = v
    return o

  # TODO: refactor this function, may be with bridge
  def run(self):
    cmdName = self.parser.cmdName
    # should change for chained command
    try:
      cmdModel = Command.objects.get(Q(name=cmdName) & (Q(mood=self.mood) | Q(mood="norm")))
    except Command.DoesNotExist:
      self.adapter.printTxt("Command not found")
      self.parser.initVar()
      return

    cmdKlass = import_class(cmdModel.classImportPath)
    #cmdKlass = import_class(".".join([cmdModel.app, "command", cmdModel.name, cmdModel.className]))
    #cmdKlass = getattr(sys.modules[cmdModel.moduleImportPath], cmdModel.className)
    cmd = cmdKlass()

    try:
      adapterName = cmd.gongs[0]
    except IndexError:
      adapterName = ""

    try:
      adapterModel = Adapter.objects.get(name=adapterName)
      adapterProperty = adapterModel.property
    except Adapter.DoesNotExist:
      adapterModel = None
      adapterProperty = []

    if(cmdModel.runMode==cmdModel.RUN_MODE_ASYNC):
      #assignFxn = lambda o, k, v: o[k] = v
      assignFxn = self._dictAssign
      storage = {}
    else:
      #assignFxn = lambda o, k, v: setattr(o, k, v)
      assignFxn = self._objAssign
      storage = cmd

    cmdArgs = [i for i in cmdModel.param if(not i.isOptional)]
    if(self.parser.args!=[]):
      for i in range(len(cmdArgs)):
        try:
          assignFxn(storage, cmdArgs[i].name, self.parser.args[i])
          #storage = assignFxn(storage, cmdModel.param[i].name, self.parser.args[i])
        except IndexError:
          # This means the number of param given unmatch the number of param register in *.command
          raise CommandSyntaxError
    if(self.parser.kwargs!={}):
      for k,v in self.parser.kwargs.iteritems():
        #setattr(cmd, k, v)
        storage = assignFxn(storage, k, v)

    if(cmdModel.runMode==cmdModel.RUN_MODE_ASYNC_WRAPPER):
      asyncContainer = AsyncContainer()
      result = asyncContainer.delay(cmd, adapterProperty).get()
    elif(cmdModel.runMode==cmdModel.RUN_MODE_ASYNC):
      result = cmd.delay(storage).get()
    else:
      asyncContainer = AsyncContainer()
      result = asyncContainer.run(cmd, adapterProperty)

    if(adapterModel!=None):
      adapterKlass = import_class(adapterModel.importPath)
      adapter = adapterKlass()
      for property in adapterModel.property:
        try:
          setattr(adapter, property, result[property])
        except KeyError:
          try:
            setattr(adapter, property, result[cmd, "_" + property])
          except KeyError:
            pass

      if(hasattr(adapter, "stdOut")):
        self.adapter.printTxt(adapter.stdOut)

    self.parser.initVar()
    History(command=self.parser.cmdInTxt, commandRef=cmdModel,
        mood=self.mood).save()

reactor = Reactor()
