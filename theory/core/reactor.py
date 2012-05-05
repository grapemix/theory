# -*- coding: utf-8 -*-
#!/usr/bin/env python
##### System wide lib #####
from mongoengine import Q

##### Theory lib #####
from theory.adapter.reactorAdapter import ReactorAdapter
from theory.model import Command, Adapter, History
from theory.core.cmdParser.txtCmdParser import TxtCmdParser
from theory.core.exceptions import CommandSyntaxError
from theory.conf import settings
from theory.gui.terminal import Terminal
from theory.utils.importlib import  import_class

##### Theory third-party lib #####

##### Local app #####

##### Theory app #####

##### Misc #####

__all__ = ('reactor',)

class Reactor(object):
  _mood = settings.DEFAULT_MOOD
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
    #self.ui.drawAll()

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
    print cmdName, self.mood
    try:
      cmdModel = Command.objects.get(Q(name=cmdName) & (Q(mood=self.mood) | Q(mood="norm")))
    except Command.DoesNotExist:
      self.adapter.printTxt("Command not found")
      self.parser.initVar()
      return

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

reactor = Reactor()
