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
  runMode = Command.RUN_MODE_SIMPLE

  @classmethod
  def getCmdModel(cls):
    cmdModel = Command(
        name=cls.name,
        app="tests.testBase",
        mood=["test",],
        runMode=cls.runMode
        )
    return cmdModel
