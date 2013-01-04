# -*- coding: utf-8 -*-
#!/usr/bin/env python
##### System wide lib #####
from mongoengine import Q
import sys

##### Theory lib #####
from theory.adapter.reactorAdapter import ReactorAdapter
from theory.command.baseCommand import AsyncContainer
from theory.core.bridge import Bridge
from theory.core.cmdParser.txtCmdParser import TxtCmdParser
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
    self.adapter = ReactorAdapter({"cmdSubmit": self._parse, "autocompleteRequest": self._autocompleteRequest})
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
    self.adapter.cleanUpCrt()
    if(mode==self.parser.MODE_COMMAND):
      (entryOutput, crtOutput)= self._queryCommandAutocomplete(frag)
      entrySetterFxn(entryOutput)
      if(crtOutput):
        self.adapter.printTxt(crtOutput)
    elif(mode==self.parser.MODE_ARGS):
      self._queryArgsAutocomplete(frag)
    self.parser.initVar()

  def _queryArgsAutocomplete(self, frag):
    cmdModel = Command.objects.get(name=self.parser.cmdName)
    cmdParamForm = import_class(cmdModel.classImportPath).ParamForm

    paramForm = cmdParamForm(self.ui.win, self.ui.bxCrt)
    paramForm.generateFilterForm()
    paramForm.generateStepControl()
    return

  def _parse(self):
    self.parser.cmdInTxt = self.adapter.cmdInTxt
    self.parser.run()
    # should change for chained command
    #if(self.parser.mode==self.parser.MODE_DONE):
    self.run()

  def _performDrums(self, cmd):
    debugLvl = settings.DEBUG_LEVEL
    bridge = Bridge()
    for adapterName, leastDebugLvl in cmd._drums.iteritems():
      if(leastDebugLvl<=debugLvl):
        (adapterModel, drum) = bridge.adaptFromCmd(adapterName, cmd)
        drum.render(uiParam=self.adapter.uiParam)

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

    bridge = Bridge()
    (cmd, storage) = bridge.getCmdComplex(cmdModel, self.parser.args, self.parser.kwargs)

    # Since we only allow execute one command in a time thru terminal,
    # the command doesn't have to return anything
    adapterProperty = []
    if(cmdModel.runMode==cmdModel.RUN_MODE_ASYNC_WRAPPER):
      asyncContainer = AsyncContainer()
      result = asyncContainer.delay(cmd, adapterProperty).get()
    elif(cmdModel.runMode==cmdModel.RUN_MODE_ASYNC):
      #result = cmd.delay(storage).get()
      cmd.delay(storage)
    else:
      asyncContainer = AsyncContainer()
      result = asyncContainer.run(cmd, adapterProperty)

    self._performDrums(cmd)
    self.parser.initVar()
    History(command=self.parser.cmdInTxt, commandRef=cmdModel,
        mood=self.mood).save()

reactor = Reactor()
