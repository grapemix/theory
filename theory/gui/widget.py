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

# 1) Developer should import this class instead of specific tookkit's field
# 2) Try your best to use 'from theory.gui import widget' instead of
#    'from theory.gui.field import *' to avoid the name collision
#    between field and mongoenigne.

def _importModule():
  module = importModule("theory.gui.{0}.widget".format(settings.UI_TOOLKIT))
  widgetNameLst = [i for i in dir(module) if i.endswith("Input")]

  for widgetName in widgetNameLst:
    globals()[widgetName] = getattr(module, widgetName)

_importModule()
