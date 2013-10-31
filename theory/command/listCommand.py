# -*- coding: utf-8 -*-
#!/usr/bin/env python
##### System wide lib #####

##### Theory lib #####
from theory.command.baseCommand import SimpleCommand
from theory.conf import settings
from theory.gui import field
from theory.model import Command

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
        help_text="Commands provided by this application",
        choices=(
          set(
            [("all", "all")] + \
            [(app, app) for app in settings.INSTALLED_APPS]
          )
        ),
        initData="all",
        required=False
    )
    mood = field.ChoiceField(
        label="Mood",
        help_text="Commands provided by this mood",
        choices=(
          set(
            [("all", "all")] + \
            [(mood, mood) for mood in settings.INSTALLED_MOODS]
          )
        ),
        initData="all",
        required=False
    )

  @property
  def query(self):
    """
    :param query: The mongoengine QuerySet being pass to mongoengine
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

    if(formData["appName"]!="all"):
      queryParam["app"] = formData["appName"]
    if(formData["mood"]!="all"):
      queryParam["mood"] = formData["mood"]

    self._query = Command.objects.all()
    if(queryParam!={}):
      self._query = self._query.filter(**queryParam)
    self._query = self._query.select_related(1)

    for i in self._query:
      paramStr = ""
      hasOptional = False
      paramLst = i.param
      paramLst.sort(key=lambda x:x.isOptional)
      for j in paramLst:
        if(not hasOptional and j.isOptional==True):
          paramStr += "["
          hasOptional = True
        paramStr += "%s %s," % (j.type, j.name)
      paramStr = paramStr[:-1]
      if(hasOptional):
        paramStr += "]"
      self._stdOut += "%s(%s)\n" % (i.name, paramStr)
