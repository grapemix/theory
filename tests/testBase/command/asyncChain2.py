# -*- coding: utf-8 -*-
##### System wide lib #####

##### Theory lib #####

##### Theory third-party lib #####
from theory.command.baseCommand import AsyncCommand
from theory.model import Command

##### Local app #####
from .baseChain2 import BaseChain2

##### Theory app #####

##### Misc #####

class AsyncChain2(BaseChain2, AsyncCommand):
  name = "asyncChain2"
  verboseName = "asyncChain2"
  runMode = Command.RUN_MODE_ASYNC

  def run(self, *args, **kwargs):
    super(AsyncChain2, self).run(*args, **kwargs)
    self._stdOut = self.paramForm.clean()["stdIn"] + " received"
