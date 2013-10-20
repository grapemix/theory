# -*- coding: utf-8 -*-
#!/usr/bin/env python
##### System wide lib #####
from abc import ABCMeta, abstractmethod

##### Theory lib #####

##### Theory third-party lib #####

##### Enlightenment lib #####
import elementary
import evas

##### Local app #####

##### Theory app #####

##### Misc #####

__all__ = ("Label", "Frame", "ListValidator", "ListModelValidator", "Genlist", \
    "Box", "Entry", "Multibuttonentry", "Button", "Icon", "CheckBox", "RadioBox", "SelectBox", \
    "FileSelector")

EXPAND_BOTH = (evas.EVAS_HINT_EXPAND, evas.EVAS_HINT_EXPAND)
EXPAND_HORIZ = (evas.EVAS_HINT_EXPAND, 0.0)
FILL_BOTH = (evas.EVAS_HINT_FILL, evas.EVAS_HINT_FILL)
FILL_HORIZ = (evas.EVAS_HINT_FILL, 0.0)

# Honestly, I am not satisfied with the code related to the GUI. So the code
# related to GUI might have a big change in the future
class E17Widget(object):
  __metaclass__ = ABCMeta
  win = None
  bx = None

  def __init__(self, attrs=None, *args, **kwargs):
    self.obj = None
    self.attrs = {
        "isFillAlign": False,
        "isFocus": False,
        "isWeightExpand": False,
        "initData": None,
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

    if(self.attrs["isWeightExpand"]):
      self.obj.size_hint_weight = EXPAND_BOTH
    else:
      self.obj.size_hint_weight = EXPAND_HORIZ

    if(self.attrs["isFillAlign"]):
      self.obj.size_hint_align = FILL_BOTH
    else:
      self.obj.size_hint_align = FILL_HORIZ

    if(isinstance(self.obj, elementary.Box) and self.attrs.has_key("layout")):
      self.obj.layout_set(self.attrs["layout"])
    self.obj.show()
    if(self.attrs["isFocus"]):
      self.obj.focus_set(True)

  def setFocus(self):
    self.obj.focus_set(True)

class Label(E17Widget):
  def __init__(self, attrs=None, *args, **kwargs):
    defaultAttrs = {\
        "isFillAlign": False, \
        "initData": "", \
    }
    if(attrs is not None):
      defaultAttrs.update(attrs)
    super(Label, self).__init__(defaultAttrs, *args, **kwargs)

  def generate(self, *args, **kwargs):
    lb = elementary.Label(self.win)
    lb.text_set(self.attrs["initData"].replace("\n", "<br>"))
    self.obj = lb

class Frame(E17Widget):
  title = None
  content = None

  def generate(self, *args, **kwargs):
    fr = elementary.Frame(self.win)
    fr.text_set(self.title)
    self.obj = fr

  def postGenerate(self):
    if(self.content!=None):
      self.obj.content_set(self.content.obj)
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
    li = elementary.List(self.win)
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
    gl = elementary.Genlist(self.win)
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
    return elementary.GenlistItemClass(item_style="default",
                                       text_get_func=self._rowItemTextGetter,
                                       content_get_func=self._rowItemContentGetter)

  def generateGroupRow(self, *args, **kwargs):
    """
    Have to define text getter fxn and content getter fxn before calling it
    """
    return elementary.GenlistItemClass(item_style="group_index",
                                       text_get_func=self._rowGroupTextGetter,
                                       content_get_func=self._rowGroupContentGetter)

  def _groupAdder(self, itc_g, data, *args, **kwargs):
    return self.obj.item_append(itc_g, data,
                         #flags=elementary.ELM_GENLIST_ITEM_TREE)
                         flags=elementary.ELM_GENLIST_ITEM_GROUP)

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

  def _keyDownAdd(self, gl, e, *args, **kwargs):
    # "Shift", "Control", "Alt", "Meta", "Hyper", "Super".
    #if(e.keyname=="space" and e.modifier_is_set("Control")):
    if(e.keyname=="space"):
      item = gl.selected_item
      pos = item.data[0]
      if(self.checkboxRelMap.has_key(pos)):
        (startIdx, endIdx) = self.checkboxRelMap[pos]
        initState = self.checkboxLst[startIdx].obj.state
        for idx in range(startIdx, endIdx):
          ck = self.checkboxLst[idx]
          ck.obj.state = not initState
          #if(idx!=startIdx):
          #  continue
          if(not self.dataPos.has_key(idx+1)):
            continue
          elif(self.changedRow.has_key(self.dataPos[idx+1])):
            del self.changedRow[self.dataPos[idx+1]]
          else:
            self.changedRow[self.dataPos[idx+1]] = True
            #self.changedRow[self.dataPos[pos+1]] = True
      else:
        self.checkboxLst[pos].obj.state = not self.checkboxLst[pos].obj.state
        item.next.selected = True
        if(self.changedRow.has_key(self.dataPos[pos+1])):
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
    return item_data[0].ref.links[item_data[1]]

  def _rowItemContentGetter(self, obj, part, data):
    r = CheckBox()
    r.win = self.win
    r.attrs["initData"] = data[0].finalState[data[1]]
    r.generate()
    return r.obj

  def _rowGroupTextGetter(self, obj, part, item_data):
    return item_data[0].name.encode("utf8")

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
      if(item.parent==None):
        currentState = self.grpAState[pos]
        self.grpAState[pos] = not currentState
        item.update()
        child = item.next
        child.data[0].finalState = [not currentState for i in range(len(child.data[0].finalState))]
        while(child.parent!=None):
          child.update()
          child = child.next
      else:
        currentState = item.data[0].finalState[item.data[1]]
        item.data[0].finalState[item.data[1]] = not currentState
        item.update()
        item.next.selected = True

  def feedData(self):
    self.obj.on_key_down_add(self._keyDownAdd, self.obj)

    itc_i = self.generateItemRow()
    itc_g = self.generateGroupRow()

    counter = 0
    for classifierModel in self.attrs["initData"]:
      self.grpAState.append(True)
      git = self._groupAdder(itc_g, (classifierModel.ref, counter))

      isAllTrue = True
      for stateIdx in range(len(classifierModel.finalState)):
        self._itemAdder(itc_i, (classifierModel, stateIdx), git)
        if(classifierModel.finalState[stateIdx]==False):
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

    bx = elementary.Box(self.win)

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
    return elementary.Entry(self.win)

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
      en.callback_changed_add(self._contentChanged)
    if(self.attrs["autoFocus"]):
      en.focus_set(1)
    if(hasattr(self, "_focusChanged")):
      en.callback_unfocused_add(self._focusChanged)

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
    if(kwargs.has_key("initData")):
      txt = kwargs["initData"]
    elif(kwargs.has_key("finalData")):
      txt = kwargs["finalData"]
    self.obj.entry_set(txt)

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
    bt = elementary.Button(self.win)
    if(self.label):
      bt.text_set(self.label)
    if(hasattr(self, "_clicked")):
      bt.callback_clicked_add(self._clicked, self._clickedData)
    self.obj = bt


class Icon(E17Widget):
  file = ""

  def generate(self, *args, **kwargs):
    ic = elementary.Icon(self.win)
    ic.file_set(file)
    self.obj = ic

class CheckBox(E17Widget):
  icon = None
  isDisable = False
  label = None

  def generate(self, *args, **kwargs):
    ck = elementary.Check(self.win)
    self.obj = ck

    if(self.label!=None):
      ck.text_set(self.label)
    if(self.icon!=None):
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
    rd = elementary.Radio(self.win)
    if(hasattr(self, "_focusChanged")):
      # callback_unfocused_add is not working as we expected, so we use
      # callback_changed in here
      rd.callback_changed_add(self._focusChanged)
    if(hasattr(self, "_contentChanged")):
      rd.callback_changed_add(self._contentChanged)

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
    self.obj = elementary.Box(self.win)
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
    bt = elementary.Hoversel(self.win)
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
  icon = []
  isDisable = False
  label = None
  initPath = None

  def __init__(self, attrs=None, *args, **kwargs):
    defaultAttrs = {"isFillAlign": True, "isWeightExpand": True}
    if(attrs is not None):
      defaultAttrs.update(attrs)
    super(FileSelector, self).__init__(defaultAttrs, *args, **kwargs)

  def fsDone(self, fs, selected, win):
      self.win.delete()

  def _selected(self, fs, selected, win):
      print "Selected file:", selected
      print "or:", fs.selected_get()

  def generate(self, *args, **kwargs):
    fs = elementary.Fileselector(self.win)
    fs.is_save_set(True)
    fs.expandable_set(False)
    if(self.initPath==None):
      import os
      fs.path_set(os.getenv("HOME"))
    else:
      fs.path_set(self.initPath)

    fs.callback_done_add(self.fsDone, self.win)
    if(hasattr(self, "_selected")):
      fs.callback_selected_add(self._selected, self.win)

    self.obj = fs


class Multibuttonentry(E17Widget):
  def cb_filter1(self, mbe, text):
    return True

  def __init__(self, attrs=None, *args, **kwargs):
    defaultAttrs = {\
        "isFillAlign": True, \
        "isWeightExpand": True, \
    }
    if(attrs is not None):
      defaultAttrs.update(attrs)
    super(Multibuttonentry, self).__init__(defaultAttrs, *args, **kwargs)
    self.counter = 0
    self.item = None

  def generate(self, *args, **kwargs):
    mbe = elementary.MultiButtonEntry(self.win)
    self.obj = mbe

    if(self.attrs.has_key("helperLabel")):
      mbe.text = self.attrs["helperLabel"]
    mbe.part_text_set("guide", "Tap to add")
    mbe.filter_append(self.cb_filter1)
    if(self.attrs["initData"] is not None):
      self.finalData = self.attrs["initData"]

  @property
  def finalData(self):
    return [i.text for i in self.obj.items]

  @finalData.setter
  def finalData(self, finalData):
    self.reset(finalData=finalData)

  def reset(self, initData=[], finalData=[]):
    data = initData if(len(initData)>0) else finalData
    for s in data:
      self.obj.item_append(s)

