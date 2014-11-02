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

  class ParamForm(SimpleCommand.ParamForm):
    appNameLst = field.MultipleChoiceField(
        label="Application Name",
        helpText="The name of application being probed",
        choices=(
          set(
            [("theory.apps", "theory.apps")] + \
            [(app, app) for app in settings.INSTALLED_APPS]
          )
        )
    )

  def run(self):
    appNameLst = self.paramForm.clean()["appNameLst"]

    self._stdOut = "Probing module: %s" % (appNameLst)
    #reprobeAllModule(settingMod)
    probeApps(appNameLst)
