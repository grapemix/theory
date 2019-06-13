# -*- coding: utf-8 -*-
#!/usr/bin/env python
##### System wide lib #####
import os
from shutil import copytree

##### Theory lib #####
from theory.apps.command.baseCommand import SimpleCommand
from theory.conf import settings
from theory.gui import field

##### Theory third-party lib #####

##### Local app #####

##### Theory app #####

##### Misc #####

class CreateApp(SimpleCommand):
  """
  Start an Theory app
  """
  name = "createApp"
  verboseName = "createApp"
  _notations = ["Command",]
  _drums = {"Terminal": 1, }

  class ParamForm(SimpleCommand.ParamForm):
    appName = field.TextField(
        label="Application Name",
        helpText=" The name of application being created",
        maxLen=32
        )

  def run(self):
    fromPath = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        "conf", "app_template")
    toPath = os.path.join(settings.APPS_ROOT, self.paramForm.clean()["appName"])
    self._stdOut += "Coping" + fromPath + " --> " + toPath + "<br/>"
    try:
      copytree(fromPath, toPath)
      self._stdOut += \
          "Don't forget to add the app name into the INSTALLED_APP within "\
          "your project's setting. To make your app recognized by theory, you "\
          "will also need to restart theory or run the probeModule command"
    except OSError as e:
      self._stdOut += str(e)
