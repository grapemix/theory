# -*- coding: utf-8 -*-
#!/usr/bin/env python
##### System wide lib #####
from collections import OrderedDict
import json

##### Theory lib #####
from theory.gui import theory_pb2

##### Theory third-party lib #####

##### Local app #####

##### Theory app #####
from theory.gui.transformer.theoryModelTblDetectorBase \
    import TheoryModelTblDetectorBase

##### Misc #####

class GtkSpreadsheetModelBSONDataHandler(TheoryModelTblDetectorBase):
  """This class handle the data conversion from Gtk spreadsheet model. In this
  handler, because of the limitation of gtkListModel, only modified rows are
  able to be notified, instead of modified rows and modified fields."""

  def run(self, dataRow, columnHandlerLabelZip, fieldNameVsProp):
    """
    :param dataRow: model from the gtkListModel as list of the list format as
      input
    :param queryLst: db model instance group as a list which is also as output
    :param columnHandlerLabelZip: a dictionary which map the column label vs the
      handler label that previous transformer probed. In that way, we don't
      have to re-probe the data type.
    """
    self.dataRow = dataRow

    self._buildTypeCatMap()
    handlerLst = []

    for fieldName, fieldProp in fieldNameVsProp.items():
      handlerLst.append((
        fieldName,
        getattr(self, "_%sDataHandler" % (fieldProp["klassLabel"])),
      ))
    self.fieldNameVsHandlerDict = OrderedDict(handlerLst)
    self.fieldNameVsProp = fieldNameVsProp

    numOfRow = len(dataRow)
    rowCounter = 0
    r = []
    for columnLabel, handlerLabel in columnHandlerLabelZip.items():
      if handlerLabel=="enumField":
        fieldProperty =  self.fieldNameVsProp[columnLabel]
        fieldProperty["reverseChoices"] = \
            dict([
              (v, k) for k,v in fieldProperty["choices"].items()
              ])

    fieldNameLst = self.fieldNameVsProp.keys()
    for rowNum in range(numOfRow):
      row = {}
      for colCounter, columnLabel in enumerate(fieldNameLst):
        if columnLabel == "id":
          # id field is a special case because it is required even it is non
          # editable
          row[columnLabel] = dataRow[rowNum][colCounter]
          continue
        newValue = self.fieldNameVsHandlerDict[columnLabel](
            rowNum,
            columnLabel,
            dataRow[rowNum][colCounter]
            )
        if newValue is not None:
          row[columnLabel] = newValue
      r.append(json.dumps(row))

    return r

  def _getFieldNameVsHandlerDict(self, klassLabel, prefix=""):
    return {
        "klassLabel": prefix + klassLabel,
        "dataHandler": getattr(self, "_%s%sDataHandler" % (prefix, klassLabel)),
        }

  def _neglectFieldDataHandler(self, rowId, fieldName, fieldVal):
    pass

  def _nonEditableForceStrFieldDataHandler(self, rowId, fieldName, fieldVal):
    return str(fieldVal)
    pass

  def _editableForceStrFieldDataHandler(self, rowId, fieldName, fieldVal):
    return str(fieldVal)

  def _dictFieldDataHandler(self, rowId, fieldName, fieldVal):
    # it is supposed to be no editable in this version
    pass

  def _embeddedFieldDataHandler(self, rowId, fieldName, fieldVal):
    pass

  def _listFieldneglectFieldDataHandler(self, rowId, fieldName, fieldVal):
    pass

  def _listFieldnonEditableForceStrFieldDataHandler(
      self,
      rowId,
      fieldName,
      fieldVal
      ):
    pass

  def _listFieldeditableForceStrFieldDataHandler(
      self,
      rowId,
      fieldName,
      fieldVal
      ):
    if fieldVal != "Too much to display......":
      # when the fieldVal is None, we will not set the field
      return json.loads(fieldVal)

  def _listFieldembeddedFieldDataHandler(self, rowId, fieldName, fieldVal):
    pass

  def _listFieldmodelFieldDataHandler(self, rowId, fieldName, fieldVal):
    pass

  def _modelFieldDataHandler(self, rowId, fieldName, fieldVal):
    pass

  def _boolFieldDataHandler(self, rowId, fieldName, fieldVal):
    return bool(fieldVal)

  def _strFieldDataHandler(self, rowId, fieldName, fieldVal):
    if fieldVal == u"None":
      return None
    return str(fieldVal)

  def _floatFieldDataHandler(self, rowId, fieldName, fieldVal):
    return float(fieldVal)

  def _intFieldDataHandler(self, rowId, fieldName, fieldVal):
    return int(fieldVal)

  def _enumFieldDataHandler(self, rowId, fieldName, fieldVal):
    if fieldVal == u"None":
      return None
    return self.fieldNameVsProp[fieldName]["reverseChoices"][fieldVal]

  def _constDataHandler(self, rowId, fieldName, fieldVal):
    """This fxn is special for the fieldVal being const and hence should not
    be modified during the save/update process(not in this fxn scope). And
    this fxn is only put in here to indicate the existance of this special
    case"""
    pass
