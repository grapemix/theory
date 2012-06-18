# -*- coding: utf-8 -*-
#!/usr/bin/env python
##### System wide lib #####

##### Theory lib #####
from theory.command.baseCommand import BaseCommand
from theory.model import Command

##### Theory third-party lib #####

##### Local app #####

##### Theory app #####

##### Misc #####

class ListCommand(BaseCommand):
  name = "listCommand"
  verboseName = "listCommand"
  params = []
  _appName = None
  _mood = None
  _query = None
  _notations = ["Command",]
  _gongs = ["Terminal", ]

  @property
  def query(self):
    return self._query

  @property
  def appName(self):
    return self._appName

  @appName.setter
  def appName(self, appName):
    self._appName = appName

  @property
  def mood(self):
    return self._mood

  @mood.setter
  def mood(self, mood):
    self._mood = mood

  def run(self, *args, **kwargs):
    self._stdRowOut = []
    param = {}
    if(self._appName!=None):
      param["appName"] = self._appName
    if(self._mood!=None):
      param["mood"] = self._mood
    self._query = Command.objects.all().select_related(1)
    if(param!={}):
      self._query = self._query.filter(**param)

    for i in self._query:
      param = ""
      hasOptional = False
      for j in i.param:
        if(not hasOptional and j.isOptional==True):
          param += "["
          hasOptional = True
        param += j.name + ","
      param = param[:-1]
      if(hasOptional):
        param += "]"
      self._stdRowOut.append("%s(%s)" % (i.name, param))
