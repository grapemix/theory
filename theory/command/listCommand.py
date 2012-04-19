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
  _app = None
  _mood = None
  _query = None
  _notations = ["Command",]
  _gongs = ["Terminal", ]

  @property
  def query(self):
    return self._query

  @property
  def app(self):
    return self._app

  @app.setter
  def app(self, app):
    self._app = app

  @property
  def mood(self):
    return self._mood

  @mood.setter
  def mood(self, mood):
    self._mood = mood

  def run(self, *args, **kwargs):
    param = {}
    if(self._app!=None):
      param["app"] = self._app
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
