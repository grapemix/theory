# -*- coding: utf-8 -*-
#!/usr/bin/env python
##### System wide lib #####
from copy import deepcopy

##### Theory lib #####
from theory.conf import settings
from theory.utils.mood import loadMoodData

##### Theory third-party lib #####
from theory.gui.etk.terminal import Terminal

##### Local app #####

##### Theory app #####

##### Misc #####

def getDimensionHints():
  resolutionSet = settings.MOOD["RESOLUTION"]
  maxHeight = maxWidth = 0
  minHeight = minWidth = 99999999

  for resolution in resolutionSet:
    width, height = resolution
    width = int(width)
    height = int(height)
    if minWidth > width:
      minWidth = width
    if minHeight > height:
      minHeight = height
    if maxWidth < width:
      maxWidth = width
    if maxHeight < height:
      maxHeight = height
  settings.DIMENSION_HINTS = {
      "minWidth": minWidth,
      "minHeight":minHeight,
      "maxWidth": maxWidth,
      "maxHeight": maxHeight,
      }

def wakeup(settings_mod, argv=None):
  # TODO: Make reactor to generate all choices for all fields to rm all deps
  from theory.apps import apps
  from copy import deepcopy
  appNameLst = deepcopy(settings.INSTALLED_APPS)
  appNameLst.insert(0, "theory.apps")
  apps.populate(appNameLst)

  loadMoodData()

  getDimensionHints()
  Terminal().start()
