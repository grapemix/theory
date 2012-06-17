# -*- coding: utf-8 -*-
#!/usr/bin/env python
##### System wide lib #####
import os
from shutil import copytree

##### Theory lib #####
from theory.command.baseCommand import BaseCommand
from theory.conf import settings

##### Theory third-party lib #####

##### Local app #####

##### Theory app #####

##### Misc #####

class CreateApp(BaseCommand):
  """
  Start an Theory app
  """
  name = "createApp"
  verboseName = "createApp"
  params = ["appName",]
  _notations = ["Command",]
  _gongs = ["Terminal", ]

  @property
  def appName(self):
    return self._appName

  @appName.setter
  def appName(self, appName):
    self._appName = appName

  def run(self, *args, **kwargs):
    fromPath = os.path.join(os.path.dirappName(os.path.dirappName(__file__)),
        "conf", "app_template")
    toPath = os.path.join(settings.APPS_ROOT, self.appName)
    self._stdOut += "Coping" + fromPath + " --> " + toPath + "<br/>"
    try:
      copytree(fromPath, toPath)
      self._stdOut += \
          "Don't forget to add the app name into the INSTALLED_APP within "\
          "your project's setting. To make your app recognized by theory, you "\
          "will also need to restart theory or run the probeModule command"
    except (OSError,), e:
      self._stdOut += str(e)



