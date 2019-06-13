# -*- coding: utf-8 -*-
#!/usr/bin/env python
##### System wide lib #####
from collections import OrderedDict
import json

##### Theory lib #####
from theory.apps.model import AppModel
from theory.gui import theory_pb2
from theory.gui.transformer import TheoryModelBSONTblDataHandler
from theory.utils.importlib import importClass

##### Theory third-party lib #####

##### Local app #####

##### Theory app #####

##### Misc #####


class ProtoBufModelTblPaginator(TheoryModelBSONTblDataHandler):

  def _getAppMdl(self, appName, mdlName):
    return AppModel.objects.only("tblField", "importPath").get(
      app=appName,
      name=mdlName
    )

  # Until we support custom protobuf interface for each model, we assume
  # all fields are being converted into str to avoid complicated protobuf
  # scheme
  def _floatFieldDataHandler(self, rowId, fieldName, fieldVal):
    if fieldVal is None:
      return "0.0"
    return str(fieldVal)

  def _intFieldDataHandler(self, rowId, fieldName, fieldVal):
    if fieldVal is None:
      return "0"
    return str(fieldVal)

  def _boolFieldDataHandler(self, rowId, fieldName, fieldVal):
    return "1" if fieldVal else "0"

  def run(self, appName, mdlName, pageNum, pageSize):
    appModelMdl = self._getAppMdl(appName, mdlName)

    super(ProtoBufModelTblPaginator, self).run(
        appModelMdl.fieldParamMap.filter(parent__isnull=True)
        )

    bufSet = set(appModelMdl.tblField)
    self.fieldNameLst = []
    for fieldName in list(self.fieldNameVsProp.keys()):
      if fieldName not in bufSet:
        del self.fieldNameVsProp[fieldName]
      else:
        self.fieldNameLst.append(fieldName)

    mdlKls = importClass(appModelMdl.importPath)
    pageNum -= 1
    self.q1 = mdlKls
    queryset = mdlKls.objects.all()[
      pageNum * pageSize: (pageNum + 1) * pageSize
    ]
    self.q2 = queryset

    r = {"dataLst": []}
    for queryrow in list(queryset):
      row = []
      for fieldName in self.fieldNameLst:
        result = self.fieldNameVsHandlerDict[fieldName]["dataHandler"](
            id,
            fieldName,
            getattr(queryrow, fieldName)
            )
        if result is None:
          result = "None"
        row.append(result)
      try:
        r["dataLst"].append(theory_pb2.DataRow(cell=row))
      except Exception as e:
        import logging
        logger = logging.getLogger("theory.usr")
        logger.error(f"ProtoBufModelTblPaginator run: {row}")
        raise

    r["dataLst"] = r["dataLst"]
    if pageNum == 0:
      r["mdlTotalNum"] = mdlKls.objects.count()
      # Since protobuf does not support OrderedDict, in order to preserve order,
      # the gui should reconstrct the list to OrderedDict
      r["fieldNameVsProp"] = []
      for k, map in self.fieldNameVsProp.items():
        # That is mainly for choices which stores in dict instead of str,
        # and protobuf assume prop is map<string, string> type, so we have
        # to jsonize in here
        for keyInMap, v in map.items():
          if isinstance(v, dict):
            map[keyInMap] = json.dumps(v)
        r["fieldNameVsProp"].append(theory_pb2.StrVsMap(k=k, v=map))
    return r
