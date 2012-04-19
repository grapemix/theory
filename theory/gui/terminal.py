# -*- coding: utf-8 -*-
#!/usr/bin/env python
##### System wide lib #####
import os

##### Theory lib #####

##### Theory third-party lib #####

##### Enlightenment lib #####
import ecore
import edje
import elementary
import evas

##### Local app #####

##### Theory app #####

##### Misc #####

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
  lastEntry = ""

  @property
  def adapter(self):
    return self._adapter

  @adapter.setter
  def adapter(self, adapter):
    self._adapter = adapter
    self._adapter.printTxt = lambda x: self.lb.text_set(x)

  def __init__(self):
    elementary.init()
    self.win = elementary.Window("theory", elementary.ELM_WIN_BASIC)
    self.win.title_set("Theory")
    self.win.callback_destroy_add(lambda x: elementary.exit())
    self.win.autodel_set(True)
    bg = elementary.Background(self.win)
    self.win.resize_object_add(bg)
    bg.size_hint_weight_set(evas.EVAS_HINT_EXPAND, evas.EVAS_HINT_EXPAND)
    bg.show()

    self.bx = elementary.Box(self.win)
    self.win.resize_object_add(self.bx)
    self.bx.size_hint_weight_set(evas.EVAS_HINT_EXPAND, evas.EVAS_HINT_EXPAND)
    self.bx.show()
    self.drawShellInput()
    self.drawLabel("")
    self.win.resize(640,100)
    self.win.show()

  def drawAll(self):
    elementary.run()
    elementary.shutdown()

  def _shellInputChangeHooker(self, object, entry, *args, **kwargs):
    curEntryTxt = object.entry_get()
    if(curEntryTxt==self.lastEntry or curEntryTxt==""):
      return
    if(curEntryTxt.endswith("<tab/>")):
      object.entry_set(self.lastEntry)
      print dir(object)
      #object.cursor_selection_begin()
      #object.cursor_selection_end()
      return
    elif(curEntryTxt.endswith("<br/>")):
      self.adapter.cmdInTxt = curEntryTxt[:-5]
      object.entry_set("")
      self.adapter.signalCmdInputSubmit()
    else:
      self.adapter.signalCmdInputChange()
      # TODO: move autocomplete into adapter
      #self.lb.text_set(self.adapter.stdOut)
    self.lastEntry = curEntryTxt
    #object.entry_set(curEntryTxt + "ss")
    #object.entry_insert("ss")
    #print entry.entry_get()

  def drawShellInput(self):
    win = self.win
    bx = self.bx

    bx2 = elementary.Box(win)
    bx2.horizontal_set(True)
    bx2.size_hint_weight_set(evas.EVAS_HINT_EXPAND, 0.0)
    bx2.size_hint_align_set(evas.EVAS_HINT_FILL, evas.EVAS_HINT_FILL)

    en = elementary.ScrolledEntry(win)
    en.entry_set("")
    en.callback_anchor_clicked_add(my_entry_anchor_test, en)
    en.callback_changed_add(self._shellInputChangeHooker, en)
    #en.callback_changed_user_add(self._shellInputChangeHooker, en)
    en.size_hint_weight_set(evas.EVAS_HINT_EXPAND, evas.EVAS_HINT_EXPAND)
    #en.size_hint_weight_set(evas.EVAS_HINT_EXPAND, 0.0)
    en.size_hint_align_set(evas.EVAS_HINT_FILL, evas.EVAS_HINT_FILL)
    bx2.pack_end(en)
    en.show()
    en.focus()

    bt = elementary.Button(win)
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

    sp = elementary.Separator(self.win)
    sp.horizontal_set(True)
    self.bx.pack_end(sp)
    sp.show()

    self.lb = elementary.Label(self.win)
    self.lb.text_set(txt)
    #fr.content_set(lb)
    self.lb.show()
    self.bx.pack_end(self.lb)

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

