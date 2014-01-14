# -*- coding: utf-8 -*-
#!/usr/bin/env python
##### System wide lib #####

##### Theory lib #####
from theory.conf import settings
from theory.utils.importlib import importModule

##### Theory third-party lib #####

##### Local app #####

##### Theory app #####

##### Misc #####

def loadMoodData(mood=None):

  def _assignPropertyIntoSettings(config):
    for i in dir(config):
      if(i==i.upper()):
        settings.MOOD[i] = getattr(config, i)

  config = importModule("norm.config")
  _assignPropertyIntoSettings(config)

  try:
    if(not mood):
      mood = settings.DEFAULT_MOOD
    config = importModule("%s.config" % (mood))
  except (AttributeError, EnvironmentError, ImportError, KeyError):
    config = None

  _assignPropertyIntoSettings(config)

  return config


