# -*- coding: utf-8 -*-
#!/usr/bin/env python
##### System wide lib #####
import os

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
    appName = field.ChoiceField(label="Application Name",
        help_text="The name of application being used",
        choices=(
          set(
            [("theory", "theory")] + \
            [(app, app) for app in settings.INSTALLED_APPS]
          )
        )
    )
    cmdName = field.TextField(
        label="Command Name",
        help_text=" The name of command being created",
        max_length=32
    )
    cmdType = field.ChoiceField(label="Command Type",
        help_text="The name of application being used",
        initData="SimpleCommand",
        choices=(
          set((
            ("SimpleCommand", "SimpleCommand"),
            ("AsyncCommand", "AsyncCommand"),
          ))
        )
    )
    propertyNameLst = field.ListField(field.TextField(max_length=96),
        label="Property Name List",
        help_text=" The name list of property being created",
        required=False,
    )

  _propertyTemplate = '''
  @property
  def {cmdProperty}(self):
    return self._{cmdProperty}

  @{cmdProperty}.setter
  def {cmdProperty}(self, {cmdProperty}):
    """
    :param {cmdProperty}: {cmdProperty} comment
    :type {cmdProperty}: {cmdProperty} type
    """
    self._{cmdProperty} = {cmdProperty}
  '''

  def getPropertyLst(self, propertLst):
    if(len(propertLst)==0):
      return ""
    else:
      r = ""
      for property in propertLst:
        r += self._propertyTemplate.format(cmdProperty=property)
      return r

  def run(self):
    data = self.paramForm.clean()
    appName = data["appName"]
    cmdName = data["cmdName"]
    if(appName!="theory"):
      toPath = os.path.join(
          settings.APPS_ROOT,
          appName,
          "command",
          cmdName + ".py"
      )
    else:
      toPath = os.path.join(os.path.dirname(__file__), cmdName + ".py")

    fromPath = os.path.join(os.path.dirname(os.path.dirname(__file__)),
        "conf", "command.tmpl")
    self._stdOut += "Coping %s --> %s\n" % (fromPath, toPath)

    propertyLst = self.getPropertyLst(data["propertyNameLst"])

    CmdName=cmdName[0].upper() + cmdName[1:]
    if(data["cmdType"]=="AsyncCommand"):
      extraCode = "super({0}, self).run(*args, **kwargs)".format(CmdName)
    else:
      extraCode = "pass"

    with open(fromPath) as tmplFile:
      tmpl = tmplFile.read().format(
          propertLst=propertyLst,
          cmdType=data["cmdType"],
          cmdName=cmdName,
          CmdName=CmdName,
          extraCode=extraCode,
          )
      with open(toPath, 'w') as fd:
        fd.write(tmpl)
