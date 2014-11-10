# -*- coding: utf-8 -*-

##### System wide lib #####

##### Theory lib #####

##### Theory third-party lib #####
from theory.apps.command.baseCommand import SimpleCommand
from theory.gui import field

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
    stdIn = field.TextField(label="Std In", helpText="Standard Input")
    customField = field.TextField(required=False) # unused

  @classmethod
  def getCmdModel(cls):
    cmdModel = super(BaseChain2, cls).getCmdModel()
    cmdModel.parameterSet.create(name="stdIn",type="String")
    return cmdModel

  def run(self, uiParam={}):
    self._stdOut = self.paramForm.clean()["stdIn"] + " received"
