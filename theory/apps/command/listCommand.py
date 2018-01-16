# -*- coding: utf-8 -*-
#!/usr/bin/env python
##### System wide lib #####

##### Theory lib #####
from theory.apps.command.baseCommand import SimpleCommand
from theory.apps.model import Command
from theory.conf import settings
from theory.gui import field

##### Theory third-party lib #####

##### Local app #####

##### Theory app #####

##### Misc #####

class ListCommand(SimpleCommand):
  name = "listCommand"
  verboseName = "listCommand"
  _appName = None
  _mood = None
  _query = None
  _notations = ["Command",]
  _gongs = ["StdPipe", ]
  _drums = {"Terminal": 1,}

  class ParamForm(SimpleCommand.ParamForm):
    appName = field.ChoiceField(
        label="Application Name",
        helpText="Commands provided by this application",
        dynamicChoiceLst=(
          set(
            [("all", "all")] + \
            [(appName, appName) for appName in settings.INSTALLED_APPS]
          )
        ),
        initData="all",
        required=False
    )
    mood = field.ChoiceField(
        label="Mood",
        helpText="Commands provided by this mood",
        dynamicChoiceLst=(
          set(
            [("all", "all")] + \
            [(moodName, moodName) for moodName in settings.INSTALLED_MOODS]
          )
        ),
        initData="all",
        required=False
    )

  @property
  def query(self):
    """
    :param query: The QuerySet being pass to theory orm
    :type query: QuerySet
    """
    return self._query

  @property
  def stdOut(self):
    return self._stdOut

  def run(self):
    self._stdOut = ""
    queryParam = {}
    formData = self.paramForm.clean()

    if formData["appName"] != "all":
      queryParam["app"] = formData["appName"]
    if formData["mood"] != "all":
      queryParam["moodSet__name"] = formData["mood"]

    self._query = Command.objects.all()
    if queryParam != {}:
      self._query = self._query.filter(**queryParam)

    for i in self._query:
      paramStr = ""
      hasOptional = False
      paramLst = i.cmdFieldSet.all().orderBy("isOptional")
      for j in paramLst:
        if not hasOptional and j.isOptional == True:
          paramStr += "["
          hasOptional = True
        paramStr += "%s %s," % (j.type, j.name)
      paramStr = paramStr[:-1]
      if hasOptional:
        paramStr += "]"
      self._stdOut += "%s(%s)\n" % (i.name, paramStr)
