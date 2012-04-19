# -*- coding: utf-8 -*-
#!/usr/bin/env python
##### System wide lib #####

##### Theory lib #####
from theory.command.baseCommand import BaseCommand
from theory.core.loader import reprobeAllModule

##### Theory third-party lib #####

##### Local app #####

##### Theory app #####

##### Misc #####

class ProbeModule(BaseCommand):
  name = "probeModule"
  verboseName = "probeModule"
  params = []
  _settingMod = None

  @property
  def settingMod(self):
    return self._settingMod

  @settingMod.setter
  def settingMod(self, settingMod):
    self._settingMod = settingMod

  def run(self, *args, **kwargs):
    print self._settingMod
    reprobeAllModule(self._settingMod)
