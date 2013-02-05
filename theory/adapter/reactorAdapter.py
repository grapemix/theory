# -*- coding: utf-8 -*-
#!/usr/bin/env python
##### System wide lib #####

##### Theory lib #####
from theory.gui import field
from theory.gui.form import GuiForm

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

  class TerminalForm(GuiForm):
    stdOut = field.TextField(label="Standard Output")

  def printTxt(self, txt):
    win = self.uiParam["win"]
    bx = self.uiParam["bx"]

    o = self.TerminalForm()
    o.fields["stdOut"].initData = txt
    o.generateForm(win, bx)
    self.terminalForm = o

  def __init__(self, signal):
    self.signal = signal

  def cleanUpCrt(self):
    bx = self.uiParam["bx"]
    bx.clear()

  @property
  def cmdInTxt(self):
    return self._cmdInTxt

  @cmdInTxt.setter
  def cmdInTxt(self, cmdInTxt):
    self._cmdInTxt = cmdInTxt

  @property
  def uiParam(self):
    return self._uiParam

  @uiParam.setter
  def uiParam(self, uiParam):
    """
    :param uiParam: The dictionary parameter which will pass from the main gui
                    window to command everytime.
    :type uiParam: dictionary
    """
    self._uiParam = uiParam

  def signalCmdInputSubmit(self, *args, **kwargs):
    if(self.signal.has_key("cmdSubmit")):
      self.signal["cmdSubmit"](*args, **kwargs)

  def signalCmdInputChange(self, *args, **kwargs):
    if(self.signal.has_key("cmdChange")):
      self.signal["cmdChange"](*args, **kwargs)

  def autocompleteRequest(self, entrySetterFxn, *args, **kwargs):
    if(self.signal.has_key("autocompleteRequest")):
      self.signal["autocompleteRequest"](entrySetterFxn, *args, **kwargs)
