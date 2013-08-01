# -*- coding: utf-8 -*-
#!/usr/bin/env python
##### System wide lib #####

##### Theory lib #####
from theory.core.resourceScan.modelClassScanner import ModelClassScanner
from theory.model import AppModel

##### Theory third-party lib #####

##### Local app #####
from baseScanManager import BaseScanManager

##### Theory app #####

##### Misc #####

class ModelScanManager(BaseScanManager):

  def scan(self):
    AppModel.objects.all().delete()
    for appImportName in self.paramList:
      modelTemplate = AppModel(importPath=appImportName)
      o = ModelClassScanner()
      o.modelTemplate = modelTemplate
      o.scan()
      for model in o.modelList:
        model.save()
