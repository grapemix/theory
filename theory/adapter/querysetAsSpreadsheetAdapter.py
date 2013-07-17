# -*- coding: utf-8 -*-
#!/usr/bin/env python
##### System wide lib #####

##### Theory lib #####
from theory.gui.gtk.spreadsheet import SpreadsheetBuilder
from theory.gui.transformer import (
    GtkSpreadsheetModelDataHandler,
    GtkSpreadsheetModelBSONDataHandler,
    )

##### Theory third-party lib #####

##### Local app #####
from . import BaseUIAdapter

##### Theory app #####

##### Misc #####

class QuerysetAsSpreadsheetAdapter(BaseUIAdapter):
  @property
  def queryset(self):
    return self._queryset

  @queryset.setter
  def queryset(self, queryset):
    self._queryset = queryset

  @property
  def isEditable(self):
    return self._isEditable

  @isEditable.setter
  def isEditable(self, isEditable):
    self._isEditable = isEditable

  def run(self):
    self.isEditable = True
    if(self.queryset!=None):
      if(len(self.queryset) == 0):
        self.isQuerysetNonEmpty = False
        return

    self.isQuerysetNonEmpty = True
    return

  def render(self, *args, **kwargs):
    if(self.isQuerysetNonEmpty):
      spreadsheet = SpreadsheetBuilder()
      spreadsheet.run(self.queryset, self.isEditable)
      selectedRow = spreadsheet.getSelectedRow()
      dataRow = spreadsheet.getDataModel()
      newQueryset = []
      newDataRow = []
      for i in selectedRow:
        newQueryset.append(self.queryset[i])
        newDataRow.append(dataRow[i])

      columnHandlerLabel = spreadsheet.getColumnHandlerLabel()
      handler = GtkSpreadsheetModelBSONDataHandler()
      #handler = GtkSpreadsheetModelDataHandler()
      self.queryset = handler.run(newDataRow, newQueryset, columnHandlerLabel)
