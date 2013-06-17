# -*- coding: utf-8 -*-
#!/usr/bin/env python
##### System wide lib #####
from abc import ABCMeta, abstractmethod
import re

##### Theory lib #####
from theory.core.exceptions import CommandSyntaxError
from theory.model import Command
from theory.utils.importlib import import_module

##### Theory third-party lib #####

##### Local app #####
from . import BaseAdapter

##### Theory app #####

##### Misc #####

class StdPipeAdapter(BaseAdapter):
  _stdOut = ""
  _stdErr = ""
  _stdIn = ""

  @property
  def stdOut(self):
    return self._stdOut

  @stdOut.setter
  def stdOut(self, stdOut):
    self._stdOut = stdOut

  @property
  def stdErr(self):
    return self._stdErr

  @stdErr.setter
  def stdErr(self, stdErr):
    self._stdErr = stdErr

  @property
  def stdIn(self):
    return self._stdIn

  @stdIn.setter
  def stdIn(self, stdIn):
    self._stdIn = stdIn

  def toDb(self):
    self.stdIn = self.stdOut
    self.stdIn += self.stdErr
    return True
