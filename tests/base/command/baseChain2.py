# -*- coding: utf-8 -*-
##### System wide lib #####

##### Theory lib #####

##### Theory third-party lib #####
from theory.command.baseCommand import SimpleCommand
from theory.gui import field
from theory.model import *

##### Local app #####
from .baseChain import BaseChain

##### Theory app #####

##### Misc #####

class BaseChain2(BaseChain):
  name = "baseChain2"
  _notations = ["StdPipe", ]
  _stdIn = ""
  _propertyForTesting = ""

  class ParamForm(SimpleCommand.ParamForm):
    stdIn = field.TextField(label="Std In", help_text="Standard Input")
    customField = field.TextField(required=False) # unused

  @classmethod
  def getCmdModel(cls):
    cmdModel = super(BaseChain2, cls).getCmdModel()
    cmdModel.param = [Parameter(name="stdIn",type="String")]
    return cmdModel

  def run(self):
    return self.paramForm.clean()["stdIn"] + " received"
