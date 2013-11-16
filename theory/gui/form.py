# -*- coding: utf-8 -*-
#!/usr/bin/env python
##### System wide lib #####

##### Theory lib #####
from theory.conf import settings
from theory.utils.importlib import import_module

##### Theory third-party lib #####

##### Local app #####

##### Theory app #####

##### Misc #####

# 1) Developer should import this class instead of specific tookkit's field
# 2) Try your best to use 'from theory.gui import field' instead of
#    'from theory.gui.field import *' to avoid the name collision
#    between field and mongoenigne.

def _importModule():
  supportModuleLst = ("Form", "SimpleGuiForm", "FlexibleGuiForm", "CommandForm",)

  module = import_module("theory.gui.{0}.form".format(settings.UI_TOOLKIT))

  for field in supportModuleLst:
    if(hasattr(module, field)):
        globals()[field] = getattr(module, field)

_importModule()
