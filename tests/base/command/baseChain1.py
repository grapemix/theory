# -*- coding: utf-8 -*-
##### System wide lib #####

##### Theory lib #####
from theory.command.baseCommand import SimpleCommand
from theory.gui import field
from theory.model import Command

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
    cmdModel = Command(name=cls.name, app="tests.base", mood=["test",])
    return cmdModel
