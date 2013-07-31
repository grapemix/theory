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
          handlerFxnName = self._typeCatMap[fieldTypeLabelToken][0]
        else:
          # When it is NOT in top level, we treated it as child
          handlerFxnName += self._typeCatMap[fieldTypeLabelToken][1]
      if(handlerFxnName=="intField" and \
          hasattr(
            getattr(self.queryset[0].__class__, fieldName),
            "choices"
          ) and \
          getattr(
            getattr(self.queryset[0].__class__, fieldName),
            "choices"
            ) is not None
          ):
        handlerFxnName = self._typeCatMap["EnumField"][0]
        self.fieldType[fieldName] = self._fillUpTypeHandler(handlerFxnName, "")
        self.fieldType[fieldName]["choices"] = \
            dict(
                getattr(
                  getattr(self.queryset[0].__class__, fieldName),
                  "choices"
                )
            )
      else:
        self.fieldType[fieldName] = self._fillUpTypeHandler(handlerFxnName, "")

  @abstractmethod
  def _fillUpTypeHandler(self, klassLabel, prefix=""):
    pass

  def _buildTypeCatMap(self):
    self._typeCatMap = {
        #"dbFieldName": ("fieldCategory", "fieldCategoryAsChild"),
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
        "EnumField": ("enumField", "editableForceStrField"), # Not a native mongo db field
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
      # in SpreadSheetBuilder's fieldType
      return 0

  def _listFieldmodelFieldDataHandler(self, rowId, fieldName, fieldVal):
    try:
      return len(fieldVal)
    except TypeError:
      # This happen when fieldVal is None which is because there has KeyError
      # in SpreadSheetBuilder's fieldType
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
    return self.fieldType[fieldName]["choices"][fieldVal]

class MongoModelDataHandler(MongoModelBSONDataHandler):
  """This class handle the data conversion from MongoDB"""

  def _editableForceStrFieldDataHandler(self, rowId, fieldName, fieldVal):
    return unicode(fieldVal)

  def _listFieldeditableForceStrFieldDataHandler(self, rowId, fieldName, fieldVal):
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
    """
    #:param fieldsDict: just a map for field name vs field type label in the model
    self.dataRow = dataRow
    self.queryLst = queryLst
    self._buildTypeCatMap()

    # loop for column
    for columnLabel, handlerLabel in columnHandlerLabelZip.iteritems():
      # fill up field type handler
      if(handlerLabel!=None):
        self.fieldType[columnLabel] = self._fillUpTypeHandler(handlerLabel)
      else:
        self.fieldType[columnLabel] = {"klassLabel": "const"}

      # fill up enum choices
      if(handlerLabel=="enumField"):
        choices = \
            getattr(
              getattr(self.queryLst[0].__class__, columnLabel),
              "choices"
            )
        self.fieldType[columnLabel]["reverseChoices"] = \
            dict([(i[1], i[0]) for i in choices])

    numOfRow = len(queryLst)
    for rowNum in range(numOfRow):
      i = 0
      for fieldName, fieldProperty in self.fieldType.iteritems():
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
    return self.fieldType[fieldName]["reverseChoices"][fieldVal]

  def _constDataHandler(self, rowId, fieldName, fieldVal):
    """This fxn is special for the fieldVal being const and hence should not
    be modified during the save/update process(not in this fxn scope). And
    this fxn is only put in here to indicate the existance of this special
    case"""
    pass

class GtkSpreadsheetModelDataHandler(GtkSpreadsheetModelBSONDataHandler):
  """This class handle the data conversion from Gtk spreadsheet model. In this
  handler, because of the limitation of gtkListModel, only modified rows are
  able to be notified, instead of modified rows and modified fields."""

  def _editableForceStrFieldDataHandler(self, rowId, fieldName, fieldVal):
    return unicode(fieldVal)

  def _listFieldeditableForceStrFieldDataHandler(self, rowId, fieldName, fieldVal):
    try:
      return ast.literal_eval(fieldVal)
    except ValueError:
      try:
        return jsonLoads(fieldVal)
      except TypeError:
        return fieldVal
