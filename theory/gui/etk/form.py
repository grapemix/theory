# -*- coding: utf-8 -*-
#!/usr/bin/env python

##### System wide lib #####
from collections import OrderedDict
import json

##### Theory lib #####
from theory.conf import settings
from theory.core.exceptions import ValidationError
from theory.gui.common.baseForm import (
    Form,
    FormBase,
    DeclarativeFieldsMetaclass,
    )
from theory.gui.transformer.theoryJSONEncoder import TheoryJSONEncoder
from theory.utils.importlib import importClass

##### Theory third-party lib #####

##### Local app #####
from widget import BasePacker, FilterFormLayout
from element import Button

##### Theory app #####

##### Misc #####

__all__ = ("Form", "CommandForm", "SimpleGuiForm", "FlexibleGuiForm")

class GuiFormBase(BasePacker):
  def _changeFormWindowHeight(self, maxHeight):
    pass

  def generateForm(self, win, bx, unFocusFxn):
    pass

  def _createFormSkeleton(self, win, bx):
    self.win = win
    self.bx = bx

  def reFillInitData(self, initDataAsDict):
    """This fxn will not destroy any widgets, instead, it will just update it.
    It should be faster and allow previous reference to it. Only useful for the
    reset button in the future.
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

    orgWidth = settings.DIMENSION_HINTS["minWidth"] * 3 / 4
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
    self._changeFormWindowHeight(settings.DIMENSION_HINTS["maxHeight"] - 200)

  def syncFormData(self, widgetElement, fieldName):
    val = self.fields[fieldName].clean(
        self.fields[fieldName].finalData
        )
    try:
      jsonData = json.dumps(val, cls=TheoryJSONEncoder)
    except Exception as e: # eval can throw many different errors
      import logging
      logger = logging.getLogger(__name__)
      logger.error(e, exc_info=True)
      raise ValidationError(str(e))
    self.fields[fieldName].finalData = None

    resp = self._syncFormData(self.cmdId, fieldName, jsonData)
    try:
      formData = json.loads(resp.jsonData)
    except Exception as e: # eval can throw many different errors
      import logging
      logger = logging.getLogger(__name__)
      logger.error(e, exc_info=True)
      raise ValidationError(str(e))

    for fieldName, attrNameVsAttr in formData.iteritems():
      # TODO: simplify this procedure later
      field = self.fields[fieldName]
      for attrName, attr in attrNameVsAttr.iteritems():
        setattr(field, attrName, attr)
        if attrName == "choices":
          field.widget.reset(choices=field.choices)

  def callExtCmd(self, widgetElement, appName, cmdName, val):
    pass

  def generateFilterForm(
      self,
      win,
      bx,
      unFocusFxn,
      cmdId,
      fieldNameVsDesc,
      syncFormDataFxn,
      callExtCmdFxn,
      **kwargs
      ):
    self._syncFormData = syncFormDataFxn
    self._callExtCmd = callExtCmdFxn
    self.cmdId = cmdId
    self.unFocusFxn = unFocusFxn
    self._createFormSkeleton(win, bx)
    optionalMenu = FilterFormLayout(
        self.win,
        self.formBx,
        {"unFocusFxn": self.unFocusFxn}
        )
    self.optionalMenu = optionalMenu

    i = 0
    for fieldName, fieldDesc in fieldNameVsDesc.iteritems():
      if fieldDesc["type"].startswith("Model"):
        fieldKlass = importClass(
            "theory.gui.model.{type}".format(**fieldDesc)
            )
      else:
        fieldKlass = importClass(
            "theory.gui.etk.field.{type}".format(**fieldDesc)
            )
      widgetKwargs = kwargs
      widgetKwargs["isFocusChgTrigger"] = fieldDesc["widgetIsFocusChgTrigger"]
      widgetKwargs["isContentChgTrigger"] = \
          fieldDesc["widgetIsContentChgTrigger"]
      if widgetKwargs["isFocusChgTrigger"] or widgetKwargs["isContentChgTrigger"]:
        widgetKwargs["syncFormData"] = self.syncFormData
        widgetKwargs["fieldName"] = fieldName
      del fieldDesc["widgetIsFocusChgTrigger"]
      del fieldDesc["widgetIsContentChgTrigger"]
      if fieldDesc["type"] == "ListField":
        fieldDesc["field"] = importClass(
            "theory.gui.etk.field.{childFieldTemplate}".format(**fieldDesc)
            )()
        del fieldDesc["childFieldTemplate"]
      if fieldDesc["type"] == "DictField":
        fieldDesc["keyField"] = importClass(
            "theory.gui.etk.field.{childKeyFieldTemplate}".format(**fieldDesc)
            )()
        fieldDesc["valueField"] = importClass(
            "theory.gui.etk.field.{childValueFieldTemplate}".format(**fieldDesc)
            )()
        del fieldDesc["childKeyFieldTemplate"]
        del fieldDesc["childValueFieldTemplate"]
      del fieldDesc["type"]
      fieldDesc["getSibilingFieldData"] = self.getSibilingFieldData
      field = fieldKlass(**fieldDesc)
      self.fields[fieldName] = field
      if(field.required):
        field.renderWidget(self.win, self.formBx.obj, attrs=widgetKwargs)
        self.formBx.addInput(field.widget)
        if(self.firstRequiredInputIdx==-1):
          self.firstRequiredInputIdx = i
      else:
        field.renderWidget(self.win, self.formBx.obj, attrs=widgetKwargs)
        if(field.widget is not None):
          optionalMenu.addInput(fieldName, field.widget)
      i += 1

    self.formBx.postGenerate()
    optionalMenu.generate()
    optionalMenu.postGenerate()
    self._changeFormWindowHeight(settings.DIMENSION_HINTS["maxHeight"])

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
      btn._clickedData = self
    self.stepControlBox.addWidget(btn)

    if(hasattr(self, "_backBtnClick")):
      btn = Button()
      btn.win = self.win
      btn.bx = self.stepControlBox.obj
      btn.label = "Back"
      btn._clicked = self._backBtnClick
      btn._clickedData = self
      self.stepControlBox.addWidget(btn)

    btn = Button()
    btn.win = self.win
    btn.bx = self.stepControlBox.obj
    btn.label = "Next"
    btn._clicked = self._nextBtnClick
    btn._clickedData = self
    self.stepControlBox.addWidget(btn)

    self.stepControlBox.postGenerate()

class CommandFormBase(StepFormBase):
  def _nextBtnClick(self, *args, **kwargs):
    self._run(*args, **kwargs)

  def _run(self, *args, **kwargs):
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
