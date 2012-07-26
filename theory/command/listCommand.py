# -*- coding: utf-8 -*-
#!/usr/bin/env python
##### System wide lib #####

##### Theory lib #####
from theory.command.baseCommand import SimpleCommand
from theory.model import Command

##### Theory third-party lib #####

##### Local app #####

##### Theory app #####

##### Misc #####

class ListCommand(SimpleCommand):
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
    """
    :param query: The mongoengine QuerySet being pass to mongoengine
    :type query: QuerySet
    """
    return self._query

  @property
  def appName(self):
    return self._appName

  @appName.setter
  def appName(self, appName):
    """
    :param appName: The name of application being used
    :type appName: string
    """
    self._appName = appName

  @property
  def mood(self):
    return self._mood

  @mood.setter
  def mood(self, mood):
    """
    :param mood: The name of mood being used
    :type mood: string
    """
    self._mood = mood

  def run(self, *args, **kwargs):
    self._stdRowOut = []
    queryParam = {}
    if(self._appName!=None):
      queryParam["appName"] = self._appName
    if(self._mood!=None):
      queryParam["mood"] = self._mood
    self._query = Command.objects.all().select_related(1)
    if(queryParam!={}):
      self._query = self._query.filter(**queryParam)

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
      self._stdRowOut.append("%s(%s)" % (i.name, paramStr))
