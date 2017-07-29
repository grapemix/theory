# -*- coding: utf-8 -*-
##### System wide lib #####

##### Theory lib #####

##### Theory third-party lib #####
from theory.apps.command.baseCommand import AsyncCommand
from theory.apps.model import Command

##### Local app #####
from .baseChain2 import BaseChain2

##### Theory app #####

##### Misc #####

class AsyncChain2(BaseChain2, AsyncCommand):
  name = "asyncChain2"
  verboseName = "asyncChain2"
  runMode = Command.RUN_MODE_ASYNC

  def run(self, paramFormData):
    super(AsyncChain2, self).run(paramFormData)
    self._stdOut = self.paramForm.clean()["stdIn"] + " received"
