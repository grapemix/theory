# -*- coding: utf-8 -*-
#!/usr/bin/env python
##### System wide lib #####
from abc import ABCMeta, abstractmethod
import copy
import json
import os

##### Theory lib #####
import theory.gui.etk.element
from theory.gui.util import LocalFileObject
from theory.utils import datetimeSafe, formats
from theory.utils.importlib import importClass

##### Theory third-party lib #####

##### Local app #####

##### Theory app #####

##### Misc #####

__all__ = (
    "HiddenInput", "StringInput", "TextInput", "NumericInput", "SelectBoxInput",
    "CheckBoxInput", "DateInput", "DateTimeInput", "TimeInput",
    "StringGroupFilterInput", "ModelValidateGroupInput", "FileselectInput",
    "EmbeddedInput", "ListInput", "DictInput", "FilterFormLayout",
    "FileSizeInput", "QueryIdInput",
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
    super(BasePacker, self).__init__()
    self.win = win
    self.bx = bx
    self.widgetLst = []
    self.isLocalized = True

    self.attrs = self._buildAttrs(\
        attrs, isContainerAFrame=True)
    #self.attrs = self._buildAttrs(attrs=attrs)

  def _createWidget(self, *args, **kwargs):
    widget = self.widgetClass(self.attrs)
    widget.win = self.win
    if "isFocusChgTrigger" in self.attrs and self.attrs["isFocusChgTrigger"]:
      widget._focusChanged = self.attrs["syncFormData"]
      widget._fieldName = self.attrs["fieldName"]
    elif "isContentChgTrigger" in self.attrs \
        and self.attrs["isContentChgTrigger"]:
      widget._contentChanged = self.attrs["syncFormData"]
      widget._fieldName = self.attrs["fieldName"]
    return (widget,)

  def _createContainer(self, attrs=None, *args, **kwargs):
    hBox = theory.gui.etk.element.Box(attrs)
    hBox.win = self.win
    if(not self.attrs["isContainerAFrame"]):
      hBox.bx = self.bx
    return hBox

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

  def valueFromDatadict(self, data, files, name):
    """
    Given a dictionary of data and this widget's name, returns the value
    of this widget. Returns None if it's not provided. Not used in this
    moment, will be used in the future.
    """
    return data.get(name, None)

class BaseFieldInput(BasePacker):
  def __init__(
      self,
      fieldSetter,
      fieldGetter,
      win,
      bx,
      attrs=None,
      *args,
      **kwargs
  ):
    self.fieldSetter = fieldSetter
    self.fieldGetter = fieldGetter
    super(BaseFieldInput, self).__init__(win, bx, attrs, *args, **kwargs)

class BaseLabelInput(BaseFieldInput):
  """This class is designed for a widget with a name label and some help text.
  The widget in here can be a container which contains other object. The
  widget should be warp by a main container. The parent should not have
  much control on the main container and all attr simply pass to the widget."""

  __metaclass__ = ABCMeta
  def __init__(
      self,
      fieldSetter,
      fieldGetter,
      win,
      bx,
      attrs=None,
      *args,
      **kwargs
  ):
    attrs = self._buildAttrs(
        attrs,
        isExpandMainContainer=False
    )
    super(BaseLabelInput, self).__init__(
      fieldSetter,
      fieldGetter,
      win,
      bx,
      attrs,
      *args,
      **kwargs
    )
    self.hasGenerate = False

  def _prepareInitData(self, data):
    return data

  def setupInstructionComponent(self):
    if(self.attrs["isContainerAFrame"]):
      self.initLabelMainContainerAsFrame()
    else:
      self.initLabelMainContainerAsTbl()

  def initLabelMainContainerAsFrame(self):
    if(self.attrs["isExpandMainContainer"]):
      fr = theory.gui.etk.element.Frame(
        {"isFillAlign": True, "isWeightExpand": True}
      )
    else:
      fr = theory.gui.etk.element.Frame(
        {"isFillAlign": False, "isWeightExpand": False}
      )
    fr.win = self.win
    fr.bx = self.bx
    self.mainContainer = fr
    helpLabel = theory.gui.etk.element.Label()
    helpLabel.win = self.win
    self.widgetLst.append(helpLabel)

  def initLabelMainContainerAsTbl(self):
    lb = theory.gui.etk.element.Label()
    lb.win = self.win
    self.widgetLst.append(lb)
    lb = theory.gui.etk.element.Label()
    lb.win = self.win
    self.widgetLst.append(lb)

    if(self.attrs["isExpandMainContainer"]):
      hBox = self._createContainer({"isFillAlign": False, "isWeightExpand": False})
    hBox.generate()
    self.mainContainer = hBox

  def generate(self, *args, **kwargs):
    if(self.attrs["isContainerAFrame"]):
      self.packAsFrame(self.title, self.help)
    else:
      self.packAsTbl(self.title, self.help)
    self.hasGenerate = True

  def packAsFrame(self, title, help):
    hBox = self._createContainer(attrs={"isFillAlign": True, "isWeightExpand": True})
    hBox.generate()
    self.mainContainer.content = hBox
    self.mainContainer.title = str(title)
    self.mainContainer.generate()

    self.widgetLst[-1].attrs["initData"] = str(help)

    widgetLst = list(self._createWidget())
    self.widgetLst = widgetLst + self.widgetLst

    for widget in self.widgetLst:
      hBox.addWidget(widget)
    hBox.postGenerate()
    self.mainContainer.postGenerate()

  def packAsTbl(self, title, help):
    hBox = self.mainContainer

    self.widgetLst[0].attrs["initData"] = str(title)
    self.widgetLst[-1].attrs["initData"] = str(help)

    widgetLst = self._createWidget()
    self.widgetLst = self.widgetLst[0] + widgetLst + self.widgetLst[1]
    #widget = self._createWidget()
    #self.widgetLst.insert(1, widget)

    for widget in self.widgetLst:
      hBox.addWidget(widget)
    hBox.postGenerate()

  def packInMainContainer(self):
    self.widgetLst = self._createWidget()
    #for widget in self.widgetLst:
    #  self.addWidget(widget)

  @property
  def initData(self):
    return self.attrs["initData"]

  def hide(self):
    self.mainContainer.hide()

  def show(self):
    self.mainContainer.show()

  def setFocus(self):
    self.widgetLst[0].setFocus()

  @abstractmethod
  def updateField(self):
    pass

  def reset(self, **kwargs):
    """ To redraw the theory.gui.etk.element when data got update"""
    for k, v in kwargs.items():
      kwargs[k] = self._prepareInitData(v)
    self.widgetLst[0].reset(**kwargs)

  def reFillLabel(self, txt):
    helpLabel = self.widgetLst[-1]
    helpLabel.reset(errData=txt)

class HiddenInput(BaseLabelInput):
  def generate(self, *args, **kwargs):
    pass

class StringInput(BaseLabelInput):
  widgetClass = theory.gui.etk.element.Entry
  lineBreak = "<br/>"

  def _getData(self):
    return self.widgetLst[0].finalData

  def updateField(self):
    self.fieldSetter({"finalData": self._getData()})

class TextInput(StringInput):
  lineBreak = "<br/>"
  def __init__(self, fieldSetter, fieldGetter, win, bx,
      attrs=None, *args, **kwargs):
    attrs = self._buildAttrs(
        attrs,
        isScrollable=True,
        isSingleLine=False,
        isExpandMainContainer=True
    )
    super(TextInput, self).__init__(
        fieldSetter,
        fieldGetter,
        win,
        bx,
        attrs,
        *args,
        **kwargs
    )

class NumericInput(StringInput):
  def __init__(
      self,
      fieldSetter,
      fieldGetter,
      win,
      bx,
      attrs=None,
      *args,
      **kwargs
  ):
    attrs = self._buildAttrs(attrs, isExpandMainContainer=False)
    super(NumericInput, self).__init__(
      fieldSetter,
      fieldGetter,
      win,
      bx,
      attrs,
      *args,
      **kwargs
    )

  def _prepareInitData(self, initData):
    return str(initData)

class FileSizeInput(NumericInput):
  def _prepareInitData(self, initData):
    try:
      return str(initData>>20) + "MB"
    except:
      return None

class SelectBoxInput(BaseLabelInput):
  """Assuming labels are unique."""
  widgetClass = theory.gui.etk.element.RadioBox

  def updateField(self):
    if self.hasGenerate:
      self.fieldSetter({"finalData": self.widgetLst[0].finalData})
    else:
      self.fieldSetter({"finalData": self.initData})

  #def _createWidget(self, *args, **kwargs):
  #  widgetLst = super(SelectBoxInput, self)._createWidget(*args, **kwargs)
  #  print widgetLst[0].objLst[-1]
  #  print dir(widgetLst[0].objLst[-1])
  #  return widgetLst

class CheckBoxInput(BaseLabelInput):
  widgetClass = theory.gui.etk.element.CheckBox

  def _createWidget(self, *args, **kwargs):
    hBox = self._createContainer({
      "isFillAlign": False,
      "isWeightExpand": False,
      "isHorizontal": True,
      })
    hBox.generate()

    for v in self.attrs["choices"]:
      (value, label) = v
      #(label, value) = v
      if self.attrs["initData"] is not None \
          and value in self.attrs["initData"]:
        widget = self.widgetClass({"initData": True, })
      else:
        widget = self.widgetClass()
      widget.value = value
      widget.win = self.win
      widget.label = str(label)
      hBox.addWidget(widget)
    return (hBox,)

  @property
  def changedData(self):
    pass

  def updateField(self):
    choices = []
    for child in self.widgetLst[0].widgetChildrenLst:
      if child.obj.state:
        choices.append(child.value)
    self.fieldSetter({"finalData": choices})

class FileselectInput(BaseLabelInput):
  widgetClass = theory.gui.etk.element.FileSelector

  def updateField(self):
    path = self.widgetLst[0].finalData
    if(path==""):
      if(self.attrs["initData"] is None):
        # file path has not been touched and no initData has been assigned
        path = None
      elif(
        "isFolderOnly" in self.attrs
        and self.attrs["isFolderOnly"]
      ):
        path = self.attrs["initData"]
      else:
        # file path has not been touched
        path = LocalFileObject(self.attrs["initData"])
    elif(
      "isFolderOnly" in self.attrs
      and self.attrs["isFolderOnly"]
    ):
      # Folder mode and we only want to return dir path
      pass
    else:
      # Encapsulate the file path into LocalFileObject for fileField
      path = LocalFileObject(path)
    self.fieldSetter({"finalData": path})

class DateInput(StringInput):
  widgetClass = theory.gui.etk.element.Entry

  def __init__(self, fieldSetter, fieldGetter, win, bx,
      attrs=None, *args, **kwargs):
    super(DateInput, self).__init__(
        fieldSetter,
        fieldGetter,
        win,
        bx,
        attrs,
        *args,
        **kwargs
    )
    if "format" in kwargs and kwargs["format"]:
      self.format = format
      self.manualFormat = True
    else:
      self.format = formats.getFormat('DATE_INPUT_FORMATS')[0]
      self.manualFormat = False

  def _prepareInitData(self, value):
    if self.isLocalized and not self.manualFormat:
      return formats.localizeInput(value)
    elif hasattr(value, 'strftime'):
      value = datetimeSafe.newDate(value)
      return value.strftime(self.format)
    return value

class DateTimeInput(StringInput):
  widgetClass = theory.gui.etk.element.Entry

  def __init__(self, fieldSetter, fieldGetter, win, bx,
      attrs=None, *args, **kwargs):
    super(DateTimeInput, self).__init__(
        fieldSetter,
        fieldGetter,
        win,
        bx,
        attrs,
        *args,
        **kwargs
    )
    if "format" in kwargs and kwargs["format"]:
      self.format = format
      self.manualFormat = True
    else:
      self.format = formats.getFormat('DATETIME_INPUT_FORMATS')[0]
      self.manualFormat = False

  def _prepareInitData(self, value):
    if self.isLocalized and not self.manualFormat:
      return formats.localizeInput(value)
    elif hasattr(value, 'strftime'):
      value = datetimeSafe.newDatetime(value)
      return value.strftime(self.format)
    return value

class TimeInput(StringInput):
  widgetClass = theory.gui.etk.element.Entry

  def __init__(self, fieldSetter, fieldGetter, win, bx,
      attrs=None, *args, **kwargs):
    super(TimeInput, self).__init__(
        fieldSetter,
        fieldGetter,
        win,
        bx,
        attrs,
        *args,
        **kwargs
    )
    if "format" in kwargs and kwargs["format"]:
      self.format = format
      self.manualFormat = True
    else:
      self.format = formats.getFormat('TIME_INPUT_FORMATS')[0]
      self.manualFormat = False

  def _prepareInitData(self, value):
    if self.isLocalized and not self.manualFormat:
      return formats.localizeInput(value)
    elif hasattr(value, 'strftime'):
      return value.strftime(self.format)
    return value

class StringGroupFilterInput(BaseLabelInput):
  #widgetClass = theory.gui.etk.element.ListModelValidator
  widgetClass = theory.gui.etk.element.ListValidator

  def __init__(
      self,
      fieldSetter,
      fieldGetter,
      win,
      bx,
      attrs=None,
      *args,
      **kwargs
  ):
    attrs = self._buildAttrs(attrs, initData=())
    super(StringGroupFilterInput, self).__init__(
      fieldSetter,
      fieldGetter,
      win,
      bx,
      attrs,
      *args,
      **kwargs
    )

  @property
  def changedData(self):
    return self.widgetLst[0].changedData

  def updateField(self):
    self.fieldSetter({"finalData": self.widgetLst[0].finalData})

class ModelValidateGroupInput(BaseLabelInput):
  widgetClass = theory.gui.etk.element.ListModelValidator

  def __init__(
      self,
      fieldSetter,
      fieldGetter,
      win,
      bx,
      attrs=None,
      *args,
      **kwargs
      ):
    attrs = self._buildAttrs(attrs, initData=(), isExpandMainContainer=True)
    super(ModelValidateGroupInput, self).__init__(
        fieldSetter,
        fieldGetter,
        win,
        bx,
        attrs,
        *args,
        **kwargs
        )

  @property
  def initData(self):
    return self.widgetLst[0].initData

  @property
  def changedData(self):
    return self.widgetLst[0].changedData

  def updateField(self):
    self.fieldSetter({\
        "finalData": self.widgetLst[0].finalData,
        "changedData":  self.changedData,
        })

class MultipleValueInput(BaseLabelInput):
  def _chooseWidgetClass(self):
    pass

  def _addDataWidget(self):
    pass

  def _rmDataWidget(self):
    pass

  def _createWidget(self):
    pass

class EmbeddedInput(BaseLabelInput):
  def __init__(self, fieldSetter, fieldGetter, embeddedFieldDict, win, bx,
      attrs=None, *args, **kwargs):
    self.fieldSetter = fieldSetter
    self.fieldGetter = fieldGetter
    self.embeddedFieldDict = embeddedFieldDict
    self._inputLst = []

    super(EmbeddedInput, self).__init__(
        fieldSetter, fieldGetter,
        win, bx, attrs, *args, **kwargs
    )

  def _createWidget(self):
    embeddedBox = self._createContainer({
        "isHorizontal": False,
        "isWeightExpand": True,
        "isFillAlign": True
    })
    embeddedBox.generate()


    widgetLst = [embeddedBox,]
    for fieldName, fieldObj in self.embeddedFieldDict.items():
      fieldObj.renderWidget(
          self.win,
          embeddedBox.obj,
          )

      input = fieldObj.widget
      if(input is not None):
        embeddedBox.addInput(input)

    return widgetLst

  def updateField(self):
    pass

class ListInput(BaseLabelInput):
  def __init__(self, fieldSetter, fieldGetter, win, bx, childFieldLst,
      addChildFieldFxn, removeChildFieldFxn, attrs=None, *args, **kwargs):
    attrs = self._buildAttrs(
        attrs,
        isExpandMainContainer=True,
        initData=()
    )

    self.fieldSetter = fieldSetter
    self.fieldGetter = fieldGetter
    self.addChildField = addChildFieldFxn
    self.removeChildField = removeChildFieldFxn

    self._inputLst = []
    self.childFieldLst = childFieldLst
    # Used to keep track of how many widget has been inserted each time for
    # widget addition
    self.numOfNewWidget = 2
    # Used to keep track of the index of each button belong to
    self.btnIdxMap = {}
    super(ListInput, self).__init__(
        fieldSetter, fieldGetter,
        win, bx, attrs, *args, **kwargs
    )

  def _addDataWidget(self, btn, btnHash):
    """Will be only called by generic widget."""
    idx = self.btnIdxMap[btnHash]

    for k, v in self.btnIdxMap.items():
      if(v>idx):
        self.btnIdxMap[k] += 1

    idx += 1

    newChildField = self.addChildField(None)
    widgetLst = self._createGenericWidget(newChildField, idx)

    startIdx = ( idx - 1 ) * self.numOfNewWidget + 1

    for i in range(self.numOfNewWidget - 1, -1, -1):
      widget = widgetLst[i]
      self.widgetLst.insert(startIdx, widget)

    self.mainContainer.content.insertAndGenerateWidget(startIdx , widgetLst)

  def _rmDataWidget(self, btn, btnHash):
    """Will be only called by generic widget."""
    idx = self.btnIdxMap[btnHash]
    startIdx = ( idx - 1 ) * self.numOfNewWidget + 1

    for i in range(startIdx, startIdx + self.numOfNewWidget):
      del self.widgetLst[startIdx]

    del self.btnIdxMap[btnHash]
    for k, v in self.btnIdxMap.items():
      if(v>idx):
        self.btnIdxMap[k] -= 1

    self.mainContainer.content.removeWidgetLst(
        startIdx, self.numOfNewWidget)
    self.removeChildField(startIdx / self.numOfNewWidget)

    self._postRmDataWidget(startIdx)

  def _postRmDataWidget(self, startIdx):
    del self._inputLst[startIdx/self.numOfNewWidget]

  def _createWidget(self):
    pass

  def _probeChildWidget(self, childFieldTemplate):
    self.widgetClass = childFieldTemplate.widget.widgetClass

    if(self.widgetClass==StringInput.widgetClass):
      if(hasattr(childFieldTemplate, "maxLen") \
          and childFieldTemplate.maxLen>20):
        self.widgetClass = TextInput.widgetClass
        self._createWidget = self._createLongStringWidget
        self.lineBreak = childFieldTemplate.widget.lineBreak
      else:
        self.widgetClass = theory.gui.etk.element.Multibuttonentry
        self._createWidget = self._createShortStringWidget
      self.isOverridedData = True
      del self.addChildField
      del self.removeChildField
    else:
      self._createWidget = self._initGenericWidget
      self.isOverridedData = False
      del self.fieldSetter
      del self.fieldGetter

  def _createShortStringWidget(self, *args, **kwargs):
    """The adding child mechanism is handled by the widget itself."""
    initDataLst = []
    if(len(self.childFieldLst)>0):
      tmpChildWidget = self.childFieldLst[0].widget(None, None, None, None)
    for field in self.childFieldLst:
      if(field.initData!="" or field.initData is not None):
        initDataLst.append(tmpChildWidget._prepareInitData(field.initData))

    defaultParam = {
        "isWeightExpand": True,
        "isFillAlign": True,
        "isSkipInstruction": True
    }

    if(len(initDataLst)>0):
      defaultParam["initData"] = initDataLst

    widget = self.widgetClass(defaultParam)
    widget.win = self.win
    self._inputLst.append(widget)
    return (widget, )

    #buttonControlBox = self._createContainer(
    #    {
    #      "isHorizontal": True,
    #      "isWeightExpand": False,
    #      "isFillAlign": False
    #    }
    #)
    #buttonControlBox.generate()

    #btn = theory.gui.etk.element.Button({"isWeightExpand": True, "isFillAlign": False, })
    #btn.win = self.win
    #btn.label = "Toggle Expand"
    #btn._clicked = lambda btn: mbe.expanded_set(not mbe.expanded_get())
    #buttonControlBox.addWidget(btn)

    #btn = theory.gui.etk.element.Button({"isWeightExpand": True, "isFillAlign": False, })
    #btn.win = self.win
    #btn.label = "Clear"
    #btn._clicked = lambda bt: widget.obj.clear()
    #buttonControlBox.addWidget(btn)
    #return (widget, buttonControlBox,)

  def _createLongStringWidget(self, *args, **kwargs):
    """The adding child mechanism is handled by the widget itself."""
    initDataLst = []
    for field in self.childFieldLst:
      if(field.initData!="" or field.initData is not None):
        initDataLst.append(field.initData)

    defaultParam = {
        "isScrollable": True,
        "isSingleLine": False,
        "isExpandMainContainer": True,
        "isWeightExpand": True,
        "isFillAlign": True,
        "isSkipInstruction": True
    }

    if(len(initDataLst)>0):
      defaultParam["initData"] = self.lineBreak.join(initDataLst)

    widget = self.widgetClass(defaultParam)
    widget.win = self.win
    self._inputLst.append(widget)

    return (widget,)

  def _initGenericWidget(self):
    widgetLst = [self._createGenericWidgetBtnControlBox(0, True),]
    for i, field in enumerate(self.childFieldLst):
      widgetLst.extend(self._createGenericWidget(field, i + 1))
    return widgetLst

  def _createGenericWidget(self, newChildField, idx):
    defaultParam = {
        "isWeightExpand": True,
        "isFillAlign": False,
        "isSkipInstruction": True
    }
    newChildField.renderWidget(self.win, None, defaultParam)
    input = newChildField.widget
    input.packInMainContainer()
    self._inputLst.append(input)

    buttonControlBox = self._createGenericWidgetBtnControlBox(idx)

    result = list(input.widgetLst)
    result.append(buttonControlBox)
    return result

  def _createGenericWidgetBtnControlBox(self, idx, isFirstBtn=False):
    buttonControlBox = self._createContainer({
        "isHorizontal": True,
        "isWeightExpand": False,
        "isFillAlign": False
    })
    buttonControlBox.generate()

    btn = theory.gui.etk.element.Button(
      {"isWeightExpand": True, "isFillAlign": False}
    )
    btn.win = self.win
    btn.label = "Add"
    btn._clicked = self._addDataWidget
    btnHash = hash(btn)
    btn._clickedData = btnHash
    self.btnIdxMap[btnHash] = idx
    buttonControlBox.addWidget(btn)

    if(not isFirstBtn):
      btn = theory.gui.etk.element.Button(
        {"isWeightExpand": True, "isFillAlign": False,}
      )
      btn.win = self.win
      btn.label = "Remove"
      btn._clicked = self._rmDataWidget
      btn._clickedData = btnHash
      buttonControlBox.addWidget(btn)

    return buttonControlBox

  def updateField(self):
    if(self.widgetClass == theory.gui.etk.element.Multibuttonentry):
      self.fieldSetter(
          {
            "finalData": self._inputLst[0].finalData,
          }
      )
    elif(self.widgetClass == TextInput.widgetClass):
      finalData = self._inputLst[0].finalData
      # For empty case
      if(finalData==""):
        finalData = []
      else:
        finalData = finalData.split("<br/>")
      self.fieldSetter(
          {
            "finalData": finalData,
          }
      )
    else:
      for idx in range(len(self._inputLst)):
        self._inputLst[idx].updateField()

  def reset(self, **kwargs):
    """ data should be in the format like:
      {
        "finalData": (1, 0),
        "choices": ((0, "False"), (1, "True")),
      }
    """
    kwargsKeys = kwargs.keys()
    widgetLstLen = len(self.widgetLst) - 2
    self._inputLst = []
    for i in range(widgetLstLen):
      del self.widgetLst[1]
    self.mainContainer.content.removeWidgetLst(1, widgetLstLen)
    widgetLst = self._createWidget()
    self.widgetLst = list(widgetLst) + self.widgetLst

    self.mainContainer.content.insertAndGenerateWidget(1 , widgetLst)

    if self.isOverridedData:
      # That means the widget is either for long or short sting which imply
      # we only have one widget and we don't have to slice data
      self._inputLst[0].reset(**kwargs)
    else:
      # slice data for each child widget
      for i, input in enumerate(self._inputLst):
        row = {}
        for k in kwargsKeys:
          if(len(kwargs[k])<=i):
            continue
          row[k] = kwargs[k][i]
        input.reset(**row)

class DictInput(ListInput):
  def __init__(self, fieldSetter, fieldGetter, win, bx, addChildFieldFxn,
      removeChildFieldFxn, childFieldPairLst, attrs=None, *args, **kwargs):
    attrs = self._buildAttrs(
        attrs,
        isExpandMainContainer=True,
        initData={}
        )
    self.addChildField = addChildFieldFxn
    self.removeChildField = removeChildFieldFxn
    self.isOverridedData = False
    self.childFieldPairLst = childFieldPairLst
    # Used to keep track of how many widget has been inserted each time for
    # widget addition
    self.numOfNewWidget = 3
    # Used to keep track of the index of each button belong to
    self.btnIdxMap = {}

    self._inputLst = []
    # We should call the __init__() of ListInput's parent because
    # widgetClass should not be changed even StringInput is used.
    super(ListInput, self).__init__(
        fieldSetter, fieldGetter, win, bx, attrs, *args, **kwargs)

  def _createWidget(self, *args, **kwargs):
    widgetBoxLst = [self._createGenericWidgetBtnControlBox(0, True),]
    i = 1
    for (keyField, valueField) in self.childFieldPairLst:
      widgetBoxLst.extend(self._createGenericWidget((keyField, valueField), i))
      i += 1
    return widgetBoxLst

  def _postRmDataWidget(self, startIdx):
    pass

  def _createGenericWidget(self, newChildField, idx):
    (keyField, valueField) = newChildField
    keyInputBox = self._createContainer(
        {
            "isHorizontal": True,
            "isWeightExpand": False,
            "isFillAlign": False,
        }
    )
    keyInputBox.generate()

    lb = theory.gui.etk.element.Label(
      {"isFillAlign": False, "isWeightExpand": False}
    )
    lb.win = self.win
    lb.attrs["initData"] = "Key:"
    keyInputBox.addWidget(lb)


    defaultParam = {
        "isWeightExpand": True,
        "isFillAlign": True,
        "isSkipInstruction": True,
        "initData": keyField.initData,
    }

    keyField.renderWidget(self.win, keyInputBox.obj, attrs=defaultParam)
    keyField.widget.widgetLst = list(keyField.widget._createWidget())
    self._inputLst.append(keyField.widget)

    keyInputBox.addWidget(keyField.widget.widgetLst[0])

    valueInputBox = self._createContainer(
        {
            "isHorizontal": True,
            "isWeightExpand": False,
            "isFillAlign": False,
        }
    )
    valueInputBox.generate()

    lb = theory.gui.etk.element.Label(
      {"isFillAlign": False, "isWeightExpand": False}
    )
    lb.win = self.win
    lb.attrs["initData"] = "Value:"
    valueInputBox.addWidget(lb)

    defaultParam = {
        "isWeightExpand": True,
        "isFillAlign": False,
        "isSkipInstruction": True,
        "initData": valueField.initData,
    }

    valueField.renderWidget(self.win, valueInputBox.obj, attrs=defaultParam)

    valueField.widget.widgetLst = list(valueField.widget._createWidget())
    self._inputLst.append(valueField.widget)
    valueInputBox.addWidget(valueField.widget.widgetLst[0])

    buttonControlBox = self._createGenericWidgetBtnControlBox(idx)
    return (keyInputBox, valueInputBox, buttonControlBox,)

  def _createGenericWidgetBtnControlBox(self, idx, isFirstBtn=False):
    buttonControlBox = self._createContainer(
        {
          "isHorizontal": True,
          "isWeightExpand": False,
          "isFillAlign": False
        })
    buttonControlBox.generate()

    btn = theory.gui.etk.element.Button(
      {"isWeightExpand": True, "isFillAlign": False}
    )
    btn.win = self.win
    btn.label = "Add"
    btn._clicked = self._addDataWidget
    btnHash = hash(btn)
    btn._clickedData = btnHash
    self.btnIdxMap[btnHash] = idx
    buttonControlBox.addWidget(btn)

    if(not isFirstBtn):
      btn = theory.gui.etk.element.Button(
        {"isWeightExpand": True, "isFillAlign": False,}
      )
      btn.win = self.win
      btn.label = "Remove"
      btn._clicked = self._rmDataWidget
      btn._clickedData = btnHash
      buttonControlBox.addWidget(btn)

    return buttonControlBox

  def reset(self, **kwargs):
    """ Always assume childFieldPairLst is consistent with initData and
    finalData. Data should be in the format like:
      {
        "finalData": OrderedDict(
            {"key": keyValue, "value: value"},
            {"key": keyValue, "value: value"},
        ),
      }
    """
    widgetLstLen = len(self.widgetLst) - 2
    for i in range(widgetLstLen):
      del self.widgetLst[0]
    self.mainContainer.content.removeWidgetLst(1, widgetLstLen)
    widgetLst = self._createWidget()
    self.widgetLst = widgetLst + self.widgetLst

    self.mainContainer.content.insertAndGenerateWidget(1 , widgetLst)

    # Unpack data and reset all child widget
    kwargsKeyLst = kwargs.keys()
    fieldNameDataKeyDict = {}

    keyLstToBeDel = []

    for i, k in enumerate(kwargsKeyLst):
      if(k.endswith("Data")):
        fieldNameDataKeyDict[k] = kwargs[k].keys()
        keyLstToBeDel.append(i)

    for i in keyLstToBeDel:
      del kwargsKeyLst[i]

    for i in range(len(self.childFieldPairLst)):
      idx = i * 2

      row = {}
      for k in kwargsKeyLst:
        row[k] = kwargs[k][idx]

      for fieldName, dataKey in fieldNameDataKeyDict.items():
        row[fieldName] = dataKey[i]

      keyInputBox = self.childFieldPairLst[i][0].widget
      keyInputBox.reset(**row)

      idx += 1
      row = {}

      for k in kwargsKeyLst:
        row[k] = kwargs[k][idx]

      for fieldName, dataKey in fieldNameDataKeyDict.items():
        row[fieldName] = kwargs[fieldName][dataKey[i]]

      valueInputBox = self.childFieldPairLst[i][1].widget
      valueInputBox.reset(**row)

class QueryIdInput(StringInput):
  def __init__(
      self,
      fieldSetter,
      fieldGetter,
      win,
      bx,
      attrs=None,
      *args,
      **kwargs
      ):
    attrs = self._buildAttrs(
        attrs,
        # For ModelChoiceField if isMultiple=False
        isMultiple=True,
    )
    super(QueryIdInput, self).__init__(
        fieldSetter,
        fieldGetter,
        win,
        bx,
        attrs,
        *args,
        **kwargs
    )

  def _prepareInitData(self, initData):
    self.rawInitData = initData
    if initData is None or len(initData)==0:
      self.finalData = ""
      return ""
    s = ""
    for i in initData:
      s += str(i) + ","
    self.finalData = s[:-1]
    return self.finalData

  def refreshData(self, idLst):
    entryWidget = self.widgetLst[0].widgetChildrenLst[0]

    # We should differentiate by isMultiple in here or in the actual
    # selection widget for better UI experience.
    finalData = ""
    for id in idLst:
      finalData += "," + str(id)

    self.finalData = finalData[1:]
    entryWidget.finalData = self.finalData

  def _createInstanceCallback(self, btn, dummy):
    from theory.gui.etk.terminal import Terminal
    terminal = Terminal()

    val = '{{"cmdName": "modelUpsert", "finalDataDict": {0}}}'.format(
        json.dumps({
          "appName": self.attrs['appName'],
          "modelName": self.attrs['mdlName'],
          "isInNewWindow": True,
        })
    )
    terminal._fireUiReq({"action": "runCmd", "val": val})

  def _selectInstanceCallback(self, btn, dummy):
    from theory.gui.etk.terminal import Terminal
    terminal = Terminal()
    spreadsheetBuilder = terminal.initSpreadSheetBuilder(
      self.attrs['appName'],
      self.attrs['mdlName'],
      False,
      [],
      1,
      500,
      None
    )
    selectedIdLst = spreadsheetBuilder.getSelectedIdLst()
    self.refreshData(selectedIdLst)

  def _createWidget(self, *args, **kwargs):
    hBox = self._createContainer(
        {"isFillAlign": False, "isWeightExpand": False, "isHorizontal": True, }
        )
    hBox.generate()

    widget = theory.gui.etk.element.Entry()
    widget.win = self.win
    widget.attrs["initData"] = self.initData
    hBox.addWidget(widget)

    vBox = self._createContainer({
      "isFillAlign": False,
      "isWeightExpand": False,
      "isHorizontal": False,
      "isShrink": True,
      })
    vBox.bx = hBox.obj
    vBox.generate()

    btn = theory.gui.etk.element.Button(
      {"isFillAlign": False, "isWeightExpand": False}
    )
    btn.win = self.win
    btn.label = u"+"
    btn.attrs["isShrink"] = True
    btn._clicked = self._createInstanceCallback
    vBox.addWidget(btn)

    btn = theory.gui.etk.element.Button(
      {"isFillAlign": False, "isWeightExpand": False}
    )
    btn.win = self.win
    btn.label = u"☷"
    btn.attrs["isShrink"] = True
    btn._clicked = self._selectInstanceCallback
    vBox.addWidget(btn)

    hBox.addWidget(vBox)
    return (hBox,)

  def updateField(self):
    try:
      entryWidget = self.widgetLst[0].widgetChildrenLst[0]
      if entryWidget.finalData != "":
        if self.attrs["isMultiple"]:
          queryset = [int(i) for i in entryWidget.finalData.split(",")]
        else:
          # For ModelChoiceField, we want to receive as int not list
          queryset = int(entryWidget.finalData.split(",")[0])
      else:
        queryset = None
    except (AttributeError, KeyError):
      queryset = self.rawInitData
    self.fieldSetter({"finalData": queryset})

class FilterFormLayout(BasePacker):
  def __init__(self, win, bxInput, attrs=None, *args, **kwargs):
    attrs = self._buildAttrs(
        attrs,
        isContainerAFrame=False,
        isExpandMainContainer=True
        )
    super(FilterFormLayout, self).__init__(win, bxInput.obj, attrs)
    if "unFocusFxn" in attrs:
      self.unFocusFxn = attrs["unFocusFxn"]
    self.labelTitle = "Param Filter:"
    self.inputLst = []
    self.bxInput = bxInput
    self.isJustStart = True

  def addInput(self, fieldName, input):
    self.inputLst.append((fieldName.lower(), input))

  def _filterField(self, en, dummyFieldName):
    if(self.isJustStart):
      self.isJustStart = False
      return

    requestFieldNamePrefix = en.entry_get()
    # Trie should be applied, but it is overkilled in this case.
    for (name, input) in self.inputLst:
      input.mainContainer.hide()
    for (name, input) in self.inputLst:
      if(name.startswith(requestFieldNamePrefix.lower())):
        input.mainContainer.show()

  def setFocusOnFilterEntry(self):
    # The first widget must be label and the second one will be the entry box
    self.filterEntryBox.widgetChildrenLst[1].setFocus()

  def generate(self, *args, **kwargs):
    filterEntryBox = self._createContainer(
        {
            "isHorizontal": True,
            "isWeightExpand": False,
            "isFillAlign": False,
        }
    )
    filterEntryBox.generate()

    lb = theory.gui.etk.element.Label(
      {"isFillAlign": False, "isWeightExpand": False}
    )
    lb.win = self.win
    lb.attrs["initData"] = self.labelTitle
    filterEntryBox.addWidget(lb)

    en = theory.gui.etk.element.Entry(
      {"isFillAlign": False, "isWeightExpand": False}
    )
    en.win = self.win
    en._contentChanged = self._filterField
    en._fieldName = None
    filterEntryBox.addWidget(en)

    self.inputContainer = self._createContainer(
        {
          "isFillAlign": True,
          "isWeightExpand": False
        }
    )
    self.inputContainer.generate()
    self.obj = self.inputContainer.obj
    self.filterEntryBox = filterEntryBox

  def postGenerate(self):
    # The reason to have another inputLst is because that when a input is
    # appended into self.inputLst, the mainContainer.obj was not generated.
    # Since the behaviour of copying complex object into a list in python is
    # copy by reference, the mainContainer.obj will remain None unless we
    # copy the input again.
    newInputLst = []
    self.inputLst.reverse()
    for (name, input) in self.inputLst:
      self.inputContainer.addInput(input)
      newInputLst.append((name, input))
    self.inputLst = newInputLst
    self.bxInput.addInput(self.filterEntryBox)
    self.bxInput.addInput(self.inputContainer)
    self.filterEntryBox.postGenerate()
    self.inputContainer.postGenerate()
    if(hasattr(self, "unFocusFxn")):
      self.bxInput.registerUnfocusFxn(self.unFocusFxn)
