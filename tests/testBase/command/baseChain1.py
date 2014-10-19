# -*- coding: utf-8 -*-
##### System wide lib #####

##### Theory lib #####
from theory.apps.command.baseCommand import SimpleCommand
from theory.apps.model import Command, Mood
from theory.gui import field

##### Theory third-party lib #####

##### Local app #####
from .baseChain import BaseChain

##### Theory app #####

##### Misc #####

class BaseChain1(BaseChain):
  name = "baseChain1"
  _gongs = ["StdPipe", ]

  class ParamForm(SimpleCommand.ParamForm):
    customField = field.TextField(required=False)

  @classmethod
  def getCmdModel(cls):
    cmdModel = Command(
        name=cls.name,
        app="tests.testBase",
        runMode=cls.runMode
        )
    cmdModel.save()
    moodModel, created = Mood.objects.getOrCreate(name="test")
    cmdModel.moodSet.add(moodModel)
    return cmdModel
