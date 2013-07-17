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
    self._buildKlsTemplate()
    self.fieldsDict = fieldsDict
    for fieldName, fieldType in fieldsDict.iteritems():
      self.fieldType[fieldName] = \
          self._matchFieldType(fieldType, self._typeHandlerMap)

  @abstractmethod
  def _fillUpTypeHandler(self, klassLabel, prefix=""):
    pass

  def _matchFieldType(self, fieldType, typeHandlerMap, prefix=""):
    for dbKlassLabel, klassLst in typeHandlerMap.iteritems():
      for klass in klassLst:
        internalKlassLabel = self._getKlassLabel(fieldType, dbKlassLabel, klass)
        if(internalKlassLabel!=None):
          return self._fillUpTypeHandler(internalKlassLabel, prefix)

  def _getKlassLabel(self, fieldType, klassLabel, klass):
    if(isinstance(fieldType, klass)):
      if(klassLabel=="listField"):
        return self._matchFieldType(
            fieldType.field,
            self._childTypeHandlerMap,
            "listField"
            )["klassLabel"]
      elif(klassLabel=="mapField"):
        return self._matchFieldType(
            fieldType.field,
            self._childTypeHandlerMap,
            "listField"
            )["klassLabel"]
      else:
        return klassLabel
    return None

  def _getKlassFromMongoEngine(self, klassLst):
    return [getattr(MongoEngineField, i) for i in klassLst]

  def _buildKlsTemplate(self):
    neglectedFieldKlass = self._getKlassFromMongoEngine(
        ["BinaryField", "DynamicField", "FileField", "ImageField"])
    nonEditableForceStrFieldKlass = self._getKlassFromMongoEngine([
      "ComplexDateTimeField",
      "DateTimeField",
      "UUIDField",
      "SequenceField",
      "DictField",
    ])
    nonEditableForceStrFieldKlass.append(MongoEngineObjectId)
    editableForceStrFieldKlass = self._getKlassFromMongoEngine(
        ["EmailField", "URLField", "GeoPointField"])

    boolFieldKlass = self._getKlassFromMongoEngine(["BooleanField",])
    floatFieldKlass = self._getKlassFromMongoEngine([
      "DecimalField",
      "FloatField"
    ])
    intFieldKlass = self._getKlassFromMongoEngine(["IntField",])
    strFieldKlass = self._getKlassFromMongoEngine(["StringField",])

    # The reason we needed OrderedDict in here instead of Dict is because
    # some fields like ComplexDateTimeField will return true for
    # isinstance(StringField) and hence we have to test those fields which
    # can be automatically casted as StringField first.
    self._typeHandlerMap = OrderedDict()
    self._typeHandlerMap["neglectField"] = neglectedFieldKlass
    self._typeHandlerMap["mapField"] = self._getKlassFromMongoEngine([
      "MapField",
    ])
    self._typeHandlerMap["nonEditableForceStrField"] = \
        nonEditableForceStrFieldKlass
    self._typeHandlerMap["editableForceStrField"] = \
        editableForceStrFieldKlass
    self._typeHandlerMap["modelField"] = self._getKlassFromMongoEngine(
        [
            "GenericReferenceField",
            "ReferenceField",
        ])
    self._typeHandlerMap["embeddedField"] = self._getKlassFromMongoEngine(
        [
            "GenericEmbeddedDocumentField",
            "EmbeddedDocumentField",
        ])
    self._typeHandlerMap["listField"] = self._getKlassFromMongoEngine([
      "SortedListField",
      "ListField"
    ])
    self._typeHandlerMap["boolField"] = boolFieldKlass
    self._typeHandlerMap["floatField"] = floatFieldKlass
    self._typeHandlerMap["intField"] = intFieldKlass
    self._typeHandlerMap["strField"] = strFieldKlass

    self._childTypeHandlerMap = deepcopy(self._typeHandlerMap)
    for i in ["boolField", "floatField", "intField", "strField"]:
      del self._childTypeHandlerMap[i]
    self._childTypeHandlerMap["editableForceStrField"] = \
        [klass for klassLst in [
          editableForceStrFieldKlass,
          boolFieldKlass,
          floatFieldKlass,
          intFieldKlass,
          strFieldKlass
        ] for klass in klassLst]

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
    self._buildKlsTemplate()

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
