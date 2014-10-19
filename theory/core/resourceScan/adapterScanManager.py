# -*- coding: utf-8 -*-
#!/usr/bin/env python
##### System wide lib #####
from mongoengine import *

##### Theory lib #####
from theory.conf import settings
from theory.core.resourceScan.adapterClassScanner import AdapterClassScanner
from theory.apps.model import Adapter

##### Theory third-party lib #####

##### Local app #####
from baseScanManager import BaseScanManager

##### Theory app #####

##### Misc #####

class AdapterScanManager(BaseScanManager):

  def scan(self):
    Adapter.objects.all().delete()
    for appImportName in self.paramList:
      adapterTemplate = Adapter(importPath=appImportName)
      o = AdapterClassScanner()
      o.adapterTemplate = adapterTemplate
      o.scan()
      for adapter in o.adapterList:
        adapter.save()
