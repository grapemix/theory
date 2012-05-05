# -*- coding: utf-8 -*-
#!/usr/bin/env python
##### System wide lib #####

##### Theory lib #####
from theory.conf import settings
from theory.core.reactor import *
from theory.utils.mood import loadMoodData

##### Theory third-party lib #####

##### Local app #####
from .baseCommand import BaseCommand

##### Theory app #####

##### Misc #####

class SwitchMood(BaseCommand):
  """
  To switch Theory mood
  """
  name = "switchMood"
  verboseName = "switchMood"
  params = ["moodName",]
  _notations = ["Command",]
  _gongs = ["Terminal", ]

  @property
  def moodName(self):
    return self._moodName

  @moodName.setter
  def moodName(self, moodName):
    self._moodName = moodName

  def run(self, *args, **kwargs):
    config = loadMoodData(self.moodName)
    for i in dir(config):
      if(i==i.upper()):
        settings.MOOD[i] = getattr(config, i)

    reactor.mood = self.moodName

    self._stdOut += "Successfully switch to %s mood%s" % (self.moodName, "<br/>")
    self._stdOut += str([(k,v) for k,v in settings.MOOD.iteritems()])

