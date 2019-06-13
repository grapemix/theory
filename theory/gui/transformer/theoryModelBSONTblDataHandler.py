# -*- coding: utf-8 -*-
#!/usr/bin/env python
##### System wide lib #####
from json import dumps as jsonDumps

##### Theory lib #####
from theory.gui.transformer.theoryJSONEncoder import TheoryJSONEncoder

##### Theory third-party lib #####

##### Local app #####

##### Theory app #####
from theory.gui.transformer.theoryModelTblDetectorBase \
    import TheoryModelTblDetectorBase

##### Misc #####

class TheoryModelBSONTblDataHandler(TheoryModelTblDetectorBase):
  """This class handle the data conversion from MongoDB in BSON, which means
  this class should able to handle all mongoDB datatype, but it is less
  user-friendly"""

  def _getFieldNameVsHandlerDict(self, klassLabel, prefix=""):
    return {
        "dataHandler": getattr(self, "_%s%sDataHandler" % (prefix, klassLabel)),
        }

  def _neglectFieldDataHandler(self, rowId, fieldName, fieldVal):
    pass

  def _nonEditableForceStrFieldDataHandler(self, rowId, fieldName, fieldVal):
    return str(fieldVal)

  def _editableForceStrFieldDataHandler(self, rowId, fieldName, fieldVal):
    return str(fieldVal)

  def _listFieldneglectFieldDataHandler(self, rowId, fieldName, fieldVal):
    pass

  def _listFieldnonEditableForceStrFieldDataHandler(
      self,
      rowId,
      fieldName,
      fieldVal
      ):
    return str(fieldVal)

  def _listFieldeditableForceStrFieldDataHandler(
      self,
      rowId,
      fieldName,
      fieldVal
      ):
    if fieldVal is not None and len(fieldVal) > 30:
      return "Too much to display......"
    return jsonDumps(fieldVal, cls=TheoryJSONEncoder)

  def _listFieldmodelFieldDataHandler(self, rowId, fieldName, fieldVal):
    try:
      return str(len(fieldVal))
    except TypeError:
      # This happen when fieldVal is None which is because there has KeyError
      # in SpreadSheetBuilder's fieldNameVsProp
      return "0"

  def _modelFieldDataHandler(self, rowId, fieldName, fieldVal):
    try:
      return str(fieldVal.id)
    except AttributeError:
      # for example, the reference field is None
      return ""

  def _boolFieldDataHandler(self, rowId, fieldName, fieldVal):
    return fieldVal

  def _strFieldDataHandler(self, rowId, fieldName, fieldVal):
    return str(fieldVal)

  def _floatFieldDataHandler(self, rowId, fieldName, fieldVal):
    if(fieldVal is None):
      return 0.0
    return fieldVal

  def _intFieldDataHandler(self, rowId, fieldName, fieldVal):
    if(fieldVal is None):
      return 0
    return fieldVal

  def _enumFieldDataHandler(self, rowId, fieldName, fieldVal):
    if(fieldVal is None):
      return "None"
    return self.fieldNameVsProp[fieldName]["choices"][fieldVal]
