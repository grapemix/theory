# -*- coding: utf-8 -*-
#!/usr/bin/env python
##### System wide lib #####
from abc import ABCMeta, abstractmethod
from collections import OrderedDict

##### Theory lib #####

##### Theory third-party lib #####

##### Enlightenment lib #####
from efl import elementary
from efl import evas
from efl.elementary.background import Background as EBackground
from efl.elementary.box import Box as EBox
from efl.elementary.check import Check as ECheck
from efl.elementary.button import Button as EButton
from efl.elementary.entry import Entry as EEntry
from efl.elementary.fileselector_entry import FileselectorEntry \
    as EFileselectorEntry
from efl.elementary.frame import Frame as EFrame
from efl.elementary.genlist import Genlist as EGenlist
from efl.elementary.genlist import GenlistItemClass as EGenlistItemClass
from efl.elementary.genlist import ELM_GENLIST_ITEM_GROUP
from efl.elementary.hoversel import Hoversel as EHoversel
from efl.elementary.icon import Icon as EIcon
from efl.elementary.label import Label as ELabel
from efl.elementary.list import List as EList
from efl.elementary.radio import Radio as ERadio
from efl.elementary.table import Table as ETable
from efl.elementary.window import StandardWindow as EStandardWindow

##### Local app #####

##### Theory app #####

##### Misc #####

__all__ = ("Label", "Frame", "ListValidator", "ListModelValidator", "Genlist",
"Box", "Entry", "Multibuttonentry", "Button", "Icon", "CheckBox", "RadioBox",
"SelectBox", "FileSelector", "getNewUiParam",
)

EXPAND_BOTH = (evas.EVAS_HINT_EXPAND, evas.EVAS_HINT_EXPAND)
EXPAND_HORIZ = (evas.EVAS_HINT_EXPAND, 0.0)
FILL_BOTH = (evas.EVAS_HINT_FILL, evas.EVAS_HINT_FILL)
FILL_HORIZ = (evas.EVAS_HINT_FILL, 0.0)

def getNewUiParam(winTitle=""):
  win = EStandardWindow(str(winTitle), str(elementary.ELM_WIN_BASIC))
  win.autodel = True
  win.title_set(winTitle)
  win.autodel_set(True)
  bg = EBackground(win)
  win.resize_object_add(bg)
  bg.size_hint_weight_set(evas.EVAS_HINT_EXPAND, evas.EVAS_HINT_EXPAND)
  bg.show()

  bx = EBox(win)
  win.resize_object_add(bx)
  bx.size_hint_weight_set(evas.EVAS_HINT_EXPAND, evas.EVAS_HINT_EXPAND)
  bx.show()
  win.show()

  return OrderedDict([
    ("win", win),
    ("bx", bx),
    ("unFocusFxn", lambda *args, **kwargs: None),
    # The rpcTerminalMixin should rm the cmdFormCache instead of in here
    ("cleanUpCrtFxn", lambda *kwargs: win.delete()),
    ])

# Honestly, I am not satisfied with the code related to the GUI. So the code
# related to GUI might have a big change in the future
class E17Widget(object):
  __metaclass__ = ABCMeta
  #win = None
  #bx = None

  def __init__(self, attrs=None, *args, **kwargs):
    self.win = None
    self.bx = None
    self.obj = None
    self.attrs = {
        "isFillAlign": False,
        "isFocus": False,
        "isWeightExpand": False,
        "initData": None,
        "isShrink": False,
    }

    if attrs is not None:
      self.attrs = self._buildAttrs(attrs)

  def _buildAttrs(self, extraAttrs=None, **kwargs):
    """Helper function for building an attribute dictionary."""
    attrs = dict(self.attrs, **kwargs)
    if extraAttrs:
      attrs.update(extraAttrs)
    return attrs

  def __deepcopy__(self, memo):
    obj = copy.copy(self)
    obj.attrs = self.attrs.copy()
    memo[id(self)] = obj
    return obj

  def preGenerate(self, *args, **kwargs):
    pass

  @abstractmethod
  def generate(self, *args, **kwargs):
    pass

  def postGenerate(self):
    #if(self.bx and not self.attrs["ignoreParentExpand"]):
    #  self.bx.size_hint_weight = EXPAND_BOTH
    #  self.bx.size_hint_align = FILL_BOTH

    if not self.attrs["isShrink"]:
      if(self.attrs["isWeightExpand"]):
        self.obj.size_hint_weight = EXPAND_BOTH
      else:
        self.obj.size_hint_weight = EXPAND_HORIZ

      if(self.attrs["isFillAlign"]):
        self.obj.size_hint_align = FILL_BOTH
      else:
        self.obj.size_hint_align = FILL_HORIZ

    if isinstance(self.obj, EBox) and "layout" in self.attrs:
      self.obj.layout_set(self.attrs["layout"])
    self.obj.show()
    if(self.attrs["isFocus"]):
      self.obj.focus_set(True)

  def setFocus(self):
    self.obj.focus_set(True)

class Label(E17Widget):
  def __init__(self, attrs=None, *args, **kwargs):
    defaultAttrs = {
        "isFillAlign": False,
        "initData": "",
    }
    if(attrs is not None):
      defaultAttrs.update(attrs)
    super(Label, self).__init__(defaultAttrs, *args, **kwargs)

  def generate(self, *args, **kwargs):
    lb = ELabel(self.win)
    lb.text_set(self.attrs["initData"].replace("\n", "<br/>"))
    self.obj = lb

  def reset(self, **kwargs):
    if(not hasattr(self, "obj")):
      self.generate()
    elif "finalData" in kwargs:
      self.obj.text_set(kwargs["finalData"].replace("\n", "<br/>"))
    elif "errData" in kwargs:
      # The color should be in red, but elementary has a bug and unable to
      # display text in red!
      kwargs["errData"] = \
         '<font color="#00FFFF">' + "<br/>".join(kwargs["errData"]) + '</font>'
      self.obj.text_set(kwargs["errData"])

class Frame(E17Widget):
  title = None
  content = None

  def generate(self, *args, **kwargs):
    fr = EFrame(self.win)
    fr.text_set(self.title)
    self.obj = fr

  def postGenerate(self):
    if(self.content!=None):
      self.obj.content_set(self.content.obj)
    if(hasattr(self.bx, "pack_end")):
      self.bx.pack_end(self.obj)
    super(Frame, self).postGenerate()

  @property
  def finalData(self):
    self.obj.text_get(finalData)

  @finalData.setter
  def finalData(self, finalData):
    self.obj.text_set(finalData)

  def hide(self):
    if(self.obj!=None):
      self.obj.hide()

  def show(self):
    if(self.obj!=None):
      self.obj.show()

class List(E17Widget):
  def __init__(self, attrs=None, *args, **kwargs):
    super(List, self).__init__(attrs, *args, **kwargs)
    self.children = []

  def generate(self, *args, **kwargs):
    li = EList(self.win)
    self.obj = li

  def addChild(self, item, *args, **kwargs):
    """Must ran after generate"""
    self.obj.item_append(item, *args, **kwargs)
    self.children.append()


class Genlist(E17Widget):
  def __init__(self, attrs=None, *args, **kwargs):
    defaultAttrs = {\
        "isFillAlign": True, \
        "isWeightExpand": True, \
    }
    if(attrs is not None):
      defaultAttrs.update(attrs)
    super(Genlist, self).__init__(defaultAttrs, *args, **kwargs)
    self.children = []

  def generate(self, *args, **kwargs):
    gl = EGenlist(self.win)
    # TODO: Use this when genlist elm_genlist_highlight_mode_set is ready
    #gl.multi_select_set(True)
    self.obj = gl

    # TODO: fix this super ugly hack
    size = self.win.size
    if(size[0]<640 or size[1]<500):
      self.win.resize(640,500)

#  def _selectedRowCallback(self, gl, gli, *args, **kwargs):
#    print "selected"
#  def _clickedDoubleRowCallback(self, gl, gli):
#    print "double clicked", gl, gli
#  def _clickedRowCallback(self, gl, gli):
#    print "clicked"
#  def _longpressedRowCallback(self, gl, gli, *args, **kwargs):
#    print "longpressed"

# TODO: Use this when genlist elm_genlist_highlight_mode_set is ready
#  def __keyDownAdd(self, gl, e, *args, **kwargs):
#    print dir(gl.selected_item), e
#    if(e.keyname=="space"):
#      gl.selected_item.next.selected = True
#      gl.selected_item.next.select_mode_set(True)

  def registerEvent(self, *args, **kwargs):
    if(hasattr(self, "_longpressedRowCallback")):
      self.obj.callback_longpressed_add(self._longpressedRowCallback)
    if(hasattr(self, "_selectedRowCallback")):
      self.obj.callback_selected_add(self._selectedRowCallback)
    if(hasattr(self, "_clickedDoubleRowCallback")):
      self.obj.callback_clicked_double_add(self._clickedDoubleRowCallback)
    # TODO: fix the callback_clicked_add
    if(hasattr(self, "_clickedRowCallback")):
      self.obj.callback_clicked_add(self._clickedRowCallback)
    # TODO: Use this when genlist elm_genlist_highlight_mode_set is ready
    #self.obj.on_key_down_add(self.__keyDownAdd, self.obj)

  def generateItemRow(self, *args, **kwargs):
    """
    Have to define text getter fxn and content getter fxn before calling it
    """
    return EGenlistItemClass(item_style="default",
                                       text_get_func=self._rowItemTextGetter,
                                       content_get_func=self._rowItemContentGetter)

  def generateGroupRow(self, *args, **kwargs):
    """
    Have to define text getter fxn and content getter fxn before calling it
    """
    return EGenlistItemClass(item_style="group_index",
                                       text_get_func=self._rowGroupTextGetter,
                                       content_get_func=self._rowGroupContentGetter)

  def _groupAdder(self, itc_g, data, *args, **kwargs):
    return self.obj.item_append(itc_g, data,
                         #flags=elementary.ELM_GENLIST_ITEM_TREE)
                         flags=ELM_GENLIST_ITEM_GROUP)

  def _itemAdder(self, itc_i, data, git, *args, **kwargs):
    self.obj.item_append(itc_i, data, git)

  def postGenerate(self):
    if(hasattr(self, "feedData")):
      self.feedData()
    self.registerEvent()
    super(Genlist, self).postGenerate()

class ListValidator(Genlist):
  def __init__(self, attrs=None, *args, **kwargs):
    super(ListValidator, self).__init__(attrs, *args, **kwargs)
    self.checkboxLst = []
    self.checkboxRelMap = {}
    self.changedRow = {}

  def _rowItemTextGetter(self, obj, part, item_data):
    return item_data[1]

  def _rowItemContentGetter(self, obj, part, data):
    r = CheckBox()
    r.win = self.win
    r.attrs["initData"] = data[2]
    r.generate()
    self.checkboxLst[data[0]] = r
    return r.obj

  def _rowGroupTextGetter(self, obj, part, item_data):
    return item_data[1]

  def _rowGroupContentGetter(self, obj, part, data):
    r = CheckBox()
    r.win = self.win
    r.attrs["initData"] = True
    r.generate()
    self.checkboxLst[data[0]] = r
    return r.obj

  # Probably depreciate
  def _keyDownAdd(self, gl, e, *args, **kwargs):
    # "Shift", "Control", "Alt", "Meta", "Hyper", "Super".
    #if(e.keyname=="space" and e.modifier_is_set("Control")):
    if(e.keyname=="space"):
      item = gl.selected_item
      pos = item.data[0]
      if pos in self.checkboxRelMap:
        (startIdx, endIdx) = self.checkboxRelMap[pos]
        initState = self.checkboxLst[startIdx].obj.state
        for idx in range(startIdx, endIdx):
          ck = self.checkboxLst[idx]
          ck.obj.state = not initState
          #if(idx!=startIdx):
          #  continue
          if idx+1 not in self.dataPos:
            continue
          elif self.dataPos[idx+1] in self.changedRow:
            del self.changedRow[self.dataPos[idx+1]]
          else:
            self.changedRow[self.dataPos[idx+1]] = True
            #self.changedRow[self.dataPos[pos+1]] = True
      else:
        self.checkboxLst[pos].obj.state = not self.checkboxLst[pos].obj.state
        item.next.selected = True
        if self.dataPos[pos+1] in self.changedRow:
          del self.changedRow[self.dataPos[pos+1]]
        else:
          self.changedRow[self.dataPos[pos+1]] = True

  def feedData(self):
    self.obj.on_key_down_add(self._keyDownAdd, self.obj)

    itc_i = self.generateItemRow()
    itc_g = self.generateGroupRow()

    counter = 0
    # TODO: remove me plz
    self.dataPos = {}
    # TODO: remove me plz
    parentCounter = 0
    for grpA, grpB in self.attrs["initData"]:
      startIdx = counter
      self.checkboxLst.append(None)
      git = self._groupAdder(itc_g, (counter, grpA))
      counter += 1

      isAllTrue = True
      for bStr, initState in grpB:
        self.checkboxLst.append(None)
        self._itemAdder(itc_i, (counter, bStr, initState), git)
        counter += 1
        self.dataPos[counter] = (parentCounter, counter-startIdx-1)
        if(initState==False):
          isAllTrue = False
      if(isAllTrue):
        self.checkboxLst[startIdx].attrs["initData"] = True
      else:
        self.checkboxLst[startIdx].attrs["initData"] = False
      parentCounter += 1
      self.checkboxRelMap[startIdx] = (startIdx, counter)

  @property
  def changedData(self):
    #return [cb.obj.state for cb in self.checkboxLst]
    return self.changedRow.keys()

class ListModelValidator(Genlist):
  def __init__(self, attrs=None, *args, **kwargs):
    super(ListModelValidator, self).__init__(attrs, *args, **kwargs)
    self.grpAState = []

  def _rowItemTextGetter(self, obj, part, item_data):
    return item_data[0]["refItemTitleLst"][item_data[1]]

  def _rowItemContentGetter(self, obj, part, data):
    r = CheckBox()
    r.win = self.win
    r.attrs["initData"] = data[0]["finalState"][data[1]]
    r.generate()
    return r.obj

  def _rowGroupTextGetter(self, obj, part, item_data):
    return item_data[0]["refGrpTitle"].encode("utf8")

  def _rowGroupContentGetter(self, obj, part, data):
    r = CheckBox()
    r.win = self.win
    r.attrs["initData"] = self.grpAState[data[1]]
    r.generate()
    return r.obj

  def _keyDownAdd(self, gl, e, *args, **kwargs):
    # "Shift", "Control", "Alt", "Meta", "Hyper", "Super".
    #if(e.keyname=="space" and e.modifier_is_set("Control")):
    if(e.keyname=="space"):
      item = gl.selected_item
      pos = item.data[1]
      if item.parent is None:
        currentState = self.grpAState[pos]
        self.grpAState[pos] = not currentState
        item.update()
        child = item.next
        child.data[0]["finalState"] = [
            not currentState for i in range(len(child.data[0]["finalState"]))
            ]
        while child.parent is not None:
          child.update()
          child = child.next
      else:
        currentState = item.data[0]["finalState"][item.data[1]]
        item.data[0]["finalState"][item.data[1]] = not currentState
        item.update()
        item.next.selected = True

  def feedData(self):
    self.obj.on_key_down_add(self._keyDownAdd, self.obj)

    itc_i = self.generateItemRow()
    itc_g = self.generateGroupRow()

    counter = 0
    for classifierDict in self.attrs["initData"]:
      self.grpAState.append(True)
      git = self._groupAdder(itc_g, (classifierDict, counter))

      isAllTrue = True
      for stateIdx in range(len(classifierDict["finalState"])):
        self._itemAdder(itc_i, (classifierDict, stateIdx), git)
        if classifierDict["finalState"][stateIdx] == False:
          isAllTrue = False
      if(isAllTrue):
        self.grpAState[-1] = True
      else:
        self.grpAState[-1] = False
      counter += 1

  @property
  def initData(self):
    return self.attrs["initData"]

  @property
  def changedData(self):
    item = self.obj.first_item
    isBeforeFirstChild = False
    r = []
    while(item!=None):
      if(item.parent==None):
        isBeforeFirstChild = True
      elif(isBeforeFirstChild):
        r.append(item.data[0])
        isBeforeFirstChild = False
      item = item.next
    return r

  @property
  def finalData(self):
    item = self.obj.first_item
    isBeforeFirstChild = False
    r = []
    while(item!=None):
      if(item.parent==None):
        isBeforeFirstChild = True
      elif(isBeforeFirstChild):
        r.append(item.data[0])
        isBeforeFirstChild = False
      item = item.next
    return r

class Box(E17Widget):

  def __init__(self, attrs=None, *args, **kwargs):
    defaultAttrs = {
        "isFillAlign": True,
        "isWeightExpand": True,
        "isHorizontal": False,
    }
    if(attrs is not None):
      defaultAttrs.update(attrs)
    super(Box, self).__init__(defaultAttrs, *args, **kwargs)
    self.widgetChildrenLst = []
    self.inputChildrenLst = [] # input inside this box

  def generate(self, *args, **kwargs):
    if(self.obj is not None):
      return

    bx = EBox(self.win)

    if(self.attrs["isHorizontal"]):
      bx.horizontal_set(True)

    # If a box is inside a frame
    if(self.bx is not None):
      self.bx.pack_end(bx)
    self.obj = bx

  def addWidget(self, widget):
    """Must ran after generate"""
    widget.bx = self.obj
    self.widgetChildrenLst.append(widget)

  def insertAndGenerateWidget(self, startIdx, widgetLst):
    """Must ran after generate. """
    i = startIdx
    for widget in widgetLst:
      self.widgetChildrenLst.insert(i, widget)
      i += 1

    self._postGenerateChildren(widgetLst, i)

  def removeWidgetLst(self, startIdx, length):
    """Must ran after generate"""
    for child in self.widgetChildrenLst[startIdx: startIdx + length]:
      child.obj.delete()
    for i in range(length):
      del self.widgetChildrenLst[startIdx]

  def addInput(self, input):
    self.inputChildrenLst.append(input)

  def _postGenerateInputLst(self, inputChildrenLst):
    for input in inputChildrenLst:
      input.generate()
      # Don't do pack_end in here. Too late.

  def _postGenerateChildren(self, widgetChildrenLst, startIdx=None):
    i = startIdx
    for child in widgetChildrenLst:
      if(child.obj is None):
        child.generate()
      if(startIdx is None):
        # for first element
        self.obj.pack_end(child.obj)
      else:
        # for appending more element
        self.obj.pack_before(child.obj, self.widgetChildrenLst[i].obj)
    for child in widgetChildrenLst:
      child.postGenerate()

  def postGenerate(self):
    """Must ran after generate"""
    self._postGenerateInputLst(self.inputChildrenLst)
    self._postGenerateChildren(self.widgetChildrenLst)
    super(Box, self).postGenerate()

  def hide(self):
    if(self.obj!=None):
      self.obj.hide()

  def show(self):
    if(self.obj!=None):
      self.obj.show()

  def registerUnfocusFxn(self, unFocusFxn):
    self.obj.on_key_down_add(unFocusFxn, self.obj)

class Table(Box):
  def generate(self, *args, **kwargs):
    if(self.obj is not None):
      return

    bx = ETable(self.win)

    # If a box is inside a frame
    if(self.bx is not None):
      self.bx.pack_end(bx)
    self.obj = bx

  def addInput(self, input, x, y, w, h):
    input.generate()
    self.obj.pack(input.mainContainer.obj, x, y, w, h)
    self.inputChildrenLst.append(input.mainContainer)

  def postGenerate(self):
    """Must ran after generate"""
    for input in self.inputChildrenLst:
      input.postGenerate()

class Entry(E17Widget):
  def __init__(self, attrs=None, *args, **kwargs):
    defaultAttrs = {
      "initData": "",
      "autoFocus": False,
      "isFillAlign": True,
      "isWeightExpand": True,
      "isLineWrap": True,
      "isScrollable": False,
      "isSingleLine": True,
    }
    if(attrs is not None):
      defaultAttrs.update(attrs)
    super(Entry, self).__init__(defaultAttrs, *args, **kwargs)

  def _createObj(self):
    return EEntry(self.win)

  def generate(self, *args, **kwargs):
    en = self._createObj()
    self.obj = en

    if(self.attrs["initData"] is not None):
      self.finalData = self.attrs["initData"]
    if(hasattr(self, "_anchorClick")):
      en.callback_anchor_clicked_add(self._anchorClick)
    if(hasattr(self, "_keyDownAdd")):
      en.on_key_down_add(self._keyDownAdd)
    if(hasattr(self, "_contentChanged")):
      en.callback_changed_add(self._contentChanged, self._fieldName)
    if(self.attrs["autoFocus"]):
      en.focus_set(1)
    if(hasattr(self, "_focusChanged")):
      en.callback_unfocused_add(self._focusChanged, self._fieldName)

    if(self.attrs["isSingleLine"]):
      en.single_line_set(True)

      if(self.attrs["isLineWrap"]):
        en.line_wrap_set(True)

  #def _keyDownAdd(self, entry, event, *args, **kwargs):
  #  "Shift", "Control", "Alt", "Meta", "Hyper", "Super".
  #  pass

  #def _anchorClick(self, obj, en, *args, **kwargs):
  #  pass

  @property
  def finalData(self):
    return self.obj.entry_get()

  @finalData.setter
  def finalData(self, finalData):
    self.reset(finalData=finalData)

  def reset(self, **kwargs):
    txt = ""
    if "initData" in kwargs:
      txt = kwargs["initData"]
    elif "finalData" in kwargs:
      txt = kwargs["finalData"]
    self.obj.entry_set(str(txt))

class Button(E17Widget):
  icon = None
  isDisable = False
  label = None

  def __init__(self, attrs=None, *args, **kwargs):
    defaultAttrs = {"isFillAlign": True}
    self._clickedData = None
    if(attrs is not None):
      defaultAttrs.update(attrs)
    super(Button, self).__init__(defaultAttrs, *args, **kwargs)

  def generate(self, *args, **kwargs):
    bt = EButton(self.win)
    if(self.label):
      bt.text_set(self.label)
    if(hasattr(self, "_clicked")):
      bt.callback_clicked_add(self._clicked, self._clickedData)
    self.obj = bt


class Icon(E17Widget):
  file = ""

  def generate(self, *args, **kwargs):
    ic = EIcon(self.win)
    ic.file_set(file)
    self.obj = ic

class CheckBox(E17Widget):
  icon = None
  isDisable = False
  label = None

  def generate(self, *args, **kwargs):
    ck = ECheck(self.win)
    self.obj = ck

    if(self.label is not None):
      ck.text_set(self.label)
    if(self.icon is not None):
      ck.icon_set(ic)
    if(self.attrs["initData"] is not None):
      self.finalData = self.attrs["initData"]
    if(self.isDisable):
      ck.disabled_set(True)
    if(hasattr(self, "_checkChanged")):
      ck.callback_changed_add(self._checkChanged)

  @property
  def finalData(self):
    return self.obj.state_get()

  @finalData.setter
  def finalData(self, finalData):
    self.obj.state_set(finalData)

class RadioBox(E17Widget):
  isDisable = False

  def __init__(self, attrs=None, *args, **kwargs):
    defaultAttrs = {
        "isFillAlign": True,
        "isWeightExpand": False,
        "choices": [],
    }
    if(attrs is not None):
      defaultAttrs.update(attrs)

    super(RadioBox, self).__init__(defaultAttrs, *args, **kwargs)
    self.obj = None
    self.objLst = []

  def _addRadioChoice(self, value, label, icon=None):
    rd = ERadio(self.win)
    if(hasattr(self, "_focusChanged")):
      # callback_unfocused_add is not working as we expected, so we use
      # callback_changed in here
      rd.callback_changed_add(self._focusChanged, self._fieldName)
    if(hasattr(self, "_contentChanged")):
      rd.callback_changed_add(self._contentChanged, self._fieldName)

    rd.text_set(label)
    rd.state_value_set(len(self.dataChoice))
    self.dataChoice.append(value)

    if(icon is not None):
      rd.icon_set(icon)
    if(self.isDisable):
      rd.disabled_set(True)

    rd.size_hint_weight = EXPAND_BOTH
    rd.size_hint_align = FILL_HORIZ

    if(self.rdg is not None):
      rd.group_add(self.rdg)
    else:
      self.rdg = rd
    rd.show()
    self.obj.pack_end(rd)
    self.objLst.append(rd)

  def generate(self, *args, **kwargs):
    if(self.obj is not None):
      self.obj.destroy()
    self.obj = EBox(self.win)
    self.obj.show()

    self.reset(choices=self.attrs["choices"], initData=self.attrs["initData"])

  def reset(self, choices=None, initData=None, finalData=None):
    selectedData = initData if finalData is None else finalData
    isRedraw = False
    if(choices is not None):
      self.attrs["choices"] = choices
      isRedraw = True

    if(finalData is not None):
      isRedraw = True
      if(choices is None):
        # That is only finalData has been assigned, but the choices remain the
        # same
        choices = self.attrs["choices"]

    if(isRedraw):
      for i in self.objLst:
        i.delete()
      self.obj.unpack_all()
      self.rdg = None
      self.objLst = []
      self.dataChoice= []
      buf = []

      # !!! Because e17 is unable to set selected data, we have to put the
      # assigned radio box at the beginning
      for data in choices:
        if(data[0]==selectedData):
          self._addRadioChoice(*data)
        else:
          buf.append(data)

      for data in buf:
        self._addRadioChoice(*data)

#    # !!! Because e17 is unable to set selected data, we have to put the
#    # assigned radio box at the beginning
#    if(value == self.attrs["initData"]):
#      #rd.value_pointer_set(value)
#      rd.value_set(value)

  @property
  def finalData(self):
    if(len(self.objLst)>0):
      return self.dataChoice[self.objLst[0].value_get()]
    else:
      return self.attrs["initData"]

  @finalData.setter
  def finalData(self, finalData):
    if(finalData==self.selectedData):
      return
    # we have to check in advance because we have to render data immediately
    if(finalData not in self.dataChoice):
      raise
    self.reset(finalData=finalData)

# TODO: to show init data as pre-select item
class SelectBox(E17Widget):
  """If developer has to assign specific icons into choices, they should
  assigned through the widget's attr["choices"] instead of fields.
  """
  icon = None
  isDisable = False
  label = "Please select"

  def __init__(self, attrs=None, *args, **kwargs):
    self.selectedData = (None, None)
    self.choices = {}
    defaultAttrs = {"choices": []}
    if(attrs is not None):
      defaultAttrs.update(attrs)
    if(attrs["initData"] is not None):
      self.selectedData = attrs["initData"]
    super(SelectBox, self).__init__(defaultAttrs, *args, **kwargs)

  def _selectionChanged(self, hoversel, hoverselItem):
    self.selectedData = self.choices[hoverselItem.text]

  @property
  def finalData(self):
    return self.selectedData

  @finalData.setter
  def finalData(self, finalData):
    # Becasue Hoversel cannot show data being selected
    self.selectedData = finalData

  def generate(self, *args, **kwargs):
    bt = EHoversel(self.win)
    bt.hover_parent_set(self.win)
    if(self.label!=None):
      bt.text_set(self.label)
    if(self.icon!=None):
      bt.icon_set(self.icon)
    if(self.isDisable):
      bt.disabled_set(True)
    for item in self.attrs["choices"]:
      try:
        (idx, label, imgPath) = item
      except ValueError:
        (idx, label) = item
        imgPath = None
      self.choices[label] = idx
      if(imgPath == None or imgPath==""):
        bt.item_add(label)
      else:
        ext = imgPath[-4:]
        if(ext in [".jpg", ".jpeg", ".gif", ".png"]):
          bt.item_add(label, imgPath, elementary.ELM_ICON_FILE)
        else:
          bt.item_add(label, imgPath, elementary.ELM_ICON_STANDARD)
    bt.callback_selected_add(self._selectionChanged)
    bt.size_hint_weight_set(0.0, 0.0)
    bt.size_hint_align_set(0.5, 0.5)
    self.obj = bt

class FileSelector(E17Widget):
  # This class will be unable to set initData because python-elementary does not
  # support

  def __init__(self, attrs=None, *args, **kwargs):
    defaultAttrs = {
        "isFillAlign": True,
        "isWeightExpand": True,
        "isFolderOnly": False,
        "initPath": "",
        }
    if(attrs is not None):
      defaultAttrs.update(attrs)
    super(FileSelector, self).__init__(defaultAttrs, *args, **kwargs)

  @property
  def finalData(self):
    return self.obj.selected_get()

  @finalData.setter
  def finalData(self, finalData):
    pass

  def generate(self, *args, **kwargs):
    fs = EFileselectorEntry(self.win)
    fs.text_set("Select a file")
    fs.inwin_mode_set(False)
    fs.folder_only_set(self.attrs["isFolderOnly"])
    fs.path_set(self.attrs["initPath"])

    self.obj = fs

class Multibuttonentry(Entry):
  @property
  def finalData(self):
    return self.obj.entry_get().split(",")

  @finalData.setter
  def finalData(self, finalData):
    self.reset(finalData=",".join(finalData))

#class Multibuttonentry(E17Widget):
#  def cb_filter1(self, mbe, text):
#    return True
#
#  def __init__(self, attrs=None, *args, **kwargs):
#    defaultAttrs = {\
#        "isFillAlign": True, \
#        "isWeightExpand": True, \
#    }
#    if(attrs is not None):
#      defaultAttrs.update(attrs)
#    super(Multibuttonentry, self).__init__(defaultAttrs, *args, **kwargs)
#    self.counter = 0
#    self.item = None
#
#  def generate(self, *args, **kwargs):
#    mbe = elementary.MultiButtonEntry(self.win)
#    self.obj = mbe
#
#    if("helperLabel" in self.attrs):
#      mbe.text = self.attrs["helperLabel"]
#    mbe.part_text_set("guide", "Tap to add")
#    mbe.filter_append(self.cb_filter1)
#    if(self.attrs["initData"] is not None):
#      self.finalData = self.attrs["initData"]
#
#  @property
#  def finalData(self):
#    return [i.text for i in self.obj.items]
#
#  @finalData.setter
#  def finalData(self, finalData):
#    self.reset(finalData=finalData)
#
#  def reset(self, initData=[], finalData=[]):
#    data = initData if(len(initData)>0) else finalData
#    for s in data:
#      self.obj.item_append(s)

