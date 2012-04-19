# -*- coding: utf-8 -*-
#!/usr/bin/env python
##### System wide lib #####
from abc import ABCMeta, abstractmethod

##### Theory lib #####

##### Theory third-party lib #####

##### Local app #####

##### Theory app #####

##### Misc #####

class BaseScanManager(object):
  __metaclass__ = ABCMeta
  _paramList = []

  @property
  def paramList(self):
    return self._paramList

  @paramList.setter
  def paramList(self, paramList):
    self._paramList = paramList

  @abstractmethod
  def scan(self, *args, **kwargs):
    pass
