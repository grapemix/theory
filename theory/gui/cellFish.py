#!/usr/bin/env python
##### System wide lib #####
import argparse
from collections import OrderedDict
import grpc
import gi
import json
# Have to be imported before notify2
from theory.gui.etk.widget import getDbusMainLoop
import notify2

##### Theory lib #####
from theory.conf import settings
from theory.thevent import gevent
from theory.gui import theory_pb2
from theory.gui import theory_pb2_grpc
from theory.gui.gtk.spreadsheet import SpreadsheetBuilder
from theory.gui.transformer import GtkSpreadsheetModelBSONDataHandler

##### Theory third-party lib #####

##### Enlightenment lib #####

##### Local app #####

##### Theory app #####

##### Misc #####


parser = argparse.ArgumentParser()
def check_positive(value):
  ivalue = int(value)
  if ivalue <= 0:
    raise argparse.ArgumentTypeError("%s is an invalid positive int value" % value)
  return ivalue

parser.add_argument('cmd', choices=["edit", "select"])
parser.add_argument('appName')
parser.add_argument('mdlName')
parser.add_argument('--pageNum', nargs='?', default=1, type=check_positive)
parser.add_argument('--pageSize', type=int, nargs='?', default=500, choices=range(500, 99999), metavar="{500..99999}")
parser.add_argument('--verbosity', type=int, nargs='?', default=1, choices=range(1, 99), metavar="{1..99}")
parser.add_argument("--queryset", nargs="+", type=str, const=None)


class CellFishClient:
  shouldIDie = False
  DEBUG_LEVEL = 0

  def __init__(self, cmd, appName, mdlName, pageNum, pageSize, verbosity, queryset):
    self.cmd = cmd
    self.appName = appName
    self.mdlName = mdlName
    self.pageNum = pageNum
    self.pageSize = pageSize
    self.verbosity = verbosity
    self.queryset = queryset

  def dieTogether(self):
    try:
      self.stub.bye(theory_pb2.Empty())
    except:
      pass

  def _fireUiReq(self, payload):
    if self.DEBUG_LEVEL >= 10:
      if not hasattr(self, "logger"):
        import logging
        self.logger = logger.getLogger("theory.internal")
      self.logger.debug(f"RpcTerminalMixin _fireUiReq {payload}")
    self._handleReactorReq(self.stub.call(theory_pb2.ReactorReq(**payload)))


  def _editData(self):
    notify2.init('Theory', getDbusMainLoop())
    errAttemptCounter = -1
    self._fireUiReq({
      "action": "runCmd",
      "val": json.dumps(
        {
          "cmdName": "modelTblEdit",
          "finalDataDict": {
            "pageNum": self.pageNum,
            "verbosity": self.verbosity,
            "queryset": self.queryset,
            "pageSize": self.pageSize,
            "appName": self.appName,
            "modelName": self.mdlName,
            "queryFilter": {}
          }
        }
      )
    })

    try:
      reactorReqArr = self.stub.register(theory_pb2.UiId(id="cellFish"))
      errAttemptCounter = 5
      self._handleReactorReq(reactorReqArr)
    except grpc._channel._Rendezvous as e:
      if errAttemptCounter >= 3:
        raise e
      gevent.sleep(pow(2, int(errAttemptCounter)))
      errAttemptCounter += 0.5

  def start(self):
    channel = grpc.insecure_channel(settings.REACTOR_URI)
    self.stub = theory_pb2_grpc.ReactorStub(channel)

    if self.cmd == "edit":
      self._editData()
    elif self.cmd == "select":
      self.printSelectedIdLst(
        self.appName,
        self.mdlName,
        self.pageNum,
        self.pageSize,
      )
    else:
      raise NotImplementedError()

  def _handleReactorReq(self, reactorReqArr):
    for resp in reactorReqArr.reqLst:
      if self.DEBUG_LEVEL >= 10:
        if not hasattr(self, "logger"):
          import logging
          self.logger = logger.getLogger("theory.internal")
        self.logger.debug(
          f"RpcTerminalMixin _handleReactorReq {resp.action}, {resp.val}"
        )
      if resp.action == "upsertSpreadSheet":
        d = json.loads(resp.val)
        d["parentSpreadSheetBuilder"] = None
        self.upsertSpreadSheet(**d)
      elif resp.action == "printStdOut":
        n = notify2.Notification(
            "Done",
            resp.val,
            "notification-message-im"   # Icon name
            )
        n.show()

  #########################################
  def fetchMoreRow(self, appName, mdlName, pageNum, pageSize, boolIdxLst):
    r = self.stub.getMdlTbl(
      theory_pb2.MdlTblReq(
        mdl=theory_pb2.MdlIden(
          appName=appName,
          mdlName=mdlName
        ),
        pageNum=pageNum,
        pageSize=pageSize,
      )
    )
    mdlLst = [list(data.ListFields()[0][1]) for data in r.dataLst]
    for colNum in boolIdxLst:
      for mdl in mdlLst:
        mdl[colNum] = True if mdl[colNum] == "1" else False
    return mdlLst

  def initSpreadSheetBuilder(
      self,
      appName,
      mdlName,
      isEditable,
      selectedIdLst,
      pageNum,
      pageSize,
      parentSpreadSheetBuilder
  ):
    spData = {
      "appName": appName,
      "mdlName": mdlName,
      "pageNum": pageNum,
      "pageSize": pageSize,
      "boolIdxLst": [],
    }
    r = self.stub.getMdlTbl(
      theory_pb2.MdlTblReq(
        mdl=theory_pb2.MdlIden(
          appName=appName,
          mdlName=mdlName
        ),
        pageNum=spData["pageNum"],
        pageSize=spData["pageSize"],
      )
    )

    # To convert protobuf msg of dataLst back into python list
    mdlLst = [list(data.ListFields()[0][1]) for data in r.dataLst]
    fieldNameVsProp = []
    for i in r.fieldNameVsProp:
      row = (i.k, {})
      for k, v in i.v.items():
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
        spData["boolIdxLst"].append(colNum)
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
        spData,
        self.fetchMoreRow,
        self.upsertSpreadSheet,
        )

    if parentSpreadSheetBuilder is not None:
      parentSpreadSheetBuilder.addChild(spreadsheetBuilder)

    spreadsheetBuilder.showWidget(
      True if parentSpreadSheetBuilder is None else False
    )
    return spreadsheetBuilder

  def printSelectedIdLst(
      self,
      appName,
      mdlName,
      pageNum,
      pageSize,
  ):
    spreadsheetBuilder = self.initSpreadSheetBuilder(
      appName,
      mdlName,
      False,
      [],
      pageNum,
      pageSize,
      None
    )
    selectedIdLst = spreadsheetBuilder.getSelectedIdLst()
    print(",".join(selectedIdLst))

  def upsertSpreadSheet(
      self,
      appName,
      mdlName,
      isEditable,
      selectedIdLst,
      pageNum,
      pageSize,
      parentSpreadSheetBuilder
  ):
    spreadsheetBuilder = self.initSpreadSheetBuilder(
      appName,
      mdlName,
      isEditable,
      selectedIdLst,
      pageNum,
      pageSize,
      parentSpreadSheetBuilder
    )

    if parentSpreadSheetBuilder is None:
      handlerFxn = GtkSpreadsheetModelBSONDataHandler()
      jsonDataLstLst = spreadsheetBuilder.getJsonDataLst(handlerFxn, [])
      msg = ""
      modelLstData = []
      for (appName, mdlName, jsonDataLst) in jsonDataLstLst:
        modelLstData.append(
          theory_pb2.ModelLstData(
            appName=appName,
            mdlName=mdlName,
            jsonDataLst=jsonDataLst,
          )
        )
      reactorReqArr = self.stub.upsertModelLst(
        theory_pb2.MultiModelLstData(modelLstData=modelLstData)
      )
      self._handleReactorReq(reactorReqArr)

#########################################
# This script is indented to be called as individual script from Theory
# via Popen and check_output. This script can be also called via cli, just
# make sure theory's reactor is running.

args = parser.parse_args()
CellFishClient(
  args.cmd,
  args.appName,
  args.mdlName,
  args.pageNum,
  args.pageSize,
  args.verbosity,
  args.queryset,
).start()
