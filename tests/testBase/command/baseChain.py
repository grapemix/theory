# -*- coding: utf-8 -*-
##### System wide lib #####

##### Theory lib #####
from theory.apps.model import Command, Mood

##### Theory third-party lib #####

##### Local app #####

##### Theory app #####

##### Misc #####

class BaseChain(object):
  name = "baseChain"
  runMode = Command.RUN_MODE_SIMPLE

  @classmethod
  def getCmdModel(cls):
    # It is mongoengine's bug. Del me after mongoengine fix it.
    #Command.objects.filter(name=cls.name).delete()
    cmdModel = Command(
        name=cls.name,
        app="tests.testBase",
        runMode=cls.runMode
        )
    cmdModel.save()
    moodModel, created = Mood.objects.getOrCreate(name="test")
    cmdModel.moodSet.add(moodModel)
    return cmdModel
