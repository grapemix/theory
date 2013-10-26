# -*- coding: utf-8 -*-
#!/usr/bin/env python

##### System wide lib #####

##### Theory lib #####
from theory.gui.common.baseForm import (
    Form,
    FormBase,
    DeclarativeFieldsMetaclass,
    )
#from theory.gui.widget import *

##### Theory third-party lib #####

##### Local app #####
from widget import BasePacker, FilterFormLayout
from element import Button

##### Theory app #####

##### Misc #####

__all__ = ("Form", "CommandForm", "GuiForm")

class GuiFormBase(FormBase, BasePacker):
  def __init__(self, *args, **kwargs):
    super(GuiFormBase, self).__init__(*args, **kwargs)
    # We have to call the initialize fxn explicitly because the
    # BasePacker initialize fxn won't be executed if we only called
    # super().__init__(). We temporary set win and bx as None because
    # form in a Command does not always need to render.
    BasePacker.__init__(self, None, None, *args, **kwargs)
    self.firstRequiredInputIdx = -1

  def _changeFormWindowHeight(self, maxHeight):
    # TODO: fix this super ugly hack
    size = self.win.size
    fieldHeight = len(self.fields) * 100
    preferHeight = fieldHeight if(fieldHeight<maxHeight) else maxHeight

    if(size[0]<640 or size[1]<preferHeight):
      self.win.resize(640, preferHeight)

  def _createFormSkeleton(self, win, bx):
    self.win = win
    self.bx = bx
    self.formBx = self._createContainer()
    self.formBx.bx = self.bx
    self.formBx.generate()

  def generateForm(self, win, bx, unFocusFxn):
    self.unFocusFxn = unFocusFxn
    self._createFormSkeleton(win, bx)

    focusChgFxnNameTmpl = "{0}FocusChgCallback"
    contentChgFxnNameTmpl = "{0}ContentChgCallback"

    for name, field in self.fields.items():
      kwargs = {}
      focusChgFxnName = focusChgFxnNameTmpl.format(name)
      contentChgFxnName = contentChgFxnNameTmpl.format(name)
      if(hasattr(self, focusChgFxnName)):
        kwargs["focusChgFxn"] = getattr(self, focusChgFxnName)
      elif(hasattr(self, contentChgFxnName)):
        kwargs["contentChgFxn"] = getattr(self, contentChgFxnName)

      field.renderWidget(self.win, self.formBx.obj, attrs=kwargs)
      self.formBx.addInput(field.widget)

    self.formBx.postGenerate()
    self._changeFormWindowHeight(720)

  def generateFilterForm(self, win, bx, unFocusFxn):
    self.unFocusFxn = unFocusFxn
    self._createFormSkeleton(win, bx)
    optionalMenu = FilterFormLayout(
        self.win,
        self.formBx,
        {"unFocusFxn": self.unFocusFxn}
        )
    self.optionalMenu = optionalMenu

    i = 0
    focusChgFxnNameTmpl = "{0}FocusChgCallback"
    contentChgFxnNameTmpl = "{0}ContentChgCallback"

    for name, field in self.fields.items():
      kwargs = {}
      focusChgFxnName = focusChgFxnNameTmpl.format(name)
      contentChgFxnName = contentChgFxnNameTmpl.format(name)
      if(hasattr(self, focusChgFxnName)):
        kwargs["focusChgFxn"] = getattr(self, focusChgFxnName)
      elif(hasattr(self, contentChgFxnName)):
        kwargs["contentChgFxn"] = getattr(self, contentChgFxnName)

      if(field.required):
        field.renderWidget(self.win, self.formBx.obj, attrs=kwargs)
        self.formBx.addInput(field.widget)
        if(self.firstRequiredInputIdx==-1):
          self.firstRequiredInputIdx = i
      else:
        field.renderWidget(self.win, self.formBx.obj, attrs=kwargs)
        optionalMenu.addInput(name, field.widget)
      i += 1

    self.formBx.postGenerate()
    optionalMenu.generate()
    optionalMenu.postGenerate()
    self._changeFormWindowHeight(960)

  def destroy(self):
    self.formBx.obj.delete()
    del self.formBx

class StepFormBase(GuiFormBase):
  def _nextBtnClick(self):
    pass

  def generateStepControl(self, *args, **kwargs):
    self.stepControlBox = self._createContainer({"isHorizontal": True, "isWeightExpand": False})
    self.stepControlBox.bx = self.bx
    self.stepControlBox.generate()

    btn = Button()
    btn.win = self.win
    btn.bx = self.stepControlBox.obj
    btn.label = "Cancel"
    if(kwargs.has_key("cleanUpCrtFxn")):
      btn._clicked = kwargs["cleanUpCrtFxn"]
    self.stepControlBox.addWidget(btn)

    if(hasattr(self, "_backBtnClick")):
      btn = Button()
      btn.win = self.win
      btn.bx = self.stepControlBox.obj
      btn.label = "Back"
      btn._clicked = self._backBtnClick
      self.stepControlBox.addWidget(btn)

    btn = Button()
    btn.win = self.win
    btn.bx = self.stepControlBox.obj
    btn.label = "Next"
    btn._clicked = self._nextBtnClick
    self.stepControlBox.addWidget(btn)

    self.stepControlBox.postGenerate()

class CommandFormBase(StepFormBase):
  def _nextBtnClick(self):
    self._run()

  def _run(self):
    pass

  def focusOnTheFirstChild(self):
    if(self.firstRequiredInputIdx!=-1):
      self.fields.values()[self.firstRequiredInputIdx].widget.setFocus()
    elif(hasattr(self, "optionalMenu")):
      self.optionalMenu.setFocusOnFilterEntry()

class GuiForm(GuiFormBase):
  __metaclass__ = DeclarativeFieldsMetaclass

class StepForm(StepFormBase):
  __metaclass__ = DeclarativeFieldsMetaclass

class CommandForm(CommandFormBase):
  __metaclass__ = DeclarativeFieldsMetaclass
