# -*- coding: utf-8 -*-
##### System wide lib #####

##### Theory lib #####
from theory.command.baseCommand import AsyncCommand

##### Theory third-party lib #####

##### Local app #####
from .baseChain1 import BaseChain1

##### Theory app #####

##### Misc #####

class AsyncChain1(BaseChain1, AsyncCommand):
  name = "asyncChain1"
  verboseName = "asyncChain1"
  _stdOut = name

  def run(self):
    self._stdOut = "asyncChain1"
