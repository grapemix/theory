# -*- coding: utf-8 -*-
#!/usr/bin/env python
##### System wide lib #####
import os
from shutil import copy

##### Theory lib #####
from theory.command.baseCommand import SimpleCommand
from theory.conf import settings
from theory.gui import field

##### Theory third-party lib #####

##### Local app #####

##### Theory app #####

##### Misc #####

class CreateCmd(SimpleCommand):
  name = "createCmd"
  verboseName = "createCmd"
  _notations = ["Command",]
  _drums = {"Terminal": 1, }

  class ParamForm(SimpleCommand.ParamForm):
    appName = field.ChoiceField(label="Application Name", \
        help_text="The name of application being used", \
        choices=(set([(len(settings.INSTALLED_APPS)+1, "theory")] + [(i, settings.INSTALLED_APPS[i]) for i in range(len(settings.INSTALLED_APPS))])))
    cmdName = field.TextField(label="Command Name", \
        help_text=" The name of command being created", max_length=32)

  def run(self):
    appName = self.paramForm.fields["appName"].finalChoiceLabel
    cmdName = self.paramForm.clean()["cmdName"]
    if(appName!="theory"):
      foundApp = False
      for i in settings.INSTALLED_APPS:
        if(i==appName):
          foundApp = True
      if(not foundApp):
        self._stdOut = "You must create the app AND put it into INSTALLED_APPS first!"
        return
      toPath = os.path.join(settings.APPS_ROOT, appName, "command", cmdName + ".py")
    else:
      toPath = os.path.join(os.path.dirname(__file__), cmdName + ".py")

    fromPath = os.path.join(os.path.dirname(os.path.dirname(__file__)),
        "conf", "app_template", "command", "__init__.py")
    self._stdOut += "Coping %s --> %s\n" % (fromPath, toPath)
    copy(fromPath, toPath)
