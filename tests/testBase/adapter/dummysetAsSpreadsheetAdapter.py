# -*- coding: utf-8 -*-
#!/usr/bin/env python
##### System wide lib #####

##### Theory lib #####
from theory.adapter.querysetAsSpreadsheetAdapter import \
    QuerysetAsSpreadsheetAdapter
from theory.gui.gtk.spreadsheet import SpreadsheetBuilder

##### Theory third-party lib #####

##### Local app #####

##### Theory app #####

##### Misc #####

__all__ = ('DummysetAsSpreadsheetAdapter',)

class DummySpreadsheetBuilder(SpreadsheetBuilder):

  def _showWidget(
      self,
      listStoreDataType,
      gtkDataModel,
      renderKwargsSet,
      isMainSpreadsheet
      ):
    self.gtkDataModel = gtkDataModel

  def getSelectedRow(self):
    return range(len(self.gtkDataModel))

  def getDataModel(self):
    return self.gtkDataModel

class DummysetAsSpreadsheetAdapter(QuerysetAsSpreadsheetAdapter):
  def _getSpreadsheetBuilder(self):
    return DummySpreadsheetBuilder()
