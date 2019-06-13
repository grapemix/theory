# -*- coding: utf-8 -*-
#!/usr/bin/env python
##### System wide lib #####

##### Theory lib #####
from theory.conf import settings
from theory.core.resourceScan.adapterClassScanner import (
  AdapterClassScanner
)
from theory.core.resourceScan.baseScanManager import BaseScanManager
from theory.apps.model import Adapter

##### Theory third-party lib #####

##### Local app #####

##### Theory app #####

##### Misc #####

class AdapterScanManager(BaseScanManager):
  def drop(self, app=None):
    if app is None:
      Adapter.objects.all().delete()
    else:
      Adapter.objects.filter(
          importPath__startswith=app + ".adapter"
          ).delete()

  def scan(self):
    for appImportName in self.paramList:
      adapterTemplate = Adapter(importPath=appImportName)
      o = AdapterClassScanner()
      o.adapterTemplate = adapterTemplate
      o.scan()
      for adapter in o.adapterList:
        adapter.save()
