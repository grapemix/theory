# -*- coding: utf-8 -*-
#!/usr/bin/env python
##### System wide lib #####

##### Theory lib #####
from theory.conf import settings
from theory.core.reactor import *
from theory.utils.mood import loadMoodData

##### Theory third-party lib #####

##### Local app #####
from .baseCommand import SimpleCommand

##### Theory app #####

##### Misc #####

class SwitchMood(SimpleCommand):
  """
  To switch Theory mood
  """
  name = "switchMood"
  verboseName = "switchMood"
  params = ["moodName",]
  _notations = ["Command",]
  _drums = {"Terminal": 1,}
  _moodName = ""

  @property
  def moodName(self):
    return self._moodName

  @moodName.setter
  def moodName(self, moodName):
    """
    :param moodName: The name of mood being used
    :type moodName: Choice(string)
    """
    self._moodName = moodName

  @property
  def moodNameChoiceLst(self):
    return settings.INSTALLED_MOODS

  def run(self, *args, **kwargs):
    config = loadMoodData(self.moodName)
    for i in dir(config):
      if(i==i.upper()):
        settings.MOOD[i] = getattr(config, i)

    reactor.mood = self.moodName

    self._stdOut += "Successfully switch to %s mood\n\nThe following config is applied:\n" % (self.moodName)
    for k,v in settings.MOOD.iteritems():
      self._stdOut += "    %s: %s\n" % (k, unicode(v))

