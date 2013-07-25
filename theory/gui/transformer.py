# -*- coding: utf-8 -*-
#!/usr/bin/env python
##### System wide lib #####
from abc import ABCMeta, abstractmethod
import ast
from collections import OrderedDict
from copy import deepcopy
from json import dumps as jsonDumps
from json import loads as jsonLoads
from mongoengine import fields as MongoEngineField
from mongoengine.base import ObjectIdField as MongoEngineObjectId

##### Theory lib #####
from theory.gui import field

##### Theory third-party lib #####

##### Local app #####

##### Theory app #####

##### Misc #####

__all__ = (
    "MongoModelDataHandler",
    "MongoModelBSONDataHandler",
    "GtkSpreadsheetModelDataHandler",
    "GtkSpreadsheetModelBSONDataHandler",
    )

class MongoModelDetectorBase(object):
  """This class detect the data type from MongoDB fields, but it does not
  handle any data type."""
  __metaclass__ = ABCMeta

  def __init__(self):
    self.fieldType = OrderedDict()

  def run(self, queryset, fieldsDict):
    self.queryset = queryset

    self._buildTypeCatMap()
    self.fieldsDict = fieldsDict
    for fieldName, fieldTypeLabel in fieldsDict.iteritems():
      fieldTypeLabelTokenLst = fieldTypeLabel.split(".")
      handlerFxnName = ""
      for fieldTypeLabelToken in fieldTypeLabelTokenLst:
        if(handlerFxnName==""):
          # When it is in top level, we treated it as normal
          handlerFxnName += self._typeCatMap[fieldTypeLabelToken][0]
        else:
          # When it is NOT in top level, we treated it as child
          handlerFxnName += self._typeCatMap[fieldTypeLabelToken][1]
      self.fieldType[fieldName] = self._fillUpTypeHandler(handlerFxnName, "")


  @abstractmethod
  def _fillUpTypeHandler(self, klassLabel, prefix=""):
    pass

  def _matchFieldType(self, unknownFieldTypeLabel, typeHandlerCatMap, prefix=""):
    for catLabel, dbFieldTypeLabelLst in typeHandlerCatMap.iteritems():
      for dbFieldTypeLabel in dbFieldTypeLabelLst:
        internalKlassLabel = self._getKlassLabel(
            unknownFieldTypeLabel,
            catLabel,
            dbFieldTypeLabel
            )
        if(internalKlassLabel!=None):
          return self._fillUpTypeHandler(internalKlassLabel, prefix)

  def _getKlassLabel(self, fieldType, klassLabel, klass):
    if(isinstance(fieldType, klass)):
      if(klassLabel=="listField"):
        return self._matchFieldType(
            fieldType.field,
            self._childTypeHandlerCatMap,
            "listField"
            )["klassLabel"]
      elif(klassLabel=="mapField"):
        return self._matchFieldType(
            fieldType.field,
            self._childTypeHandlerCatMap,
            "listField"
            )["klassLabel"]
      else:
        return klassLabel
    return None

  def _buildTypeCatMap(self):
    self._typeCatMap = {
        "BinaryField": ("neglectField", "neglectField"),
        "DynamicField": ("neglectField", "neglectField"),
        "FileField": ("neglectField", "neglectField"),
        "ImageField": ("neglectField", "neglectField"),
        "ComplexDateTimeField": ("nonEditableForceStrField", "nonEditableForceStrField"),
        "DateTimeField": ("nonEditableForceStrField", "nonEditableForceStrField"),
        "UUIDField": ("nonEditableForceStrField", "nonEditableForceStrField"),
        "SequenceField": ("nonEditableForceStrField", "nonEditableForceStrField"),
        "DictField": ("nonEditableForceStrField", "nonEditableForceStrField"),
        "EmailField": ("editableForceStrField", "editableForceStrField"),
        "URLField": ("editableForceStrField", "editableForceStrField"),
        "GeoPointField": ("editableForceStrField", "editableForceStrField"),
        "BooleanField": ("boolField", "editableForceStrField"),
        "DecimalField": ("floatField", "editableForceStrField"),
        "FloatField": ("floatField", "editableForceStrField"),
        "IntField": ("intField", "editableForceStrField"),
        "StringField": ("strField", "editableForceStrField"),
        "MapField": ("listField", "listField"),
        "ReferenceField": ("modelField", "modelField"),
        "GenericReferenceField": ("modelField", "modelField"),
        "EmbeddedDocumentField": ("embeddedField", "embeddedField"),
        "GenericEmbeddedDocumentField": ("embeddedField", "embeddedField"),
        "ListField": ("listField", "listField"),
        "SortedListField": ("listField", "listField"),
    }

class MongoModelBSONDataHandler(MongoModelDetectorBase):
  """This class handle the data conversion from MongoDB in BSON, which means
  this class should able to handle all mongoDB datatype, but it is less
  user-friendly"""

  def _fillUpTypeHandler(self, klassLabel, prefix=""):
    return {
        "klassLabel": prefix + klassLabel,
        "dataHandler": getattr(self, "_%s%sDataHandler" % (prefix, klassLabel)),
        }

  def _neglectFieldDataHandler(self, rowId, fieldVal):
    pass

  def _nonEditableForceStrFieldDataHandler(self, rowId, fieldVal):
    return unicode(fieldVal)

  def _editableForceStrFieldDataHandler(self, rowId, fieldVal):
    return unicode(fieldVal)

  def _dictFieldDataHandler(self, rowId, fieldVal):
    # we cannot use json.dumps in here because some of the fields cannot be
    # serialize
    return unicode(fieldVal)

  def _embeddedFieldDataHandler(self, rowId, fieldVal):
    return rowId

  def _listFieldneglectFieldDataHandler(self, rowId, fieldVal):
    pass

  def _listFieldnonEditableForceStrFieldDataHandler(self, rowId, fieldVal):
    return unicode(fieldVal)

  def _listFieldeditableForceStrFieldDataHandler(self, rowId, fieldVal):
    return jsonDumps(fieldVal)

  def _listFieldembeddedFieldDataHandler(self, rowId, fieldVal):
    try:
      return len(fieldVal)
    except TypeError:
      # This happen when fieldVal is None which is because there has KeyError
      # in SpreadSheetBuilder's fieldType
      return 0

  def _listFieldmodelFieldDataHandler(self, rowId, fieldVal):
    try:
      return len(fieldVal)
    except TypeError:
      # This happen when fieldVal is None which is because there has KeyError
      # in SpreadSheetBuilder's fieldType
      return 0

  def _modelFieldDataHandler(self, rowId, fieldVal):
    return "1" if(fieldVal is not None) else "0"
    # The string data might be too long in some case
    #try:
    #  return str(fieldVal.id)
    #except AttributeError:
    #  # for example, the reference field is None
    #  return ""

  def _boolFieldDataHandler(self, rowId, fieldVal):
    return fieldVal

  def _strFieldDataHandler(self, rowId, fieldVal):
    return unicode(fieldVal)

  def _floatFieldDataHandler(self, rowId, fieldVal):
    if(fieldVal is None):
      return 0.0
    return fieldVal

  def _intFieldDataHandler(self, rowId, fieldVal):
    if(fieldVal is None):
      return 0
    return fieldVal

class MongoModelDataHandler(MongoModelBSONDataHandler):
  """This class handle the data conversion from MongoDB"""

  def _editableForceStrFieldDataHandler(self, rowId, fieldVal):
    return unicode(fieldVal)

  def _listFieldeditableForceStrFieldDataHandler(self, rowId, fieldVal):
    return fieldVal

class GtkSpreadsheetModelBSONDataHandler(MongoModelDetectorBase):
  """This class handle the data conversion from Gtk spreadsheet model. In this
  handler, because of the limitation of gtkListModel, only modified rows are
  able to be notified, instead of modified rows and modified fields."""

  def run(self, dataRow, queryLst, columnHandlerLabelZip):
    """
    :param dataRow: model from the gtkListModel as list of the list format as
      input
    :param queryLst: db model instance group as a list which is also as output
    :param fieldsDict: just a dict to descibe fields in the model
    """
    self.dataRow = dataRow
    self.queryLst = queryLst
    self._buildTypeCatMap()

    for columnLabel, handlerLabel in columnHandlerLabelZip.iteritems():
      if(handlerLabel!=None):
        self.fieldType[columnLabel] = self._fillUpTypeHandler(handlerLabel)
      else:
        self.fieldType[columnLabel] = {"klassLabel": "const"}

    numOfRow = len(queryLst)
    for rowNum in range(numOfRow):
      i = 0
      for fieldName, fieldProperty in self.fieldType.iteritems():
        if(fieldProperty["klassLabel"]!="const"):
          newValue = fieldProperty["dataHandler"](i, dataRow[rowNum][i])
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

  def _neglectFieldDataHandler(self, rowId, fieldVal):
    pass

  def _nonEditableForceStrFieldDataHandler(self, rowId, fieldVal):
    pass

  def _editableForceStrFieldDataHandler(self, rowId, fieldVal):
    return unicode(fieldVal)

  def _dictFieldDataHandler(self, rowId, fieldVal):
    # it is supposed to be no editable in this version
    pass

  def _embeddedFieldDataHandler(self, rowId, fieldVal):
    pass

  def _listFieldneglectFieldDataHandler(self, rowId, fieldVal):
    pass

  def _listFieldnonEditableForceStrFieldDataHandler(self, rowId, fieldVal):
    pass

  def _listFieldeditableForceStrFieldDataHandler(self, rowId, fieldVal):
    return jsonLoads(fieldVal)

  def _listFieldembeddedFieldDataHandler(self, rowId, fieldVal):
    pass

  def _listFieldmodelFieldDataHandler(self, rowId, fieldVal):
    pass

  def _modelFieldDataHandler(self, rowId, fieldVal):
    pass

  def _boolFieldDataHandler(self, rowId, fieldVal):
    return bool(fieldVal)

  def _strFieldDataHandler(self, rowId, fieldVal):
    return unicode(fieldVal)

  def _floatFieldDataHandler(self, rowId, fieldVal):
    return float(fieldVal)

  def _intFieldDataHandler(self, rowId, fieldVal):
    return int(fieldVal)

  def _constDataHandler(self, rowId, fieldVal):
    """This fxn is special for the fieldVal being const and hence should not
    be modified during the save/update process(not in this fxn scope). And
    this fxn is only put in here to indicate the existance of this special
    case"""
    pass

class GtkSpreadsheetModelDataHandler(GtkSpreadsheetModelBSONDataHandler):
  """This class handle the data conversion from Gtk spreadsheet model. In this
  handler, because of the limitation of gtkListModel, only modified rows are
  able to be notified, instead of modified rows and modified fields."""

  def _editableForceStrFieldDataHandler(self, rowId, fieldVal):
    return unicode(fieldVal)

  def _listFieldeditableForceStrFieldDataHandler(self, rowId, fieldVal):
    try:
      return ast.literal_eval(fieldVal)
    except ValueError:
      try:
        return jsonLoads(fieldVal)
      except TypeError:
        return fieldVal
