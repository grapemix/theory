# -*- coding: utf-8 -*-
#!/usr/bin/env python
##### System wide lib #####
import gevent
import logging
import os
import signal

##### Theory lib #####
from theory.gui.common.rpcTerminalMixin import RpcTerminalMixin
from theory.gui.etk.element import getNewUiParam
from theory.conf import settings
from theory.utils.importlib import importClass
from theory.utils.singleton import Singleton

##### Theory third-party lib #####

##### Enlightenment lib #####
from efl import ecore
from efl import elementary
from efl.elementary.background import Background
from efl.elementary.box import Box
from efl.elementary.button import Button
from efl.elementary.entry import Entry
from efl.elementary.label import Label
from efl.elementary.layout import Layout
from efl.elementary.scroller import Scroller
from efl.elementary.separator import Separator
from efl.elementary.window import StandardWindow
from efl import evas

##### Local app #####

##### Theory app #####

##### Misc #####

__all__ = ("Terminal",)

class Terminal(RpcTerminalMixin, metaclass=Singleton):
  __metaclass__ = Singleton
  lb = None
  crlf = "<br/>"
  lastEntry = ""

  def _getFilterFormUi(self, isInNewWindow=False):
    if isInNewWindow:
      return getNewUiParam()
    else:
      return {
        "win": self.win,
        "bx": self.bxCrt,
        "unFocusFxn": self.unFocusFxn,
        "cleanUpCrtFxn": self.cleanUpCrt,
      }

  def _setCmdLineTxt(self, txt):
    self._cmdLineEntry.entry_set(txt)

  def unFocusFxn(self, entry, event, *args, **kwargs):
    if event.keyname == "Escape":
      self._cmdLineEntry.focus_set(True)

  # keep the *args. It might be called from toolkits which pass widget as param
  def cleanUpCrt(self, *args, **kwargs):
    """To reset to original form."""
    # Reactor call it a lot
    self.bxCrt.clear()
    self.win.resize(self.initCrtSize[0], self.initCrtSize[1])
    self._cmdLineEntry.focus_set(True)
    self.formHashInUse = None

  def _stdOutAdjuster(self, txt, crlf=None):
    if crlf is None:
      window = len(self.crlf)
      length = len(txt) - window
      counter = 0
      for i in range(length):
        if txt[i:i+window] == self.crlf:
          counter += 1
      height = counter * settings.UI_FONT_HEIGHT_RATIO + 130
    else:
      height = txt.count(crlf) * settings.UI_FONT_HEIGHT_RATIO + 130
    if height > self.maxHeight:
      height = self.maxHeight
    self.win.resize(self.initCrtSize[0], height)

  def _getDimensionHints(self):
    self.initCrtSize = (settings.DIMENSION_HINTS["minWidth"] * 3 / 4, 30)
    settings.initCrtSize = self.initCrtSize
    self.maxHeight = settings.DIMENSION_HINTS["maxHeight"]

  def __init__(self):
    self.logger = logging.getLogger(__name__)
    self.shouldIDie = False
    elementary.init()
    self.win = StandardWindow("theory", "Theory", autodel=True)
    self.win.autodel = True
    self.win.title_set("Theory")
    self.win.callback_delete_request_add(lambda x: elementary.exit())
    self.win.autodel_set(True)
    bg = Background(self.win)
    self.win.resize_object_add(bg)
    bg.size_hint_weight_set(evas.EVAS_HINT_EXPAND, evas.EVAS_HINT_EXPAND)
    bg.show()

    ly = Layout(self.win)
    #ly.file_set("gui/background.edj", "layout")
    ly.size_hint_weight_set(evas.EVAS_HINT_EXPAND, evas.EVAS_HINT_EXPAND)
    self.win.resize_object_add(ly)
    ly.show()

    self.bx = Box(self.win)
    self.win.resize_object_add(self.bx)
    self.bx.size_hint_weight_set(evas.EVAS_HINT_EXPAND, evas.EVAS_HINT_EXPAND)
    self.bx.show()
    self._drawShellInput()
    self._drawLabel("")

  def _switchToGeventLoop(self):
    gevent.sleep(0.1)
    ecore.timer_add(0.1, self._switchToGeventLoop)

  def _drawAll(self):
    self._switchToGeventLoop()
    self._getDimensionHints()
    self.cleanUpCrt()
    self.win.show()

    elementary.run()
    elementary.shutdown()

  def _shellInputChangeHooker(self, object, entry, *args, **kwargs):
    curEntryTxt = object.entry_get()
    if curEntryTxt == self.lastEntry or curEntryTxt == "":
      return
    elif curEntryTxt == "<tab/>":
      object.entry_set("")
    elif curEntryTxt.endswith("<tab/>"):
      self.lastEntry = curEntryTxt[:-6]
      object.entry_set(self.lastEntry)
      self._fireUiReq({
        "action": "autocompleteRequest",
        "val": self.lastEntry
      })
      object.cursor_line_end_set()
    elif curEntryTxt.endswith(self.crlf):
      self.lastEntry = curEntryTxt[:-5]
      object.entry_set("")
      self._runCmd(self.cmdFormCache[self.formHashInUse])

  def _cmdLineKeyDownHandler(self, entry, event, *args, **kwargs):
    # "Shift", "Control", "Alt", "Meta", "Hyper", "Super".
    if event.keyname == "Up":
      self._fireUiReq({"action": "showPreviousCmdRequest"})
    elif event.keyname == "Down":
      self._fireUiReq({"action": "showNextCmdRequest"})
    elif event.keyname == "Escape":
      self._fireUiReq({"action": "escapeRequest"})
    elif(
        event.modifier_is_set("Control")
        and event.modifier_is_set("Alt")
        and event.keyname == "q"
      ):
      self.dieTogether()
      self.shouldIDie = True
      elementary.exit()
      os.kill(os.getpid(), signal.SIGQUIT)

  def _drawShellInput(self):
    win = self.win
    bx = self.bx

    bx2 = Box(win)
    bx2.horizontal_set(True)
    bx2.size_hint_weight_set(evas.EVAS_HINT_EXPAND, 0.0)
    bx2.size_hint_align_set(evas.EVAS_HINT_FILL, evas.EVAS_HINT_FILL)

    en = Entry(win)
    en.line_wrap_set(True)
    en.entry_set("")
    en.scale_set(1.5)
    en.callback_changed_add(self._shellInputChangeHooker, en)
    # test mulitple key-binding
    en.on_key_down_add(self._cmdLineKeyDownHandler, en)
    en.size_hint_weight_set(evas.EVAS_HINT_EXPAND, evas.EVAS_HINT_EXPAND)
    en.size_hint_align_set(evas.EVAS_HINT_FILL, evas.EVAS_HINT_FILL)
    bx2.pack_end(en)
    en.show()
    en.focus_set(1)

    self._cmdLineEntry = en

    bt = Button(win)
    bt.text_set("Clear")
    bt.callback_clicked_add(self._clearShellInput)
    bt.size_hint_align_set(evas.EVAS_HINT_FILL, evas.EVAS_HINT_FILL)
    en.size_hint_weight_set(evas.EVAS_HINT_EXPAND, evas.EVAS_HINT_EXPAND)
    bx2.pack_end(bt)
    bt.show()

    bx.pack_end(bx2)
    bx2.show()

    en.focus_set(True)
    self.shellInput = en

  def _drawLabel(self, txt):
    box0 = self.bx

    sp = Separator(self.win)
    sp.horizontal_set(True)
    self.bx.pack_end(sp)
    sp.show()

    sc = Scroller(self.win)
    sc.bounce = (False, True)
    sc.policy = (
      elementary.scroller.ELM_SCROLLER_POLICY_OFF,
      elementary.scroller.ELM_SCROLLER_POLICY_AUTO
    )
    sc.size_hint_align = (evas.EVAS_HINT_FILL, evas.EVAS_HINT_FILL)
    sc.size_hint_weight = (evas.EVAS_HINT_EXPAND, evas.EVAS_HINT_EXPAND)
    self.bx.pack_end(sc)
    sc.show()

    self.bxCrt = Box(self.win)
    self.bxCrt.size_hint_weight_set(
      evas.EVAS_HINT_EXPAND,
      evas.EVAS_HINT_EXPAND
    )
    self.bxCrt.size_hint_align_set(evas.EVAS_HINT_FILL, evas.EVAS_HINT_FILL)
    self.lb = Label(self.win)
    self.lb.text_set(txt)
    self.lb.show()
    self.bxCrt.pack_end(self.lb)
    self.bxCrt.show()
    sc.content = self.bxCrt

  def _clearShellInput(self, *args, **kwargs):
    self.shellInput.entry_set("")
    self.lb.hide()

  def printStdOut(self, txt):
    # cannot use _clearShellInput instead of _drawShellInput, because form will
    # not be cleared
    self.bx.clear()
    self._drawShellInput()
    self._drawLabel(txt.replace("\n", "<br/>"))
    self._stdOutAdjuster(txt, "\n")

  def startAdapterUi(self, d):
    kls = importClass(d["importPath"])
    win = elementary.Window(
        d["importPath"].split(".")[-1],
        elementary.ELM_WIN_BASIC
        )
    win.title_set(d["importPath"].split(".")[-1])
    win.autodel_set(True)
    bx = elementary.Box(win)
    bx.size_hint_weight_set(evas.EVAS_HINT_EXPAND, evas.EVAS_HINT_EXPAND)
    bx.size_hint_align_set(evas.EVAS_HINT_FILL, evas.EVAS_HINT_FILL)
    win.resize_object_add(bx)
    bx.show()
    kls.render(d, {"win": win, "bx": bx}, self.callReactor)

  def restoreCmdLine(self, *args, **kwargs):
    self._cmdLineEntry.entry_set("")

  def setCmdLine(self, txt):
    self.lastEntry = txt
    self._setCmdLineTxt(txt)

  def setAndSelectCmdLine(self, txt):
    self.lastEntry = txt
    self._setCmdLineTxt(txt)
    if txt != "":
      self._cmdLineEntry.select_all()

  def selectCmdLine(self, start, end):
    self._cmdLineEntry.select_region_set(start, end)
