# -*- coding: utf-8 -*-
#!/usr/bin/env python
##### System wide lib #####

##### Theory lib #####


##### Theory third-party lib #####

##### Local app #####
from . import BaseUIAdapter

##### Theory app #####

##### Misc #####

__all__ = ("TerminalAdapter",)

class TerminalAdapter(BaseUIAdapter):
  _stdOut = ""
  _stdErr = ""

  @property
  def stdOut(self):
    return self._stdOut

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
  def stdErr(self):
    return self._stdErr

  @stdErr.setter
  def stdErr(self, stdErr):
    self._stdErr = stdErr

  def render(self, *args, **kwargs):
    return [{
        "action": "printStdOut",
        "val": self.stdOut + "\n"
        }]
