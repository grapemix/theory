# -*- coding: utf-8 -*-
#!/usr/bin/env python
##### System wide lib #####
from collections import OrderedDict
import gevent
import os
import signal

##### Theory lib #####
from theory.conf import settings

##### Theory third-party lib #####

##### Enlightenment lib #####
from efl import ecore
from efl import edje
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

# TODO: MUST rewrite this file!
#----- common -{{{-
def my_entry_bt_2(bt, en):
  str = en.entry_get()
  print "ENTRY: %s" % str

def my_entry_bt_3(bt, en):
  str = en.selection_get()
  print "SELECTION: %s" % str

def my_entry_bt_4(bt, en):
  en.entry_insert("Insert some <b>BOLD</> text")

def my_entry_anchor_test(obj, en, *args, **kwargs):
  en.entry_insert("ANCHOR CLICKED")
# -}}}-

class Terminal(object):
  lb = None
  crlf = "<br/>"

  @property
  def adapter(self):
    return self._adapter

  @adapter.setter
  def adapter(self, adapter):
    self._adapter = adapter
    #self._adapter.printTxt = lambda x: self.lb.text_set(x)
    self._adapter.crlf = self.crlf
    self._adapter.uiParam = OrderedDict([
        ("win", self.win),
        ("bx", self.bxCrt),
        ("unFocusFxn", self.unFocusFxn),
        ("cleanUpCrtFxn", self.cleanUpCrt),
    ])
    self._adapter.registerEntrySetterFxn(self._cmdLineEntry.entry_set)
    self._adapter.registerEntrySetAndSelectFxn(self.cmdLineSetter)
    self._adapter.registerCleanUpCrtFxn(self.cleanUpCrt)
    self._adapter.registerStdOutAdjusterFxn(self.stdOutAdjuster)

  def cmdLineSetter(self, txt):
    self._cmdLineEntry.entry_set(txt)
    if(txt!=""):
      self._cmdLineEntry.select_all()

  def unFocusFxn(self, entry, event, *args, **kwargs):
    if(event.keyname=="Escape"):
      self._cmdLineEntry.focus_set(True)

  # keep the *args. It might be called from toolkits which pass widget as param
  def cleanUpCrt(self, *args, **kwargs):
    """To reset to original form."""
    self.bxCrt.clear()
    self.win.resize(self.initCrtSize[0], self.initCrtSize[1])
    self._cmdLineEntry.focus_set(True)

  def stdOutAdjuster(self, txt, crlf=None):
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
    ly.file_set("gui/background.edj", "layout")
    ly.size_hint_weight_set(evas.EVAS_HINT_EXPAND, evas.EVAS_HINT_EXPAND)
    self.win.resize_object_add(ly)
    ly.show()

    self.bx = Box(self.win)
    self.win.resize_object_add(self.bx)
    self.bx.size_hint_weight_set(evas.EVAS_HINT_EXPAND, evas.EVAS_HINT_EXPAND)
    self.bx.show()
    self.drawShellInput()
    self.drawLabel("")

  def _switchToGeventLoop(self):
    gevent.sleep(0)
    ecore.timer_add(1, self._switchToGeventLoop)

  def drawAll(self):
    self._switchToGeventLoop()
    self._getDimensionHints()
    self.cleanUpCrt()
    self.win.show()

    elementary.run()
    elementary.shutdown()
    return True

  def _shellInputChangeHooker(self, object, entry, *args, **kwargs):
    curEntryTxt = object.entry_get()
    #print ".", curEntryTxt, "."
    if(curEntryTxt==self.adapter.lastEntry or curEntryTxt==""):
      return
    if(curEntryTxt.endswith("<tab/>")):
      #object.entry_set(self.adapter.lastEntry)
      #print dir(object)
      #return
      self.adapter.cmdInTxt = curEntryTxt[:-6]
      self.adapter.autocompleteRequest()
      #object.cursor_selection_begin()
      #object.cursor_selection_end()
      object.cursor_line_end_set()
      self.adapter.lastEntry = self.adapter.cmdInTxt
    elif(curEntryTxt.endswith(self.crlf)):
      self.adapter.cmdInTxt = curEntryTxt[:-5]
      object.entry_set("")
      self.adapter.signalCmdInputSubmit()
      self.adapter.lastEntry = self.adapter.cmdInTxt
    else:
      self.adapter.signalCmdInputChange()
      #self.lb.text_set(self.adapter.stdOut)
    #object.entry_set(curEntryTxt + "ss")
    #object.entry_insert("ss")
    #print entry.entry_get()

  def key_down(self, entry, event, *args, **kwargs):
    # "Shift", "Control", "Alt", "Meta", "Hyper", "Super".
    #print event, event.modifier_is_set("Alt")
    if(event.keyname=="Up"):
      self.adapter.showPreviousCmdRequest()
    elif(event.keyname=="Down"):
      self.adapter.showNextCmdRequest()
    elif(event.keyname=="Escape"):
      self.adapter.escapeRequest()
    elif(
        event.modifier_is_set("Control")
        and event.modifier_is_set("Alt")
        and event.keyname=="q"
      ):
      elementary.exit()
      os.kill(os.getpid(), signal.SIGQUIT)

  def drawShellInput(self):
    win = self.win
    bx = self.bx

    bx2 = Box(win)
    bx2.horizontal_set(True)
    bx2.size_hint_weight_set(evas.EVAS_HINT_EXPAND, 0.0)
    bx2.size_hint_align_set(evas.EVAS_HINT_FILL, evas.EVAS_HINT_FILL)

    en = Entry(win)
    en.line_wrap_set(True)
    #en = elementary.ScrolledEntry(win)
    en.entry_set("")
    en.scale_set(1.5)
    #en.callback_anchor_clicked_add(my_entry_anchor_test, en)
    en.callback_changed_add(self._shellInputChangeHooker, en)
    # test mulitple key-binding
    en.on_key_down_add(self.key_down, en)
    en.size_hint_weight_set(evas.EVAS_HINT_EXPAND, evas.EVAS_HINT_EXPAND)
    #en.size_hint_weight_set(evas.EVAS_HINT_EXPAND, 0.0)
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

    """
    en = elementary.Entry(win)
    en.line_wrap_set(False)
    en.entry_set("This is an entry widget in this window that<br>"
                 "uses markup <b>like this</> for styling and<br>"
                 "formatting <em>like this</>, as well as<br>"
                 "<a href=X><link>links in the text</></a>, so enter text<br>"
                 "in here to edit it. By the way, links are<br>"
                 "called <a href=anc-02>Anchors</a> so you will need<br>"
                 "to refer to them this way.")
    en.callback_anchor_clicked_add(my_entry_anchor_test, en)
    en.size_hint_weight_set(evas.EVAS_HINT_EXPAND, evas.EVAS_HINT_EXPAND)
    en.size_hint_align_set(evas.EVAS_HINT_FILL, evas.EVAS_HINT_FILL)
    bx.pack_end(en)
    en.show()
    """

    en.focus_set(True)
    self.shellInput = en

  def drawLabel(self, txt):
    box0 = self.bx

    sp = Separator(self.win)
    sp.horizontal_set(True)
    self.bx.pack_end(sp)
    sp.show()

    sc = Scroller(self.win)
    sc.bounce = (False, True)
    sc.policy = (elementary.scroller.ELM_SCROLLER_POLICY_OFF, elementary.scroller.ELM_SCROLLER_POLICY_AUTO)
    sc.size_hint_align = (evas.EVAS_HINT_FILL, evas.EVAS_HINT_FILL)
    sc.size_hint_weight = (evas.EVAS_HINT_EXPAND, evas.EVAS_HINT_EXPAND)
    self.bx.pack_end(sc)
    sc.show()

    self.bxCrt = Box(self.win)
    self.bxCrt.size_hint_weight_set(evas.EVAS_HINT_EXPAND, evas.EVAS_HINT_EXPAND)
    self.bxCrt.size_hint_align_set(evas.EVAS_HINT_FILL, evas.EVAS_HINT_FILL)
    self.lb = Label(self.win)
    self.lb.text_set(txt)
    #fr.content_set(lb)
    self.lb.show()
    self.bxCrt.pack_end(self.lb)
    self.bxCrt.show()
    sc.content = self.bxCrt
    #self.bx.pack_end(self.bxCrt)

  # e.x:
  #  items = [("Entry", entry_clicked),
  #           ("Entry Scrolled", entry_scrolled_clicked)]
  def drawList(self, item):
    win = self.win
    box0 = self.bx
    li = elementary.List(win)
    li.size_hint_weight_set(evas.EVAS_HINT_EXPAND, evas.EVAS_HINT_EXPAND)
    li.size_hint_align_set(evas.EVAS_HINT_FILL, evas.EVAS_HINT_FILL)
    box0.pack_end(li)
    li.show()

    for item in items:
      li.item_append(item[0], callback=item[1])

    li.go()

  def _clearShellInput(self, button):
    self.shellInput.entry_set("")
    self.lb.hide()

if __name__ == "__main__":
    o = Terminal()

