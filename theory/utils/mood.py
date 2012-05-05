# -*- coding: utf-8 -*-
#!/usr/bin/env python
##### System wide lib #####

##### Theory lib #####
from theory.utils.importlib import import_module

##### Theory third-party lib #####

##### Local app #####

##### Theory app #####

##### Misc #####

def loadMoodData(mood=None):
  try:
    from theory.conf import settings
    if(not mood):
      mood = settings.DEFAULT_MOOD
    config = import_module("%s.config" % (mood))
  except (AttributeError, EnvironmentError, ImportError, KeyError):
    config = None
  for i in dir(config):
    if(i==i.upper()):
      settings.MOOD[i] = getattr(config, i)
  return config


