# -*- coding: utf-8 -*-
#!/usr/bin/env python
##### System wide lib #####
from collections import defaultdict

##### Theory lib #####
from theory.core.resourceScan.baseScanManager import BaseScanManager
from theory.core.resourceScan.modelClassScanner import (
  ModelClassScanner
)
from theory.apps.model import AppModel

##### Theory third-party lib #####

##### Local app #####

##### Theory app #####

##### Misc #####

class ModelScanManager(BaseScanManager):

  def _getLabelFromFieldParam(self, fieldParam):
    return "{0}|{1}".format(
        fieldParam.childParamLst.all()[0].data,
        fieldParam.childParamLst.all()[1].data
        )

  def _markCircular(self, rootLabel, fieldParam, parentLabelLst=[]):
    refLabel = self._getLabelFromFieldParam(fieldParam)
    if(refLabel==rootLabel):
      fieldParam.isCircular = True
      return True
    if(refLabel in parentLabelLst):
      return False
    elif refLabel in self.modelDepMap:
      isEitherOneCircular = False
      parentLabelLst.append(refLabel)
      for i in self.modelDepMap[refLabel]:
        r = self._markCircular(rootLabel, i, parentLabelLst)
      return False
    else:
      return False

  def drop(self, app=None):
    if app is None:
      AppModel.objects.all().delete()
    else:
      AppModel.objects.filter(
          app=app
          ).delete()

  def scan(self):
    self.modelDepMap = defaultdict(list)

    modelLst = []
    for appImportName in self.paramList:
      modelTemplate = AppModel(importPath=appImportName)
      o = ModelClassScanner()
      o.modelTemplate = modelTemplate
      o.modelDepMap = self.modelDepMap
      o.scan()
      modelLst.extend(o.modelList)

    for k, v in self.modelDepMap.items():
      for i in v:
        self._markCircular(k, i)

    for model in modelLst:
      model.save()
