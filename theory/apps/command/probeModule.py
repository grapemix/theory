# -*- coding: utf-8 -*-
#!/usr/bin/env python
##### System wide lib #####

##### Theory lib #####
from theory.apps.command.baseCommand import SimpleCommand
from theory.conf import settings
from theory.core.loader.util import probeApps
from theory.gui import field

##### Theory third-party lib #####

##### Local app #####

##### Theory app #####

##### Misc #####

class ProbeModule(SimpleCommand):
  name = "probeModule"
  verboseName = "probeModule"
  _drums = {"Terminal": 1,}

  @property
  def stdOut(self):
    return self._stdOut

  class ParamForm(SimpleCommand.ParamForm):
    appNameLst = field.MultipleChoiceField(
        label="Application Name",
        helpText="The name of application being probed",
        dynamicChoiceLst=[("theory.apps", "theory.apps")] +
          [(appName, appName) for appName in settings.INSTALLED_APPS],
    )

  def run(self):
    appNameLst = self.paramForm.clean()["appNameLst"]

    self._stdOut = "Probing module: %s\n" % (appNameLst)
    #reprobeAllModule(settingMod)

    probeApps(appNameLst)
    self._stdOut += "done"
