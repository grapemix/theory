# -*- coding: utf-8 -*-
#!/usr/bin/env python
##### System wide lib #####
import os
from shutil import copy

##### Theory lib #####
from theory.command.baseCommand import BaseCommand
from theory.conf import settings

##### Theory third-party lib #####

##### Local app #####

##### Theory app #####

##### Misc #####

class CreateCmd(BaseCommand):
  name = "createCmd"
  verboseName = "createCmd"
  params = ["appName", "cmdName"]
  _appName = ""
  _cmdName = ""
  _notations = ["Command",]
  _gongs = ["Terminal", ]


  @property
  def appName(self):
    return self._appName

  @appName.setter
  def appName(self, appName):
    self._appName = appName

  @property
  def cmdName(self):
    return self._cmdName

  @cmdName.setter
  def cmdName(self, cmdName):
    self._cmdName = cmdName

  def run(self, *args, **kwargs):
    if(self.appName!="theory"):
      foundApp = False
      for i in settings.INSTALLED_APPS:
        if(i==self.appName):
          foundApp = True
      if(not foundApp):
        self._stdOut = "You must create the app AND put it into INSTALLED_APPS first!"
        return
      toPath = os.path.join(settings.APPS_ROOT, self.appName, "command", self.cmdName + ".py")
    else:
      toPath = os.path.dirname(__file__)

    fromPath = os.path.join(os.path.dirname(os.path.dirname(__file__)),
        "conf", "app_template", "command", "__init__.py")
    self._stdOut += "Coping" + fromPath + " --> " + toPath + "<br/>"
    copy(fromPath, toPath)
    self._stdOut += \
        "Don't forget to add the app name into the INSTALLED_APPS within "\
        "your project's setting. To make your app recognized by theory, you "\
        "will also need to restart theory or run the probeModule command"
