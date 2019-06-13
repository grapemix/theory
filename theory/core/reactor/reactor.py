# -*- coding: utf-8 -*-
#!/usr/bin/env python
##### System wide lib #####
import json
import logging
import sys

##### Theory lib #####
from theory.apps.model import (
    Adapter,
    AdapterBuffer,
    AppModel,
    Command,
    Mood,
    )
from theory.core.bridge import Bridge
from theory.core.exceptions import ValidationError
from theory.core.reactor.autoCompleteMixin import AutoCompleteMixin
from theory.core.reactor.historyMixin import HistoryMixin
from theory.conf import settings
from theory.db import transaction
from theory.db.model import Q
from theory.gui import theory_pb2
from theory.gui import theory_pb2_grpc
from theory.gui.transformer.theoryJSONEncoder import TheoryJSONEncoder
from theory.gui.transformer.protoBufModelTblPaginator import ProtoBufModelTblPaginator
from theory.utils.importlib import importClass
from theory.utils.singleton import Singleton

##### Theory third-party lib #####

##### Local app #####

##### Theory app #####

##### Misc #####

__all__ = ('Reactor',)

class Reactor(
    theory_pb2_grpc.ReactorServicer,
    AutoCompleteMixin,
    HistoryMixin,
    metaclass=Singleton,
):
  """
  It should be in charge to handle the high level user interaction bewteen
  theory and user. And it should dedicated on the GUI part, but able to
  seperate with the logic from a specific toolkit. It is implemented into
  singleton pattern.
  """
  __metaclass__ = Singleton

  _moodName = settings.DEFAULT_MOOD
  paramForm = None
  formHasBeenCleared = False
  actionQ = []
  uiIdVsAdapterLst = {}
  paramFormCache = {}

  @property
  def moodName(self):
    return self._moodName

  @moodName.setter
  def moodName(self, moodName):
    self._moodName = moodName

  def __init__(self):
    self.logger = logging.getLogger("theory.usr")
    super(Reactor, self).__init__()

  #def _actionQGenerator(self):
  #  print "_actionQGenerator"
  #  for action in self.actionQ:
  #    print action
  #    yield theory_pb2.ReactorReq(**action)
  #  if self.cmdModel.runMode == Command.RUN_MODE_ASYNC:
  #    self.asyncEvt.wait()
  #    print "_notificationGeneratora active"
  #    yield theory_pb2.ReactorReq(
  #        action="getNotify",
  #        val=str("test"),
  #        )

  def register(self, request, context):
    return self._dumpActionQ()

    #while True:
    #  if len(self.actionQ) > 0:
    #    action = self.actionQ.pop(0)
    #    yield theory_pb2.ReactorReq(**action)
    #  else:
    #    print "register sleep"
    #    gevent.sleep(1)
    #    print "register wake

  def _dumpActionQ(self):
    r = []
    while len(self.actionQ) > 0:
      action = self.actionQ.pop(0)
      r.append(theory_pb2.ReactorReq(**action))
    return theory_pb2.ReactorReqArr(reqLst=r)

  def _packGrpcJsonData(self, val):
    try:
      jsonData = json.dumps(val, cls=TheoryJSONEncoder)
    except Exception as e: # eval can throw many different errors
      self.logger.error(e, exc_info=True)
      raise ValidationError(str(e))

    return theory_pb2.JsonData(jsonData=jsonData)

  def bye(self, request, context):
    sys.exit(0)

  def getMdlTbl(self, request, context):
    protoBufModelTblPaginator = ProtoBufModelTblPaginator()
    dataComplex = protoBufModelTblPaginator.run(
        request.mdl.appName,
        request.mdl.mdlName,
        request.pageNum,
        request.pageSize
    )
    return theory_pb2.SpreadSheetData(**dataComplex)

  def upsertModelLst(self, request, context):
    msg = ""
    try:
      with transaction.atomic():
        for modelLstData in request.modelLstData:
          msg += "=== {} - {} ===\n".format(
            modelLstData.appName,
            modelLstData.mdlName
          )

          modelModel = AppModel.objects.get(
              app=modelLstData.appName,
              name=modelLstData.mdlName
              )
          modelKls = importClass(modelModel.importPath)

          for modelData in modelLstData.jsonDataLst:
            modelData = json.loads(modelData)
            modelDataWoM2m = {}
            m2mKeyLst = []
            for k, v in modelData.items():
              if k.endswith('__m2m'):
                m2mKeyLst.append(k)
              elif isinstance(v, dict) and len(v) == 0:
                # This special case is for HStoreField. May be it is a bug.
                # HStoreField can not store an empty dict
                continue
              else:
                modelDataWoM2m[k] = v
            if "id" in modelData:
              modelKls.objects.filter(id=modelData["id"]).update(
                **modelDataWoM2m
              )
              if len(m2mKeyLst) > 0:
                instance = modelKls.objects.get(id=modelData["id"])
            else:
              instance = modelKls(**modelDataWoM2m)
              instance.save()

            if len(m2mKeyLst) > 0:
              for k in m2mKeyLst:
                if modelData[k] is not None:
                  getattr(instance, k[:-5]).add(*modelData[k])
          msg += "Status: success\n"
          msg += "Msg: {0} models have been saved\n".format(
            len(modelLstData.jsonDataLst)
          )
    except Exception as e:
      self.logger.error(e, exc_info=True)
      msg += "Status: err\n"
      msg += "Msg: {}\n".format(str(e))

    self.actionQ.append({
        "action": "printStdOut",
        "val": msg,
        })
    return self._dumpActionQ()

  def syncFormData(self, request, context):
    """
    Being called when a user change a field in a form. If the form registered
    a hook for a field of an event, this fxn will be called and data will be
    passed to the server, so the server can return a new set of data for the
    involved fields to the UI.
    """
    if request.cmdId in self.paramFormCache:
      paramForm = self.paramFormCache[request.cmdId]
    else:
      try:
        cmdModel = Command.objects.get(id=request.cmdId)
      except Exception as e:
        self.logger.error(e, exc_info=True)
        raise ValidationError(str(e))

      cmdKlass = importClass(cmdModel.classImportPath)
      paramForm = cmdKlass.ParamForm()

    try:
      val = json.loads(request.jsonData)
    except Exception as e: # eval can throw many different errors
      raise ValidationError(str(e))
    if hasattr(paramForm, "{0}ContentChgCallback".format(request.fieldName)):
      val = getattr(
          paramForm,
          "{0}ContentChgCallback".format(request.fieldName)
          )(val)
    elif hasattr(paramForm, "{0}FocusChgCallback".format(request.fieldName)):
      val = getattr(
          paramForm,
          "{0}FocusChgCallback".format(request.fieldName)
          )(val)
    else:
      val = {}

    return self._packGrpcJsonData(val)

  def callCmdSubFxn(self, request, context):
    try:
      cmdModel = Command.objects.get(id=request.cmdId)
    except Exception as e:
      self.logger.error(e, exc_info=True)
      raise ValidationError(str(e))

    cmdKlass = importClass(cmdModel.classImportPath)
    cmd = cmdKlass()
    val = getattr(cmd, request.fxnName)(**json.loads(request.jsonData))

    if type(val).__name__ == "ReactorReq":
      return val

    return self._packGrpcJsonData(val)

  def adaptFromUi(self, request, context):
    bridge = Bridge()
    try:
      adapterBufferModel = AdapterBuffer.objects.filter(
          id=request.adapterBufferModelId
          ).first()
      # for security reason
      if adapterBufferModel is not None:
        adapter = importClass(adapterBufferModel.adapter.importPath)()
        adapter.fromUi(
            json.loads(request.jsonData)
            )
      cmd = bridge.bridgeFromUIAdapter(adapterBufferModel, adapter)

      cmd = self.runCmd(cmd, adapterBufferModel.toCmd, self.actionQ)
      adapterBufferModel.delete()
    except Exception as e:
      self.logger.error(e, exc_info=True)
      raise ValidationError(str(e))
    return theory_pb2.JsonData(jsonData=request.jsonData)

  def call(self, request, context):
    if settings.DEBUG_LEVEL >= 10:
      self.logger.debug(f"reactor call {request.action}, {request.val}")
    elif settings.DEBUG_LEVEL > 5:
      if request.action not in ["escapeRequest", "autocompleteRequest"]:
        self.logger.debug(f"reactor call {request.action}, {request.val}")
    self.actionQ = []
    if request.action == "runCmd":
      self._parse(request.val)
    elif request.action == "showPreviousCmdRequest":
      self._showPreviousCmdRequest()
    elif request.action == "showNextCmdRequest":
      self._showNextCmdRequest()
    elif request.action == "escapeRequest":
      self._escapeRequest()
    elif request.action == "autocompleteRequest":
      self._autocompleteRequest(request.val)
    elif request.action == "restartTheory":
      self._restartTheory()
    return self._dumpActionQ()

  def _buildCmdForm(self, finalDataDict=None):
    val = (
      '{{'
      '"cmdId": {0}, '
      '"isFocusOnFirstChild": "true", '
      '"fieldNameVsDesc": {{'
    ).format(self.cmdModel.id)
    cmdParamForm = None
    for row in self.cmdModel.cmdFieldSet.exclude(param="").orderBy(
        "isOptional"
        ).values("name", "param"):
      param = json.loads(row["param"])
      if finalDataDict is not None and row["name"] in finalDataDict:
        param["initData"] = finalDataDict[row["name"]]
        if param["type"] == "ChoiceField" \
            and ("choices" not in param or len(param["choices"]) == 0):
          param["choices"] = [[param["initData"], param["initData"]]]
          if isinstance(param["choices"], set):
            param["choices"] = list(param["choices"])
          if len(param["dynamicChoiceLst"]) == 0:
            del param["dynamicChoiceLst"]
        row["param"] = json.dumps(param, cls=TheoryJSONEncoder)
      elif "dynamicChoiceLst" in param:
        if cmdParamForm is None:
          cmdParamFormKlass = importClass(
            self.cmdModel.classImportPath
          ).ParamForm
          cmdParamForm = cmdParamFormKlass()
        param["choices"] = getattr(
          cmdParamForm.fields[row["name"]],
          "dynamicChoiceLst"
        )
        if param["required"] and param["type"] == "ChoiceField" and (
            "initData" not in param or param["initData"] is None
        ):
          # Since data in dynamicChoiceLst is assumed being updated frequently,
          # initData is sometimes unable to know in advance.
          try:
            param["initData"] = list(param["choices"])[0][0]
          except IndexError as e:
            self.logger.error(f"Choice not found in {self.cmdModel}")
            raise ValidationError(str(e))
        del param["dynamicChoiceLst"]
        if isinstance(param["choices"], set):
          param["choices"] = list(param["choices"])
        row["param"] = json.dumps(param, cls=TheoryJSONEncoder)

      val += '"{name}": {param},'.format(**row)
    val = val[:-1]
    val += "}}"
    return val

  def _parse(self, data):
    data = json.loads(data)
    self.parser.cmdInTxt = data["cmdName"]
    self.parser.run()

    if(self._loadCmdModel()):
      self.processCmd(data["finalDataDict"])
    else:
      self.actionQ.append({
          "action": "printStdOut",
          "val": "Command '{0}' not found".format(data["cmdName"])
          })

  def _performDrums(self, cmd):
    debugLvl = settings.DEBUG_LEVEL
    bridge = Bridge()
    for adapterName, leastDebugLvl in cmd._drums.items():
      if leastDebugLvl <= debugLvl:
        (adapterModel, drum) = bridge.adaptFromCmd(adapterName, cmd)
        self.actionQ.extend(drum.render(None, None, None))
        self.formHasBeenCleared = True
    if not self.formHasBeenCleared \
        or self.cmdModel.runMode == Command.RUN_MODE_ASYNC:
      self.actionQ.append({
          "action": "printStdOut",
          "val": "Command '{0}' has been run".format(self.cmdModel.name)
          })

  def reset(self):
    self.parser.initVar()

    self.actionQ.append({
        "action": "restoreCmdLine",
        })
    self.cmdModel = None
    if self.paramForm is not None and not self.formHasBeenCleared:
      self.actionQ.append({
          "action": "cleanUpCrt",
          })
      self.formHasBeenCleared = False
    self.paramForm = None
    self.historyIndex = -1

  def _loadCmdModel(self):
    cmdName = self.parser.cmdName
    # should change for chained command
    try:
      self.cmdModel = Command.objects.get(
          Q(name=cmdName)
          & (Q(moodSet__name=self.moodName) | Q(moodSet__name="norm"))
      )
      self.parser.cmdInTxt = self.cmdModel.name
    except Command.DoesNotExist:
      return False
    return True

  def runCmd(self, cmd, cmdModel, actionQ):
    bridge = Bridge()
    if not bridge._executeCommand(cmd, cmdModel, actionQ):
      # TODO: integrate with std reactor error system
      self.logger.error(str(cmd.paramForm.errors), exc_info=True)
      self.actionQ.append({
          "action": "printStdOut",
          "val": str(cmd.paramForm.errors)
          })
      self.actionQ.append({
          "action": "restoreCmdLine",
          })

    self._performDrums(cmd)
    return cmd

  # TODO: refactor this function, may be with bridge
  def processCmd(self, finalDataDict):
    #cmd = bridge.getCmdComplex(self.cmdModel, [], finalDataDict)
    cmdKlass = importClass(self.cmdModel.classImportPath)
    cmd = cmdKlass()
    if self.cmdModel.id in self.paramFormCache:
      cmd.paramForm = self.paramFormCache[self.cmdModel.id]
    else:
      cmd.paramForm = cmdKlass.ParamForm()
    cmd.paramForm.fillFinalFields(self.cmdModel, [], finalDataDict)
    cmd.paramForm.isValid()

    cmd = self.runCmd(cmd, self.cmdModel, self.actionQ)

    if cmd.isSaveToHistory:
      try:
        self._updateHistory(cmd.paramForm.exportToHistory())
      except Exception as e:
        self.logger.error(e, exc_info=True)

    if self.cmdModel.id in self.paramFormCache:
      del self.paramFormCache[self.cmdModel.id]
    self.reset()
