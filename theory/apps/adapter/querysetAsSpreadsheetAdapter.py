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
  def __init__(self, *args, **kwargs):
    super(QuerysetAsSpreadsheetAdapter, self).__init__(*args, **kwargs)
    self.selectedIdLst = []

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

  @property
  def appModel(self):
    return self._appModel

  @appModel.setter
  def appModel(self, appModel):
    self._appModel = appModel

  @property
  def selectedIdLst(self):
    return self._selectedIdLst

  @selectedIdLst.setter
  def selectedIdLst(self, selectedIdLst):
    self._selectedIdLst = selectedIdLst

  def run(self):
    self.isEditable = True
    self.hasBeenSelected = False

  def _getSpreadsheetBuilder(self):
    return SpreadsheetBuilder()

  def render(self, *args, **kwargs):
    if(not self.hasBeenSelected):
      self.hasBeenSelected = True
      spreadsheet = self._getSpreadsheetBuilder()
      selectedIdLst = self.selectedIdLst
      spreadsheet.run(
          self.queryset,
          self.appModel,
          self.isEditable,
          selectedIdLst=selectedIdLst
          )
      selectedRow = spreadsheet.getSelectedRow()
      dataRow = spreadsheet.getDataModel()

      newDataRow = []
      # If the self.queryset type is queryset, we want to newQueryset
      # as queryset, otherwise, we want to return as list
      if type(self.queryset).__name__ == "QuerySet":
        newPkSet = set()
        for i in selectedRow:
          newPkSet.add(self.queryset[i].id)
          newDataRow.append(dataRow[i])
        newQueryset = self.queryset.filter(pk__in=newPkSet)
      else:
        newQueryset = []
        for i in selectedRow:
          newQueryset.append(self.queryset[i])
          newDataRow.append(dataRow[i])

      if(len(newQueryset)!=0):
        columnHandlerLabel = spreadsheet.getColumnHandlerLabel()
        handler = GtkSpreadsheetModelBSONDataHandler()
        self.queryset = handler.run(
            newDataRow,
            newQueryset,
            columnHandlerLabel,
            self.appModel.fieldParamMap.all(),
            )
      else:
        self.queryset = []
