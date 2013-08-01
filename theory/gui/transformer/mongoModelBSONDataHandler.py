# -*- coding: utf-8 -*-
#!/usr/bin/env python
##### System wide lib #####
from json import dumps as jsonDumps

##### Theory lib #####

##### Theory third-party lib #####

##### Local app #####

##### Theory app #####
from gui.transformer.mongoModelDetectorBase import MongoModelDetectorBase

##### Misc #####

class MongoModelBSONDataHandler(MongoModelDetectorBase):
  """This class handle the data conversion from MongoDB in BSON, which means
  this class should able to handle all mongoDB datatype, but it is less
  user-friendly"""

  def _fillUpTypeHandler(self, klassLabel, prefix=""):
    return {
        "klassLabel": prefix + klassLabel,
        "dataHandler": getattr(self, "_%s%sDataHandler" % (prefix, klassLabel)),
        }

  def _neglectFieldDataHandler(self, rowId, fieldName, fieldVal):
    pass

  def _nonEditableForceStrFieldDataHandler(self, rowId, fieldName, fieldVal):
    return unicode(fieldVal)

  def _editableForceStrFieldDataHandler(self, rowId, fieldName, fieldVal):
    return unicode(fieldVal)

  def _dictFieldDataHandler(self, rowId, fieldName, fieldVal):
    # we cannot use json.dumps in here because some of the fields cannot be
    # serialize
    return unicode(fieldVal)

  def _embeddedFieldDataHandler(self, rowId, fieldName, fieldVal):
    return rowId

  def _listFieldneglectFieldDataHandler(self, rowId, fieldName, fieldVal):
    pass

  def _listFieldnonEditableForceStrFieldDataHandler(self, rowId, fieldName, fieldVal):
    return unicode(fieldVal)

  def _listFieldeditableForceStrFieldDataHandler(self, rowId, fieldName, fieldVal):
    return jsonDumps(fieldVal)

  def _listFieldembeddedFieldDataHandler(self, rowId, fieldName, fieldVal):
    try:
      return len(fieldVal)
    except TypeError:
      # This happen when fieldVal is None which is because there has KeyError
      # in SpreadSheetBuilder's fieldPropDict
      return 0

  def _listFieldmodelFieldDataHandler(self, rowId, fieldName, fieldVal):
    try:
      return len(fieldVal)
    except TypeError:
      # This happen when fieldVal is None which is because there has KeyError
      # in SpreadSheetBuilder's fieldPropDict
      return 0

  def _modelFieldDataHandler(self, rowId, fieldName, fieldVal):
    return "1" if(fieldVal is not None) else "0"
    # The string data might be too long in some case
    #try:
    #  return str(fieldVal.id)
    #except AttributeError:
    #  # for example, the reference field is None
    #  return ""

  def _boolFieldDataHandler(self, rowId, fieldName, fieldVal):
    return fieldVal

  def _strFieldDataHandler(self, rowId, fieldName, fieldVal):
    return unicode(fieldVal)

  def _floatFieldDataHandler(self, rowId, fieldName, fieldVal):
    if(fieldVal is None):
      return 0.0
    return fieldVal

  def _intFieldDataHandler(self, rowId, fieldName, fieldVal):
    if(fieldVal is None):
      return 0
    return fieldVal

  def _enumFieldDataHandler(self, rowId, fieldName, fieldVal):
    return self.fieldPropDict[fieldName]["choices"][fieldVal]


