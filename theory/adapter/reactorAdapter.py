# -*- coding: utf-8 -*-
#!/usr/bin/env python
##### System wide lib #####

##### Theory lib #####

##### Theory third-party lib #####

##### Local app #####

##### Theory app #####

##### Misc #####

# To avoid being auto-probe, never derive from baseAdapter
class ReactorAdapter(object):
  """
  This class is a special adapter for internal theory usage only. No external
  app should call or derive anything from it.
  """
  lastEntry = ""
  crlf = ""

  def printTxt(self, *args, **kwargs):
    pass

  def __init__(self, signal):
    self.signal = signal

  @property
  def cmdInTxt(self):
    return self._cmdInTxt

  @cmdInTxt.setter
  def cmdInTxt(self, cmdInTxt):
    self._cmdInTxt = cmdInTxt

  def signalCmdInputSubmit(self, *args, **kwargs):
    if(self.signal.has_key("cmdSubmit")):
      self.signal["cmdSubmit"](*args, **kwargs)

  def signalCmdInputChange(self, *args, **kwargs):
    if(self.signal.has_key("cmdChange")):
      self.signal["cmdChange"](*args, **kwargs)

  def autocompleteRequest(self, entrySetterFxn, *args, **kwargs):
    if(self.signal.has_key("autocompleteRequest")):
      self.signal["autocompleteRequest"](entrySetterFxn, *args, **kwargs)
