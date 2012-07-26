# -*- coding: utf-8 -*-
#!/usr/bin/env python
##### System wide lib #####

##### Theory lib #####
from theory.command.baseCommand import SimpleCommand
from theory.core.loader.util import reprobeAllModule

##### Theory third-party lib #####

##### Local app #####

##### Theory app #####

##### Misc #####

class ProbeModule(SimpleCommand):
  name = "probeModule"
  verboseName = "probeModule"
  params = []
  _settingMod = None

  @property
  def settingMod(self):
    return self._settingMod

  @settingMod.setter
  def settingMod(self, settingMod):
    """
    :param settingMod: The python module being used to setup environment during probing
    :type settingMod: pythonModule
    """
    self._settingMod = settingMod

  def run(self, *args, **kwargs):
    print self._settingMod
    reprobeAllModule(self._settingMod)
