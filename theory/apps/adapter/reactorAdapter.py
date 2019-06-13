# -*- coding: utf-8 -*-
#!/usr/bin/env python
##### System wide lib #####

##### Theory lib #####
from theory.gui import field as FormField
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
    stdOut = FormField.TextField(label="Standard Output")

  def printTxt(self, txt):
    o = self.TerminalForm()
    o.fields["stdOut"].initData = txt
    o.generateForm(**self.uiParam)
    self.terminalForm = o
    self.stdOutAdjuster(txt)

  def __init__(self, signal):
    self.signal = signal

  def registerEntrySetterFxn(self, entrySetterFxn):
    self.entrySetterFxn = entrySetterFxn

  def registerEntrySetAndSelectFxn(self, entrySetterFxn):
    self.entrySetAndSelectFxn = entrySetterFxn

  def registerCleanUpCrtFxn(self, cleanUpCrtFxn):
    self.cleanUpCrt = cleanUpCrtFxn


  def registerStdOutAdjusterFxn(self, stdOutAdjusterFxn):
    self.stdOutAdjuster = stdOutAdjusterFxn

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
    if "cmdSubmit" in self.signal:
      self.signal["cmdSubmit"]()

  def signalCmdInputChange(self):
    if "cmdChange" in self.signal:
      self.signal["cmdChange"]()

  def autocompleteRequest(self):
    if "autocompleteRequest" in self.signal:
      self.signal["autocompleteRequest"](self.entrySetterFxn)

  def showPreviousCmdRequest(self):
    if "showPreviousCmdRequest" in self.signal:
      self.signal["showPreviousCmdRequest"](self.entrySetterFxn)

  def showNextCmdRequest(self):
    if "showNextCmdRequest" in self.signal:
      self.signal["showNextCmdRequest"](self.entrySetterFxn)

  def escapeRequest(self):
    if "escapeRequest" in self.signal:
      self.signal["escapeRequest"](self.entrySetterFxn)
