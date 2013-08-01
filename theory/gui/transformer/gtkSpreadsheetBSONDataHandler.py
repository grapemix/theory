# -*- coding: utf-8 -*-
#!/usr/bin/env python
##### System wide lib #####
from json import loads as jsonLoads

##### Theory lib #####

##### Theory third-party lib #####

##### Local app #####

##### Theory app #####
from gui.transformer.mongoModelDetectorBase import MongoModelDetectorBase

##### Misc #####

class GtkSpreadsheetModelBSONDataHandler(MongoModelDetectorBase):
  """This class handle the data conversion from Gtk spreadsheet model. In this
  handler, because of the limitation of gtkListModel, only modified rows are
  able to be notified, instead of modified rows and modified fields."""

  def run(self, dataRow, queryLst, columnHandlerLabelZip):
    """
    :param dataRow: model from the gtkListModel as list of the list format as
      input
    :param queryLst: db model instance group as a list which is also as output
    :param columnHandlerLabelZip: a dictionary which map the column label vs the
      handler label that previous transformer probed. In that way, we don't
      have to re-probe the data type.
    """
    self.dataRow = dataRow
    self.queryLst = queryLst
    self._buildTypeCatMap()

    # loop for column
    for columnLabel, handlerLabel in columnHandlerLabelZip.iteritems():
      # fill up field type handler
      if(handlerLabel!=None):
        self.fieldPropDict[columnLabel] = self._fillUpTypeHandler(handlerLabel)
      else:
        self.fieldPropDict[columnLabel] = {"klassLabel": "const"}

      # fill up enum choices
      if(handlerLabel=="enumField"):
        choices = \
            getattr(
              getattr(self.queryLst[0].__class__, columnLabel),
              "choices"
            )
        self.fieldPropDict[columnLabel]["reverseChoices"] = \
            dict([(i[1], i[0]) for i in choices])

    numOfRow = len(queryLst)
    for rowNum in range(numOfRow):
      i = 0
      for fieldName, fieldProperty in self.fieldPropDict.iteritems():
        if(fieldProperty["klassLabel"]!="const"):
          newValue = fieldProperty["dataHandler"](i, fieldName, dataRow[rowNum][i])
          if(not newValue is None):
            setattr(
                queryLst[rowNum],
                fieldName,
                newValue
            )
        i += 1
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
    return unicode(fieldVal)

  def _dictFieldDataHandler(self, rowId, fieldName, fieldVal):
    # it is supposed to be no editable in this version
    pass

  def _embeddedFieldDataHandler(self, rowId, fieldName, fieldVal):
    pass

  def _listFieldneglectFieldDataHandler(self, rowId, fieldName, fieldVal):
    pass

  def _listFieldnonEditableForceStrFieldDataHandler(self, rowId, fieldName, fieldVal):
    pass

  def _listFieldeditableForceStrFieldDataHandler(self, rowId, fieldName, fieldVal):
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
    return unicode(fieldVal)

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


