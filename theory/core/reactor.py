# -*- coding: utf-8 -*-
#!/usr/bin/env python
##### System wide lib #####
from datetime import datetime
from mongoengine import Q
import sys

##### Theory lib #####
from theory.adapter.reactorAdapter import ReactorAdapter
from theory.core.bridge import Bridge
from theory.core.cmdParser.txtCmdParser import TxtCmdParser
from theory.conf import settings
from theory.gui.terminal import Terminal
from theory.model import Command, Adapter, History
from theory.utils.importlib import import_class

##### Theory third-party lib #####

##### Local app #####

##### Theory app #####

##### Misc #####

__all__ = ('reactor',)

class Reactor(object):
  """
  It should be in charge to handle the high level user interaction bewteen
  theory and user. And it should dedicated on the GUI part, but able to
  seperate with the logic from a specific toolkit. It is implemented into
  singleton pattern.
  """

  _mood = settings.DEFAULT_MOOD
  _avblCmd = None
  autocompleteCounter = 0
  lastAutocompleteSuggest = ""
  originalQuest = ""
  paramForm = None
  historyIndex = -1  # It should be working reversely
  historyLen = 0

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
    self.adapter = ReactorAdapter(
        {
          "cmdSubmit": self._parse,
          "autocompleteRequest": self._autocompleteRequest,
          "showPreviousCmdRequest": self._showPreviousCmdRequest,
          "showNextCmdRequest": self._showNextCmdRequest,
          "escapeRequest": self._escapeRequest,
        }
    )
    # The ui will generate its supported output function
    self.ui.adapter = self.adapter
    settings.CRTWIN = self.ui.win
    settings.CRT = self.ui.bxCrt
    self.historyModel = History.objects.all()
    self.historyLen = len(self.historyModel)

  def _queryCommandAutocomplete(self, frag):
    # which means user keeps tabbing
    if(self.lastAutocompleteSuggest==frag):
      frag = self.originalQuest
      self.autocompleteCounter += 1
    else:
      self.autocompleteCounter = 0
      self.lastAutocompleteSuggest = ""
      self.originalQuest = ""

    # Temp disable using mood as reference during the autocomplete process because of a bug of mongoengine. This feature should be restored when mongoengine is updated.
    cmdModelQuery = Command.objects.filter(name__startswith=frag)
    #cmdModelQuery = Command.objects.filter(Q(name__startswith=frag) & (Q(mood=self.mood) | Q(mood="norm")))
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


  def _showPreviousCmdRequest(self, entrySetterFxn):
    if(self.historyIndex >= self.historyLen):
      entrySetterFxn("")
    else:
      if(self.historyIndex + 1 < self.historyLen):
        self.historyIndex += 1
      commandName = self.historyModel[self.historyIndex].commandName
      entrySetterFxn(commandName)

  def _showNextCmdRequest(self, entrySetterFxn):
    if(self.historyIndex == -1):
      entrySetterFxn("")
    else:
      if(self.historyIndex - 1 >= 0):
        self.historyIndex -= 1
      commandName = self.historyModel[self.historyIndex].commandName
      entrySetterFxn(commandName)

  def _escapeRequest(self, entrySetterFxn):
    self.historyIndex = -1
    entrySetterFxn("")
    self.adapter.cleanUpCrt()

  def _autocompleteRequest(self, entrySetterFxn):
    self.parser.cmdInTxt = self.adapter.cmdInTxt
    self.parser.run()
    (mode, frag) = self.parser.partialInput
    self.adapter.cleanUpCrt()
    if(mode==self.parser.MODE_ERROR):
      # Not doing anything in here, but the cleanUpCrt() and initVar() will
      # still be run
      pass
    elif(mode==self.parser.MODE_COMMAND):
      (entryOutput, crtOutput)= self._queryCommandAutocomplete(frag)
      entrySetterFxn(entryOutput)
      if(crtOutput):
        self.adapter.printTxt(crtOutput)
      self.paramForm = None
    elif(mode==self.parser.MODE_ARGS):
      if(not self._queryArgsAutocompleteAsForm()):
        self.adapter.cleanUpCrt()
        self.adapter.printTxt("Cannot load command")
      # Cut the last tab out
      self.adapter.restoreCmdLine()
      self.paramForm.focusOnTheFirstChild()
    self.parser.initVar()

  def cleanParamForm(self, btn):
    if(self.paramForm.is_valid()):
      self.run()
    else:
      # TODO: integrate with std reactor error system
      print self.paramForm.errors

  def _queryArgsAutocompleteAsForm(self):
    if(not self._loadCmdModel()):
      return False

    cmdParamFormKlass = import_class(self.cmdModel.classImportPath).ParamForm

    self.paramForm = cmdParamFormKlass()
    self.paramForm._nextBtnClick = self.cleanParamForm
    self.paramForm.generateFilterForm(*self.adapter.uiParam.values())
    self.paramForm.generateStepControl(cleanUpCrtFxn=self.adapter.cleanUpCrt)
    return True

  def _parse(self):
    self.parser.cmdInTxt = self.adapter.cmdInTxt
    self.parser.run()
    # should change for chained command
    #if(self.parser.mode==self.parser.MODE_DONE):

    if(not self._loadCmdModel()):
      return

    self.run()

  def _performDrums(self, cmd):
    debugLvl = settings.DEBUG_LEVEL
    bridge = Bridge()
    for adapterName, leastDebugLvl in cmd._drums.iteritems():
      if(leastDebugLvl<=debugLvl):
        (adapterModel, drum) = bridge.adaptFromCmd(adapterName, cmd)
        drum.render(uiParam=self.adapter.uiParam)

  def reset(self):
    self.parser.initVar()
    self.cmdModel = None
    self.paramForm = None
    self.historyIndex = -1

  def _fillParamForm(self, cmdModel):
    bridge = Bridge()
    return bridge.getCmdComplex(cmdModel, self.parser.args, self.parser.kwargs)

  def _loadCmdModel(self):
    """Error should be handle within this fxn, return False in case not found"""
    cmdName = self.parser.cmdName
    # should change for chained command
    try:
      self.cmdModel = Command.objects.get(
          Q(name=cmdName)
          & (Q(mood=self.mood) | Q(mood="norm"))
      )
    except Command.DoesNotExist:
      # TODO: integrate with std reactor error system
      self.adapter.printTxt("Command not found")
      self.reset()
      return False
    return True

  def _updateHistory(self, jsonData):
    # Temp disable. During the development stage, reprobeAllModule is run almost
    # everytime which delete all command module. However, since the
    # reverse_delete_rule of the command field is cascade, all history record
    # will be lost. This field should re-enable in the future.
    #History(commandName=self.parser.cmdInTxt, command=self.cmdModel,

    History.objects(
        commandName=self.parser.cmdInTxt,
        mood=self.mood,
        jsonData=jsonData,
        ).update_one(
            inc__repeated=1,
            set__touched=datetime.utcnow(),
            upsert=True
            )

    self.historyModel = History.objects.all()
    self.historyLen += 1

  # TODO: refactor this function, may be with bridge
  def run(self):
    if(self.paramForm==None):
      cmd = self._fillParamForm(self.cmdModel)
    else:
      cmdKlass = import_class(self.cmdModel.classImportPath)
      cmd = cmdKlass()
      cmd.paramForm = self.paramForm

    bridge = Bridge()
    if(not bridge._execeuteCommand(cmd, self.cmdModel, self.adapter.uiParam)):
      # TODO: integrate with std reactor error system
      print cmd.paramForm.errors
      self.adapter.restoreCmdLine()
      return

    self._performDrums(cmd)

    self._updateHistory(cmd.paramForm.toJson())

    self.reset()

reactor = Reactor()
