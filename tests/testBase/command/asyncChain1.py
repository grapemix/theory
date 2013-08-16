# -*- coding: utf-8 -*-
##### System wide lib #####

##### Theory lib #####
from theory.command.baseCommand import AsyncCommand
from theory.model import Command

##### Theory third-party lib #####

##### Local app #####
from .baseChain1 import BaseChain1

##### Theory app #####

##### Misc #####

class AsyncChain1(BaseChain1, AsyncCommand):
  name = "asyncChain1"
  verboseName = "asyncChain1"
  runMode = Command.RUN_MODE_ASYNC

  def run(self, *args, **kwargs):
    super(AsyncChain1, self).run(*args, **kwargs)
    self._stdOut = "asyncChain1"
