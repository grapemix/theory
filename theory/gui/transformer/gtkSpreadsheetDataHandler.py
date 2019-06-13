# -*- coding: utf-8 -*-
#!/usr/bin/env python
##### System wide lib #####
import ast
from json import loads as jsonLoads

##### Theory lib #####

##### Theory third-party lib #####

##### Local app #####

##### Theory app #####
from theory.gui.transformer.gtkSpreadsheetBSONDataHandler \
    import GtkSpreadsheetModelBSONDataHandler

##### Misc #####

class GtkSpreadsheetModelDataHandler(GtkSpreadsheetModelBSONDataHandler):
  """
  This class handle the data conversion from Gtk spreadsheet model. In this
  handler, because of the limitation of gtkListModel, only modified rows are
  able to be notified, instead of modified rows and modified fields.

  Not being used currently. The reason for using this class instead of
  GtkSpreadsheetModelBSONDataHandler is because the list of string will be
  handled without quotation which allow user to type less. On the other hand,
  it will be not as safe as BSON handler which guarantee the conversion safety.
  """

  def _editableForceStrFieldDataHandler(self, rowId, fieldName, fieldVal):
    return str(fieldVal)

  def _listFieldeditableForceStrFieldDataHandler(
      self,
      rowId,
      fieldName,
      fieldVal
      ):
    try:
      return ast.literal_eval(fieldVal)
    except ValueError:
      try:
        return jsonLoads(fieldVal)
      except TypeError:
        return fieldVal
