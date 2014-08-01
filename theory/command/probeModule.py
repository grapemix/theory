# -*- coding: utf-8 -*-
#!/usr/bin/env python
##### System wide lib #####

##### Theory lib #####
from theory.command.baseCommand import SimpleCommand
from theory.core.loader.util import reprobeAllModule
from theory.gui import field

##### Theory third-party lib #####

##### Local app #####

##### Theory app #####

##### Misc #####

class ProbeModule(SimpleCommand):
  name = "probeModule"
  verboseName = "probeModule"

  class ParamForm(SimpleCommand.ParamForm):
    settingMod = field.TextField(
        label="Setting Module",
        helpText=(
          "The python module being used to setup environment \n",
          "during probing"
          ),
        maxLength=64
        )

  def run(self):
    self._stdOut = "Probing module: %s" %  (self._settingMod,)
    reprobeAllModule(self.paramForm.clean()["settingMod"])
