# -*- coding: utf-8 -*-
##### System wide lib #####

##### Theory lib #####
from theory.model import Command

##### Theory third-party lib #####

##### Local app #####

##### Theory app #####

##### Misc #####

class BaseChain(object):
  name = "baseChain"

  @classmethod
  def getCmdModel(cls):
    cmdModel = Command(name=cls.name, app="tests.base", mood=["test",])
    return cmdModel
