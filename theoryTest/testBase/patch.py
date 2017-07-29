# -*- coding: utf-8 -*-
##### System wide lib #####

##### Theory lib #####
from theory.apps.model import AppModel
from theory.core.resourceScan.modelScanManager import ModelScanManager

##### Theory third-party lib #####

##### Local app #####

##### Theory app #####

##### Misc #####

def patchDumpdata():
  modelScanManager = ModelScanManager()
  modelScanManager.paramList = [
      "testBase.__init__",
      ]
  modelScanManager.scan()
