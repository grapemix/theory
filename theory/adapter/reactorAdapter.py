# -*- coding: utf-8 -*-
#!/usr/bin/env python
##### System wide lib #####

##### Theory lib #####
from theory.gui import field
from theory.gui.form import SimpleGuiForm

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
  entrySetterFxn = None

  class TerminalForm(SimpleGuiForm):
    stdOut = field.TextField(label="Standard Output")

  def printTxt(self, txt):
    o = self.TerminalForm()
    o.fields["stdOut"].initData = txt
    o.generateForm(**self.uiParam)
    self.terminalForm = o

  def __init__(self, signal):
    self.signal = signal

  def registerEntrySetterFxn(self, entrySetterFxn):
    self.entrySetterFxn = entrySetterFxn

  def registerCleanUpCrtFxn(self, cleanUpCrtFxn):
    self.cleanUpCrt = cleanUpCrtFxn

  def restoreCmdLine(self):
    self.entrySetterFxn(self.cmdInTxt)
    self.cmdInTxt = ""

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

  def signalCmdInputSubmit(self):
    if(self.signal.has_key("cmdSubmit")):
      self.signal["cmdSubmit"]()

  def signalCmdInputChange(self):
    if(self.signal.has_key("cmdChange")):
      self.signal["cmdChange"]()

  def autocompleteRequest(self):
    if(self.signal.has_key("autocompleteRequest")):
      self.signal["autocompleteRequest"](self.entrySetterFxn)

  def showPreviousCmdRequest(self):
    if(self.signal.has_key("showPreviousCmdRequest")):
      self.signal["showPreviousCmdRequest"](self.entrySetterFxn)

  def showNextCmdRequest(self):
    if(self.signal.has_key("showNextCmdRequest")):
      self.signal["showNextCmdRequest"](self.entrySetterFxn)

  def escapeRequest(self):
    if(self.signal.has_key("escapeRequest")):
      self.signal["escapeRequest"](self.entrySetterFxn)
