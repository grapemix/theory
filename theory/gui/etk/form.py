# -*- coding: utf-8 -*-
#!/usr/bin/env python

##### System wide lib #####
from collections import OrderedDict

##### Theory lib #####
from theory.conf import settings
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

__all__ = ("Form", "CommandForm", "SimpleGuiForm", "FlexibleGuiForm")

class GuiFormBase(BasePacker):
  def _preFillFieldProperty(self):
    """It is used to prefill fields which depends on the fields'
    value. It will only be called in the __init__() and when the form
    needs another set of initData(e.x: when prefilling the history)."""
    pass

  def _changeFormWindowHeight(self, maxHeight):
    pass

  def fillInitData(self, initDataAsDict):
    """This is used for updating form and destroy all widget and past
    reference. It should be used when no previous fields and widgets
    can be reused and need reference to.
    """
    for fieldName, data in initDataAsDict.iteritems():
      try:
        self.fields[fieldName].initData = data
      except KeyError:
        pass

    # used to fill in other properties which depends on the
    # other field's initData
    self._preFillFieldProperty()

  def reFillInitData(self, initDataAsDict):
    """This fxn will not destroy any widgets, instead, it will just update it.
    It should be faster and allow previous reference to it.
    """
    for fieldName, data in initDataAsDict.iteritems():
      try:
        self.fields[fieldName].initData = data
        # To force widget to update in next time
        self.fields[fieldName].finalData = None
        self.fields[fieldName].widget.reset(
            initData=data,
            finalData=data # To force radio element to update
            )
      except KeyError:
        pass

    # used to fill in other properties which depends on the
    # other field's initData
    self._preFillFieldProperty()

  def generateForm(self, win, bx, unFocusFxn):
    pass

  def _createFormSkeleton(self, win, bx):
    self.win = win
    self.bx = bx

class FlexibleGuiFormBase(GuiFormBase):
  def __init__(self, *args, **kwargs):
    super(FlexibleGuiFormBase, self).__init__(None, None, None)
    #super(FlexibleGuiFormBase, self).__init__(*args, **kwargs)
    self.modelFieldNameLst = {}
    self.combineFieldNameVsModelField = {}
    self.modelCacheDict = {}

  def _generateCombineFieldName(self, modelName, fieldName):
    combineFieldName = modelName[0].lower() + modelName[1:] + \
        fieldName[0].upper() + fieldName[1:]

    self.combineFieldNameVsModelField[combineFieldName] = (modelName, fieldName)
    return combineFieldName

  def updateModelInOrderedDict(self):
    for modelName, fieldNameLst in self.modelFieldNameLst.iteritems():
      modelObj = self.modelCacheDict[modelName]
      for fieldName in fieldNameLst:
        combineFieldName = self._generateCombineFieldName(modelName, fieldName)
        formData = self.clean()
        if (formData.has_key(combineFieldName)
            and not isinstance(modelObj, (list, tuple))
            ):
          print formData[combineFieldName], getattr(modelObj, fieldName)

  def modelObjVsRelationToOrderedDict(self, modelObjVsRelation):
    r = OrderedDict()

    for modelObj, relation in modelObjVsRelation.iteritems():
      modelName = modelObj.__class__.__name__
      fieldNameLst = self.modelFieldNameLst[modelName]
      if(relation is not None):
        parentModelName, idFieldName = id.split(".")
        modelRef = r[parentModelName + idFieldName[0].upper() + idFieldName[1:]]
        self.modelCacheDict[modelName] = modelRef

        if(isinstance(modelRef, (list, tuple))):
          fieldVal = []
          for modelChildObj in modelRef:
            fieldVal.append(getattr(modelChildObj, fieldName))
          for fieldName in fieldNameLst:
            combineFieldName = self._generateCombineFieldName(modelName, fieldName)
            r[combineFieldName] = fieldVal
        elif(isinstance(modelRef, dict)):
          pass
        else:
          for fieldName in fieldNameLst:
            combineFieldName = self._generateCombineFieldName(modelName, fieldName)
            r[combineFieldName] = getattr(modelRef, fieldName)
      else:
        self.modelCacheDict[modelName] = modelObj
        for i, fieldName in enumerate(fieldNameLst):
          combineFieldName = self._generateCombineFieldName(modelName, fieldName)
          r[combineFieldName] = getattr(modelObj, fieldName)

    return r


  def getModelInOrderedDict(self, modelKlassVsId):
    r = OrderedDict()
    for modelKlass, id in modelKlassVsId.iteritems():
      modelName = modelKlass.__name__
      fieldNameLst = self.modelFieldNameLst[modelName]
      if("." in str(id)):
        parentModelName, idFieldName = id.split(".")
        modelRef = r[parentModelName + idFieldName[0].upper() + idFieldName[1:]]
        self.modelCacheDict[modelName] = modelRef

        # some bug in modelRef,
        if(isinstance(modelRef, (list, tuple))):
          fieldVal = []
          for modelObj in modelRef:
            fieldVal.append(getattr(modelObj, fieldName))
          for fieldName in fieldNameLst:
            combineFieldName = self._generateCombineFieldName(modelName, fieldName)
            r[combineFieldName] = fieldVal
        elif(isinstance(modelRef, dict)):
          pass
        else:
          for fieldName in fieldNameLst:
            combineFieldName = self._generateCombineFieldName(modelName, fieldName)
            r[combineFieldName] = getattr(modelRef, fieldName)
      else:
        modelObj = modelKlass.objects.only(*fieldNameLst).get(id=id)
        self.modelCacheDict[modelName] = modelObj
        for i, fieldName in enumerate(fieldNameLst):
          combineFieldName = self._generateCombineFieldName(modelName, fieldName)
          r[combineFieldName] = getattr(modelObj, fieldName)

    return r

  def _customRenderAndPackWidget(self, fieldName, field, kwargs):
    pass

  def generateForm(self, win, bx, unFocusFxn):
    self.unFocusFxn = unFocusFxn
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
      self._customRenderAndPackWidget(name, field, kwargs)

class SimpleGuiFormBase(GuiFormBase):
  def __init__(self, *args, **kwargs):
    super(SimpleGuiFormBase, self).__init__(self, None, None, *args, **kwargs)
    self.firstRequiredInputIdx = -1

  def _changeFormWindowHeight(self, maxHeight):
    size = self.win.size
    fieldHeight = len(self.fields) * settings.UI_FORM_FIELD_HEIGHT_RATIO
    preferHeight = fieldHeight if(fieldHeight<maxHeight) else maxHeight

    orgWidth = settings.dimensionHints["minWidth"] * 3 / 4
    self.win.resize(orgWidth, preferHeight)
    self.win.pos_set(self.win.pos[0], 0)

  def _createFormSkeleton(self, win, bx):
    super(SimpleGuiFormBase, self)._createFormSkeleton(win, bx)
    self.formBx = self._createContainer()
    self.formBx.bx = self.bx
    self.formBx.generate()

  def generateForm(self, win, bx, unFocusFxn, **kwargs):
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
      if(field.widget is not None):
        self.formBx.addInput(field.widget)

    self.formBx.postGenerate()
    self._changeFormWindowHeight(settings.dimensionHints["maxHeight"] - 200)

  def generateFilterForm(self, win, bx, unFocusFxn, **kwargs):
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
        if(field.widget is not None):
          optionalMenu.addInput(name, field.widget)
      i += 1

    self.formBx.postGenerate()
    optionalMenu.generate()
    optionalMenu.postGenerate()
    self._changeFormWindowHeight(settings.dimensionHints["maxHeight"])

  def showErrInFieldLabel(self):
    for fieldName, errMsg in self.errors.iteritems():
      self.fields[fieldName].widget.reFillLabel(errMsg)

class StepFormBase(SimpleGuiFormBase):
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

class GuiForm(FormBase, GuiFormBase):
  __metaclass__ = DeclarativeFieldsMetaclass

class SimpleGuiForm(FormBase, SimpleGuiFormBase):
  __metaclass__ = DeclarativeFieldsMetaclass

class FlexibleGuiForm(FormBase, FlexibleGuiFormBase):
  __metaclass__ = DeclarativeFieldsMetaclass

class StepForm(FormBase, StepFormBase):
  __metaclass__ = DeclarativeFieldsMetaclass

class CommandForm(FormBase, CommandFormBase):
  __metaclass__ = DeclarativeFieldsMetaclass
