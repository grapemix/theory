# -*- coding: utf-8 -*-
#!/usr/bin/env python
##### System wide lib #####
from collections import OrderedDict
import gevent
import grpc
import json
from math import pow
import notify2

##### Theory lib #####
from theory.gui import theory_pb2
from theory.gui import theory_pb2_grpc
from theory.gui.etk import getDbusMainLoop
from theory.gui.gtk.spreadsheet import SpreadsheetBuilder
from theory.gui.transformer import GtkSpreadsheetModelBSONDataHandler
from theory.utils.importlib import importClass

##### Theory third-party lib #####

##### Enlightenment lib #####

##### Local app #####

##### Theory app #####

##### Misc #####

__all__ = ("RpcTerminalMixin",)

class RpcTerminalMixin(object):
  """
  To provide interface to handle signal from reactor. And also
  to implement fxn related to paramForm and notification
  """
  paramForm = None

  def _fireUiReq(self, dict):
    self._handleReactorReq(self.stub.call(theory_pb2.ReactorReq(**dict)))

  def callReactor(self, fxnName, val):
    r = getattr(self.stub, fxnName)(val)
    return r

  def _registerToReactor(self):
    notify2.init('Theory', getDbusMainLoop())
    errAttemptCounter = -1
    while not self.shouldIDie:
      try:
        reactorReqArr = self.stub.register(theory_pb2.UiId(id="etkTerminal"))
        errAttemptCounter = 5
        self._handleReactorReq(reactorReqArr)
        # Instead of sleep big chunk of time which will block the dieTogether
        # feature, we should break it down into a short amount of time instead
        for i in range(60):
          gevent.sleep(1)
          if self.shouldIDie:
            return
      except grpc._channel._Rendezvous as e:
        if errAttemptCounter >= 3:
          raise e
        gevent.sleep(pow(2, int(errAttemptCounter)))
        errAttemptCounter += 0.5

  def dieTogether(self):
    try:
      self.stub.bye(theory_pb2.Empty())
    except:
      pass

  def _handleReactorReq(self, reactorReqArr):
    for resp in reactorReqArr.reqLst:
      #print resp.action, resp.val
      if resp.action in [
          "cleanUpCrt",
          "setCmdLine",
          "setAndSelectCmdLine",
          "restoreCmdLine",
          "printStdOut",
        ]:
        getattr(self, resp.action)(resp.val)
      elif resp.action == "selectCmdLine":
        start, end = resp.val.split(",")
        self.selectCmdLine(int(start), int(end))
      elif resp.action == "startAppUi":
        d = json.loads(resp.val)
        fxn = importClass(d["importPath"])
        fxn(d, self.callReactor)
      elif resp.action == "startAdapterUi":
        d = json.loads(resp.val)
        self.logger.info("Loading adapater UI: {0}".format(d["importPath"]))
        self.startAdapterUi(d)
      elif resp.action == "upsertSpreadSheet":
        d = json.loads(resp.val)
        d["parentSpreadSheetBuilder"] = None
        self.upsertSpreadSheet(**d)
      elif resp.action == "getNotify":
        n = notify2.Notification(
            "Done",
            resp.val,
            "notification-message-im"   # Icon name
            )
        n.show()
      elif resp.action == "buildParamForm":
        self.buildParamForm(resp.val)
      elif resp.action == "cleanParamForm":
        self.cleanParamForm(None, None)
      elif resp.action == "focusOnParamFormFirstChild":
        self.paramForm.focusOnTheFirstChild()

  def _runCmd(self):
    if self.paramForm is not None and self.paramForm.isValid():
      val = '{{"cmdName": "{0}", "finalDataDict": {1}}}'.format(
          self.lastEntry,
          self.paramForm.toJson()
          )
    else:
      val = '{{"cmdName": "{0}", "finalDataDict": {{}}}}'.format(
          self.lastEntry
          )

    self._fireUiReq({"action": "runCmd", "val": val})

  def syncFormData(self, cmdId, fieldName, jsonData):
    """
    Being called when a user change a field in a form. If the form registered
    a hook for a field of an event, this fxn will be called and data will be
    passed to the server, so the server can return a new set of data for the
    involved fields to the UI.
    """
    return self.stub.syncFormData(theory_pb2.FieldData(
      cmdId=cmdId,
      fieldName=fieldName,
      jsonData=jsonData
      )
    )

  def cleanParamForm(self, btn, dummy):
    self.paramForm.isLazy = False
    self.paramForm.fullClean()
    if self.paramForm.isValid():
      self._runCmd()
    else:
      # TODO: integrate with std reactor error system
      self.paramForm.showErrInFieldLabel()

  def upsertModelLst(self, btn, dummy):
    self.paramForm.isLazy = False
    self.paramForm.fullClean()

    if self.paramForm.isValid():
      jsonDataLst = self.paramForm.toModelForm()
      self.stub.upsertModelLst(theory_pb2.ModelLstData(
        appName=self.lastModel["appName"],
        modelName=self.lastModel["modelName"],
        jsonDataLst=[jsonDataLst]
        )
      )
      self.lastModel = {}
    else:
      # TODO: integrate with std reactor error system
      self.paramForm.showErrInFieldLabel()

  def initSpreadSheetBuilder(
      self,
      appName,
      mdlName,
      isEditable,
      selectedIdLst,
      parentSpreadSheetBuilder
  ):
    r = self.stub.getMdlTbl(
      theory_pb2.MdlTblReq(
        mdl=theory_pb2.MdlIden(
          appName=appName,
          mdlName=mdlName
        ),
        pageNum=1,
        pageSize=10,
      )
    )

    # To convert protobuf msg of dataLst back into python list
    mdlLst = [list(data.ListFields()[0][1]) for data in r.dataLst]
    fieldNameVsProp = []
    for i in r.fieldNameVsProp:
      row = (i.k, {})
      for k, v in i.v.iteritems():
        if k == "choices":
          v = json.loads(v)
        row[1][k] = v
      fieldNameVsProp.append(row)
    fieldNameVsProp = OrderedDict(fieldNameVsProp)

    # Until we support custom protobuf interface for each model, we assume
    # all fields are being converted into str to avoid complicated protobuf
    # scheme
    # Special treatment for bool field
    for colNum, fieldProp in enumerate(fieldNameVsProp.values()):
      if fieldProp["type"] == "bool":
        for mdl in mdlLst:
          mdl[colNum] = True if mdl[colNum] == "1" else False

    spreadsheetBuilder = SpreadsheetBuilder()
    spreadsheet = spreadsheetBuilder.run(
        appName,
        mdlName,
        mdlLst,
        fieldNameVsProp,
        isEditable,
        selectedIdLst,
        self.upsertSpreadSheet,
        )

    if parentSpreadSheetBuilder is not None:
      parentSpreadSheetBuilder.addChild(spreadsheetBuilder)

    spreadsheetBuilder.showWidget(
      True if parentSpreadSheetBuilder is None else False
    )
    return spreadsheetBuilder

  def upsertSpreadSheet(
      self,
      appName,
      mdlName,
      isEditable,
      selectedIdLst,
      parentSpreadSheetBuilder
  ):
    spreadsheetBuilder = self.initSpreadSheetBuilder(
      appName,
      mdlName,
      isEditable,
      selectedIdLst,
      parentSpreadSheetBuilder
    )

    if parentSpreadSheetBuilder is None:

      handlerFxn = GtkSpreadsheetModelBSONDataHandler()
      jsonDataLstLst = spreadsheetBuilder.getJsonDataLst(handlerFxn, [])
      for (appName, mdlName, jsonDataLst) in jsonDataLstLst:
        self.stub.upsertModelLst(theory_pb2.ModelLstData(
          appName=appName,
          modelName=mdlName,
          jsonDataLst=jsonDataLst,
          )
        )

  def callExtCmd(self):
    pass

  def buildParamForm(self, val):
    data = json.loads(val)
    cmdParamFormKlass = importClass("theory.gui.etk.form.CommandForm")
    self.paramForm = cmdParamFormKlass()
    if "nextFxn" not in data:
      self.paramForm._nextBtnClick = self.cleanParamForm
    elif data["nextFxn"] == "upsertModelLst":
      self.paramForm._nextBtnClick = self.upsertModelLst
      self.lastModel = {
          "appName": data["appName"],
          "modelName": data["modelName"],
          }

    filterFormParam = self._getFilterFormUi()
    filterFormParam.update({
      "cmdId": data["cmdId"],
      "fieldNameVsDesc": data["fieldNameVsDesc"],
      "syncFormDataFxn": self.syncFormData,
      "callExtCmdFxn": self.callExtCmd,
      "_cleanUpCrtFxn": self.cleanUpCrt,
    })
    self.paramForm.generateFilterForm(**filterFormParam)
    self.paramForm.generateStepControl(_cleanUpCrtFxn=self.cleanUpCrt)

  def start(self):
    channel = grpc.insecure_channel('localhost:50051')
    self.stub = theory_pb2_grpc.ReactorStub(channel)
    gevent.joinall(
        [
          gevent.spawn(self._drawAll),
          gevent.spawn(self._registerToReactor),
        ]
    )
