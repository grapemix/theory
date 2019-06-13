# -*- coding: utf-8 -*-
#!/usr/bin/env python
##### System wide lib #####
from collections import OrderedDict
import json

##### Theory lib #####
from theory.apps.command.baseCommand import SimpleCommand, AsyncCommand
from theory.apps.model import Command, CmdField
from theory.conf import settings
from theory.gui.transformer.theoryJSONEncoder import TheoryJSONEncoder

##### Theory third-party lib #####

##### Local app #####
from .baseClassScanner import BaseClassScanner

##### Theory app #####

##### Misc #####

class CommandClassScanner(BaseClassScanner):
  @property
  def cmdModel(self):
    return self._cmdModel

  @cmdModel.setter
  def cmdModel(self, cmdModel):
    self._cmdModel = cmdModel

  def _loadCommandClass(self):
    """
    Given a command name and an application name, returns the Command
    class instance. All errors raised by the import process
    (ImportError, AttributeError) are allowed to propagate.
    """
    module = self._loadSubModuleCommandClass(
      self.cmdModel.app,
      "command",
      self.cmdModel.name
    )
    return module

  def saveModel(self):
    # We already save model in scan() and we probably should rm this fxn in the
    # future
    pass

  def getParmFormFieldDesc(self, field, row):
    optionalParamLst = [
      "maxLen",
      "minLen",
      "uiPropagate",
      "appName",
      "mdlName"
    ]
    for i in [
        'helpText',
        'initData',
        'label',
        'localize',
        'required',
        'showHiddenInitial',
        'queryset',
        'errorMessages',
        'choices',
        'dynamicChoiceLst',
        'childFieldTemplate',
        'childKeyFieldTemplate',
        'childValueFieldTemplate',
        'uiPropagate',
        'maxLen',
        'minLen',
        'appName',
        'mdlName',
        ]:
      if hasattr(field, i):
        val = getattr(field, i)
        if (
            (val is None or val == "" or val == 0 or val == {})
            and i in optionalParamLst
        ):
          continue
        elif isinstance(val, dict):
          # for errorMessages
          newDict = {}
          for k, v in val.items():
            if type(v).__name__ == "__proxy__":
              newDict[k] = str(v)
          if len(newDict) > 0:
            val = newDict
        elif i == "childFieldTemplate":
          val = type(val).__name__
        elif i == "childKeyFieldTemplate":
          val = type(val).__name__
        elif i == "childValueFieldTemplate":
          val = type(val).__name__
        elif i == "dynamicChoiceLst":
          if val is None:
            # Choice field and its descendant will have dynamicChoiceLst and set
            # as None by default. We don't want to store it unless
            # dynamicChoiceLst has been actually in use because we will override
            # choices by dynamicChoiceLst
            continue
          # Since the val has to freshly generate everytime, stored val should
          # be empty
          val = ""
        row[i] =  val
    return row

  def geneateModelFormFieldDesc(self, form):
    # modelUpsert use this fxn
    r = OrderedDict()
    # If baseFields are used, then the modelForm won't get field value
    for fieldName, field in form.fields.items():
      row = {
          "type": type(field).__name__,
          "widgetIsFocusChgTrigger": False,
          "widgetIsContentChgTrigger": False
          }
      if type(field).__name__ == "HStoreField":
        row["type"] = "DictField"
        row["childKeyFieldTemplate"] = "CharField"
        row["childValueFieldTemplate"] = "CharField"
      r[fieldName] = self.getParmFormFieldDesc(field, row)
    return r

  def addParmFormFieldLst(self, form):
    focusChgFxnNameTmpl = "{0}FocusChgCallback"
    contentChgFxnNameTmpl = "{0}ContentChgCallback"

    for fieldName, field in form.baseFields.items():
      if(field.required):
        cmdField = CmdField(name=fieldName, isOptional=False)
      else:
        cmdField = CmdField(name=fieldName)
      focusChgFxnName = focusChgFxnNameTmpl.format(fieldName)
      contentChgFxnName = contentChgFxnNameTmpl.format(fieldName)

      row = {
          "type": type(field).__name__,
          "widgetIsFocusChgTrigger": \
              True if hasattr(form, focusChgFxnName) else False,
          "widgetIsContentChgTrigger": \
              True if(hasattr(form, contentChgFxnName)) else False
          }

      row = self.getParmFormFieldDesc(field, row)
      cmdField.param = json.dumps(row, cls=TheoryJSONEncoder)
      self.cmdModel.cmdFieldSet.add(cmdField)

  def scan(self):
    cmdFileClass = self._loadCommandClass()
    if (hasattr(cmdFileClass, "ABCMeta")
        or hasattr(cmdFileClass, "abstract")
        ):
      self._cmdModel = None
      return
    try:
      cmdClass = getattr(
          cmdFileClass,
          self.cmdModel.name[0].upper() + self.cmdModel.name[1:]
          )
      # Should add debug flag checking and dump to log file instead
    except AttributeError:
      self._cmdModel = None
      return

    if(issubclass(cmdClass, AsyncCommand)):
      self.cmdModel.runMode = self.cmdModel.RUN_MODE_ASYNC
    elif(not issubclass(cmdClass, SimpleCommand)):
      self.cmdModel.runMode = self.cmdModel.RUN_MODE_SIMPLE

    self.cmdModel.save()
    self.addParmFormFieldLst(cmdClass.ParamForm)

    # Class properties will be able to be captured and passed to adapter
    for k,v in cmdClass.__dict__.items():
      if(isinstance(v, property)):
        param = CmdField(name=k)
        if(getattr(getattr(cmdClass, k), "fset") is None):
          param.isReadOnly = True
        self.cmdModel.cmdFieldSet.add(param)
