# -*- coding: utf-8 -*-
##### System wide lib #####

##### Theory lib #####
from theory.command.baseCommand import SimpleCommand

##### Theory third-party lib #####

##### Local app #####
from .baseChain1 import BaseChain1

##### Theory app #####

##### Misc #####

class SimpleChain1(BaseChain1, SimpleCommand):
  name = "simpleChain1"
  verboseName = "simpleChain1"

  def run(self, uiParam={}):
    self._stdOut = "simpleChain1"
