# -*- coding: utf-8 -*-
#!/usr/bin/env python
##### System wide lib #####
import re

##### Theory lib #####
from theory.model import Command
from theory.core.exceptions import CommandSyntaxError
from theory.gui.terminal import Terminal
from theory.utils.importlib import import_module

##### Theory third-party lib #####

##### Local app #####
from . import BaseAdapter

##### Theory app #####

##### Misc #####

class TerminalAdapter(BaseAdapter):
  _stdOut = ""
  _stdRowOut = []
  _stdOutLineBreak = "<br/>"
  isDisplayWidgetCompatable = True

  @property
  def stdOut(self):
    self.preStdOutPacker()
    r = self.stdOutPacker()
    return self.postStdOutPacker(r)

  def preStdOutPacker(self):
    if(self._stdOut=="" and self._stdRowOut!=[]):
      self._stdOut = self._stdOutLineBreak.join(self._stdRowOut)

  def stdOutPacker(self):
    return self._stdOut

  def postStdOutPacker(self, r):
    return r

  @stdOut.setter
  def stdOut(self, stdOut):
    self._stdOut = stdOut

  @property
  def stdRowOut(self):
    self.preStdRowOutPacker()
    r = self.stdRowOutPacker()
    return self.postStdRowOutPacker(r)

  def preStdRowOutPacker(self):
    if(self._stdRowOut==[] and self._stdOut!=""):
      self._stdRowOut = self._stdOut.split(self._stdOutLineBreak)

  def stdRowOutPacker(self):
    return self._stdRowOut

  def postStdRowOutPacker(self, r):
    return r

  @stdRowOut.setter
  def stdRowOut(self, stdRowOut):
    self._stdRowOut = stdRowOut


