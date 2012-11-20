# -*- coding: utf-8 -*-
#!/usr/bin/env python
##### System wide lib #####
from abc import ABCMeta, abstractmethod

##### Theory lib #####

##### Theory third-party lib #####

##### Local app #####
from e17.widget import *

##### Theory app #####

##### Misc #####

__all__ = (\
    "StringInput", "TextInput", "NumericInput", "SelectBoxInput",\
    "CheckBoxInput", "StringGroupFilterInput", "ModelValidateGroupInput",\
    "Fileselector", "ListInput", "FilterFormLayout", \
    )

# Honestly, I am not satisfied with the code related to the GUI. So the code
# related to GUI might have a big change in the future
class BasePacker(object):
  """This class is designed as a base class for a widget needed to be in a
  container. The widget in here can be a container which contains other object.
  It should also take care of how the main container connected with the rest
  of the program as well as the attrs.
  """
  #__metaclass__ = ABCMeta
  widgetClass = None
  attrs = {}

  def __init__(self, win, bx, attrs=None, *args, **kwargs):
    """attrs being asssigned should have higher priority than the default attrs
    """
    self.win = win
    self.bx = bx
    self.widgetLst = []

    self.attrs = self._buildAttrs(\
        attrs, isContainerAFrame=True)
    #self.attrs = self._buildAttrs(attrs=attrs)

  def _createWidget(self, *args, **kwargs):
    widget = self.widgetClass(self.attrs)
    widget.win = self.win
    return (widget,)

  def _createContainer(self, attrs=None, *args, **kwargs):
    hBox = Box(attrs)
    hBox.win = self.win
    if(not self.attrs["isContainerAFrame"]):
      hBox.bx = self.bx
    return hBox

  def _buildAttrs(self, extraAttrs=None, **kwargs):
    "Helper function for building an attribute dictionary."
    attrs = dict(self.attrs, **kwargs)
    if extraAttrs:
      attrs.update(extraAttrs)
    return attrs

  def __deepcopy__(self, memo):
    obj = copy.copy(self)
    obj.attrs = self.attrs.copy()
    memo[id(self)] = obj
    return obj

  def value_from_datadict(self, data, files, name):
    """
    Given a dictionary of data and this widget's name, returns the value
    of this widget. Returns None if it's not provided. Not used in this
    moment, will be used in the future.
    """
    return data.get(name, None)

class BaseLabelInput(BasePacker):
  """This class is designed for a widget with a name label and some help text.
  The widget in here can be a container which contains other object. The
  widget should be warp by a main container. The parent should not have
  much control on the main container and all attr simply pass to the widget."""

  __metaclass__ = ABCMeta
  def __init__(self, win, bx, attrs=None, *args, **kwargs):
    attrs = self._buildAttrs(\
        attrs, isExpandMainContainer=False)
    super(BaseLabelInput, self).__init__(win, bx, attrs, *args, **kwargs)
    if(self.attrs["isContainerAFrame"]):
      self.initLabelMainContainerAsFrame(*args, **kwargs)
    else:
      self.initLabelMainContainerAsTbl(*args, **kwargs)

  def initLabelMainContainerAsFrame(self, *args, **kwargs):
    if(self.attrs["isExpandMainContainer"]):
      fr = Frame({"isFillAlign": True, "isWeightExpand": True})
    else:
      fr = Frame({"isFillAlign": False, "isWeightExpand": False})
    fr.win = self.win
    fr.bx = self.bx
    self.mainContainer = fr
    lb = Label()
    lb.win = self.win
    self.widgetLst.append(lb)

  def initLabelMainContainerAsTbl(self, *args, **kwargs):
    lb = Label()
    lb.win = self.win
    self.widgetLst.append(lb)
    lb = Label()
    lb.win = self.win
    self.widgetLst.append(lb)

    if(self.attrs["isExpandMainContainer"]):
      hBox = self._createContainer({"isFillAlign": False, "isWeightExpand": False})
    hBox.generate()
    self.mainContainer = hBox

  def generate(self, *args, **kwargs):
    if(self.attrs["isContainerAFrame"]):
      self.packAsFrame(self.title, self.help, *args, **kwargs)
    else:
      self.packAsTbl(self.title, self.help, *args, **kwargs)

  def packAsFrame(self, title, help, *args, **kwargs):
    hBox = self._createContainer()
    hBox.generate()
    self.mainContainer.content = hBox
    self.mainContainer.title = title
    self.mainContainer.generate()

    self.widgetLst[-1].attrs["initData"] = help

    widgetLst = list(self._createWidget())
    self.widgetLst = widgetLst + self.widgetLst

    for widget in self.widgetLst:
      hBox.addWidget(widget)
    hBox.postGenerate()
    self.mainContainer.postGenerate()

  def packAsTbl(self, title, help, *args, **kwargs):
    hBox = self.mainContainer

    self.widgetLst[0].attrs["initData"] = title
    self.widgetLst[-1].attrs["initData"] = help

    widgetLst = self._createWidget()
    self.widgetLst = self.widgetLst[0] + widgetLst + self.widgetLst[1]
    #widget = self._createWidget()
    #self.widgetLst.insert(1, widget)

    for widget in self.widgetLst:
      hBox.addWidget(widget)
    hBox.postGenerate()

  @property
  def initData(self):
    return self.attrs["initData"]

  @abstractmethod
  def finalData(self):
    pass

class StringInput(BaseLabelInput):
  widgetClass = Entry

  #def __init__(self, win, bx, attrs=None, *args, **kwargs):
  #  defaultAttrs = self._buildAttrs(\
  #      attrs, isExpandMainContainer=False)
  #  super(StringInput, self).__init__(win, bx, defaultAttrs, *args, **kwargs)

  def _getData(self):
    return self.widgetLst[0].obj.entry_get()

  @property
  def initData(self):
    return self.attrs["initData"]

  @property
  def changedData(self):
    return self._getData()

  @property
  def finalData(self):
    return self._getData()

class TextInput(StringInput):
  def __init__(self, win, bx, attrs=None, *args, **kwargs):
    attrs = self._buildAttrs(attrs, isScrollable=True, isSingleLine=False, isExpandMainContainer=True)
    super(TextInput, self).__init__(win, bx, attrs, *args, **kwargs)

class NumericInput(StringInput):
  def __init__(self, win, bx, attrs=None, *args, **kwargs):
    attrs = self._buildAttrs(attrs, isExpandMainContainer=False)
    super(NumericInput, self).__init__(win, bx, attrs, *args, **kwargs)

class SelectBoxInput(BaseLabelInput):
  """Assuming labels are unique."""
  widgetClass = SelectBox

  @property
  def finalData(self):
    return self.widgetLst[0].selectedData

# TODO: Fix the padding problem
class CheckBoxInput(BaseLabelInput):
  widgetClass = CheckBox

  def _createWidget(self, *args, **kwargs):
    hBox = self._createContainer({"isFillAlign": False, "isWeightExpand": False, "isHorizontal": True, "ignoreParentExpand": True, })
    hBox.bx = self.bx
    hBox.generate()

    for v in self.attrs["choices"]:
      (label, value) = v
      widget = self.widgetClass({"ignoreParentExpand": True, "initData": value, })
      widget.win = self.win
      widget.label = label
      hBox.addWidget(widget)
    return (hBox,)

  @property
  def changedData(self):
    pass

class Fileselector(BaseLabelInput):
  widgetClass = FileSelector

class StringGroupFilterInput(BaseLabelInput):
  widgetClass = ListModelValidator
  #widgetClass = ListValidator

  def __init__(self, win, bx, attrs=None, *args, **kwargs):
    attrs = self._buildAttrs(attrs, initData=())
    super(StringGroupFilterInput, self).__init__(win, bx, attrs, *args, **kwargs)

  @property
  def changedData(self):
    return self.widgetLst[0].changedData()


class ModelValidateGroupInput(BaseLabelInput):
  widgetClass = ListModelValidator

  def __init__(self, win, bx, attrs=None, *args, **kwargs):
    attrs = self._buildAttrs(attrs, initData=())
    super(ModelValidateGroupInput, self).__init__(win, bx, attrs, *args, **kwargs)

  @property
  def initData(self):
    return self.widgetLst[0].initData()

  @property
  def changedData(self):
    return self.widgetLst[0].changedData()

  @property
  def finalData(self):
    return self.widgetLst[0].finalData()

class ListInput(BaseLabelInput):

  def __init__(self, win, bx, widgetClass, attrs=None, *args, **kwargs):
    attrs = self._buildAttrs(\
        attrs, isExpandMainContainer=True, initData=())
    # TODO: this is e17 specific, add one more layer instead
    if(widgetClass==StringInput.widgetClass):
      widgetClass = Multibuttonentry
      self._createWidget = self._createStringWidget
    else:
      self._createWidget = self._createGenericWidget
    self.widgetClass = widgetClass

    self._dataWidgetLst = []
    super(ListInput, self).__init__(win, bx, attrs, *args, **kwargs)

  def _addDataWidget(self, *args, **kwargs):
    (widget, buttonControlBox,) = self._createWidget()
    startIdx = len(self.widgetLst) - 1
    self.widgetLst.insert(len(self.widgetLst) - 1 , widget)
    self.widgetLst.insert(len(self.widgetLst) - 1 , buttonControlBox)
    self.mainContainer.content.insertAndGenerateWidget(startIdx , (widget, buttonControlBox))

  def _rmDataWidget(self, *args, **kwargs):
    idx = None
    for i in range(len(self.widgetLst)):
      if(self.widgetLst[i].obj == args[0].parent_widget):
        idx = i
        break
    if idx == None:
      raise
    del self.widgetLst[idx - 1]
    del self.widgetLst[idx - 1]
    self.mainContainer.content.removeWidgetLst(idx - 1, 2)
    del self._dataWidgetLst[(idx - 1)/2]

  def _createWidget(self, *args, **kwargs):
    pass

  def _createStringWidget(self, *args, **kwargs):
    widget = self.widgetClass({"isWeightExpand": True, "isFillAlign": True, "ignoreParentExpand": False })
    widget.win = self.win
    self._dataWidgetLst.append(widget)
    return (widget,)

    """
    buttonControlBox = self._createContainer({"isHorizontal": True, "isWeightExpand": False, "isFillAlign": False, "ignoreParentExpand": True,})
    buttonControlBox.generate()

    btn = Button({"isWeightExpand": True, "isFillAlign": False, "ignoreParentExpand": True,})
    btn.win = self.win
    btn.label = "Toggle Expand"
    btn._clicked = lambda btn: mbe.expanded_set(not mbe.expanded_get())
    buttonControlBox.addWidget(btn)

    btn = Button({"isWeightExpand": True, "isFillAlign": False, "ignoreParentExpand": True,})
    btn.win = self.win
    btn.label = "Clear"
    btn._clicked = lambda bt: widget.obj.clear()
    buttonControlBox.addWidget(btn)
    return (widget, buttonControlBox,)
    """


  def _createGenericWidget(self, *args, **kwargs):
    widget = self.widgetClass({"isWeightExpand": True, "isFillAlign": False, "ignoreParentExpand": True })
    widget.win = self.win
    self._dataWidgetLst.append(widget)


    buttonControlBox = self._createContainer({"isHorizontal": True, "isWeightExpand": False, "isFillAlign": False, "ignoreParentExpand": True,})
    buttonControlBox.generate()

    btn = Button({"isWeightExpand": True, "isFillAlign": False, "ignoreParentExpand": True,})
    btn.win = self.win
    btn.label = "Add"
    btn._clicked = self._addDataWidget
    buttonControlBox.addWidget(btn)

    btn = Button({"isWeightExpand": True, "isFillAlign": False, "ignoreParentExpand": True,})
    btn.win = self.win
    btn.label = "Remove"
    btn._clicked = self._rmDataWidget
    buttonControlBox.addWidget(btn)
    return (widget, buttonControlBox,)

  @property
  def initData(self):
    return [i.initData() for i in self._dataWidgetLst]

  @property
  def changedData(self):
    return [i.changedData() for i in self._dataWidgetLst]

  @property
  def finalData(self):
    return [i.finalData() for i in self._dataWidgetLst]

class FilterFormLayout(BasePacker):
  def __init__(self, win, bxInput, attrs=None, *args, **kwargs):
    attrs = self._buildAttrs(\
        attrs, isContainerAFrame=False, isExpandMainContainer=True)
    super(FilterFormLayout, self).__init__(win, bxInput.obj, attrs)
    self.labelTitle = "Param Filter:"
    self.inputLst = []
    self.bxInput = bxInput

  def addInput(self, input):
    self.inputLst.append(input)

  def generate(self, *args, **kwargs):
    filterEntryBox = self._createContainer(
        {\
            "isHorizontal": True, \
            "isWeightExpand": False, \
            "isFillAlign": False, \
            "ignoreParentExpand": True,\
            "isContainerAFrame": False,\
        })
    filterEntryBox.generate()

    lb = Label({"isFillAlign": False, "isWeightExpand": False, "ignoreParentExpand": False})
    lb.win = self.win
    lb.attrs["initData"] = self.labelTitle
    filterEntryBox.addWidget(lb)

    en = Entry({"isFillAlign": False, "isWeightExpand": False, "ignoreParentExpand": False})
    en.win = self.win
    filterEntryBox.addWidget(en)

    self.inputContainer = self._createContainer({"isFillAlign": True, "isWeightExpand": True})
    self.inputContainer.generate()
    self.obj = self.inputContainer.obj
    self.filterEntryBox = filterEntryBox

  def postGenerate(self):
    for input in self.inputLst:
      self.inputContainer.addInput(input)
    self.bxInput.addInput(self.filterEntryBox)
    self.bxInput.addInput(self.inputContainer)
    self.filterEntryBox.postGenerate()
    self.inputContainer.postGenerate()
