# -*- coding: utf-8 -*-
#!/usr/bin/env python
##### System wide lib #####
from json import loads as jsonLoads

##### Theory lib #####

##### Theory third-party lib #####

##### Local app #####

##### Theory app #####
from theory.gui.transformer.mongoModelTblDetectorBase \
    import MongoModelTblDetectorBase

##### Misc #####

class GtkSpreadsheetModelBSONDataHandler(MongoModelTblDetectorBase):
  """This class handle the data conversion from Gtk spreadsheet model. In this
  handler, because of the limitation of gtkListModel, only modified rows are
  able to be notified, instead of modified rows and modified fields."""

  def run(self, dataRow, queryLst, columnHandlerLabelZip, fieldParamMap):
    """
    :param dataRow: model from the gtkListModel as list of the list format as
      input
    :param queryLst: db model instance group as a list which is also as output
    :param columnHandlerLabelZip: a dictionary which map the column label vs the
      handler label that previous transformer probed. In that way, we don't
      have to re-probe the data type.
    """
    self.dataRow = dataRow

    super(GtkSpreadsheetModelBSONDataHandler, self).run(fieldParamMap)
    numOfRow = len(queryLst)
    rowCounter = 0
    # loop for column
    for columnLabel, handlerLabel in columnHandlerLabelZip.iteritems():
      # fill up field type handler
      if(handlerLabel is None):
        self.fieldPropDict[columnLabel] = {"klassLabel": "const"}
      else:
        fieldProperty =  self.fieldPropDict[columnLabel]
        if(handlerLabel=="enumField"):
          fieldProperty["reverseChoices"] = \
              dict([
                (v, k) for k,v in fieldProperty["choices"].iteritems()
                ])
        for rowNum in range(numOfRow):
          newValue = fieldProperty["dataHandler"](
              rowCounter,
              columnLabel,
              dataRow[rowNum][rowCounter]
              )
          if(not newValue is None):
            setattr(
                queryLst[rowNum],
                columnLabel,
                newValue
            )
      rowCounter += 1
    return queryLst

  def _fillUpTypeHandler(self, klassLabel, prefix=""):
    return {
        "klassLabel": prefix + klassLabel,
        "dataHandler": getattr(self, "_%s%sDataHandler" % (prefix, klassLabel)),
        }

  def _neglectFieldDataHandler(self, rowId, fieldName, fieldVal):
    pass

  def _nonEditableForceStrFieldDataHandler(self, rowId, fieldName, fieldVal):
    pass

  def _editableForceStrFieldDataHandler(self, rowId, fieldName, fieldVal):
    return unicode(fieldVal.decode("utf8"))

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
    return jsonLoads(fieldVal)

  def _listFieldembeddedFieldDataHandler(self, rowId, fieldName, fieldVal):
    pass

  def _listFieldmodelFieldDataHandler(self, rowId, fieldName, fieldVal):
    pass

  def _modelFieldDataHandler(self, rowId, fieldName, fieldVal):
    pass

  def _boolFieldDataHandler(self, rowId, fieldName, fieldVal):
    return bool(fieldVal)

  def _strFieldDataHandler(self, rowId, fieldName, fieldVal):
    return unicode(fieldVal.decode("utf8"))

  def _floatFieldDataHandler(self, rowId, fieldName, fieldVal):
    return float(fieldVal)

  def _intFieldDataHandler(self, rowId, fieldName, fieldVal):
    return int(fieldVal)

  def _enumFieldDataHandler(self, rowId, fieldName, fieldVal):
    return self.fieldPropDict[fieldName]["reverseChoices"][fieldVal]

  def _constDataHandler(self, rowId, fieldName, fieldVal):
    """This fxn is special for the fieldVal being const and hence should not
    be modified during the save/update process(not in this fxn scope). And
    this fxn is only put in here to indicate the existance of this special
    case"""
    pass


