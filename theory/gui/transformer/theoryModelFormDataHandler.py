# -*- coding: utf-8 -*-
#!/usr/bin/env python
##### System wide lib #####
from json import dumps as jsonDumps

##### Theory lib #####
from theory.gui.transformer.theoryJSONEncoder import TheoryJSONEncoder

##### Theory third-party lib #####

##### Local app #####

##### Theory app #####
from theory.gui.transformer.theoryModelDetectorBase import (
    TheoryModelDetectorBase
    )

##### Misc #####

class TheoryModelFormDataHandler(TheoryModelDetectorBase):
  """This class handle the data conversion from MongoDB in BSON, which means
  this class should able to handle all mongoDB datatype, but it is less
  user-friendly"""

  """This class detect the data type from theory fields specific for table,
  but it does not handle any data type."""

  fieldParamTmpl = {
      "widgetIsFocusChgTrigger": False,
      "widgetIsContentChgTrigger":  False,
      }

  def _buildTypeCatMap(self):
    self._typeCatMap = {
        #"dbFieldName": ("fieldCategory", "fieldCategoryAsChild"),
        "BinaryField": ("neglectField", "neglectField"),
        "FileField": ("neglectField", "neglectField"),
        "ImageField": ("neglectField", "neglectField"),
        "DateField": (
          "nonEditableForceStrField",
          "nonEditableForceStrField"
          ),
        "TimeField": (
          "nonEditableForceStrField",
          "nonEditableForceStrField"
          ),
        "DateTimeField": (
          "nonEditableForceStrField",
          "nonEditableForceStrField"
          ),
        "AutoField": (
          "nonEditableForceStrField",
          "nonEditableForceStrField"
          ),
        "EmailField": ("editableForceStrField", "editableForceStrField"),
        "URLField": ("editableForceStrField", "editableForceStrField"),
        "BooleanField": ("boolField", "editableForceStrField"),
        "DecimalField": ("floatField", "editableForceStrField"),
        "FloatField": ("floatField", "editableForceStrField"),
        # Not a native mongo db field
        "EnumField": ("enumField", "editableForceStrField"),
        "NullBooleanField": ("enumField", "editableForceStrField"),
        "IntegerField": ("intField", "editableForceStrField"),
        "BigIntegerField": ("intField", "editableForceStrField"),
        "SmallIntegerField": ("intField", "editableForceStrField"),
        "PositiveIntegerField": ("intField", "editableForceStrField"),
        "PositiveSmallIntegerField": ("intField", "editableForceStrField"),
        "CharField": ("strField", "editableForceStrField"),
        "TextField": ("strField", "editableForceStrField"),
        "SlugField": ("strField", "editableForceStrField"),
        "IPAddressField": ("strField", "editableForceStrField"),
        "GenericIPAddressField": ("strField", "editableForceStrField"),
        "FilePathField": ("strField", "editableForceStrField"),
        "CommaSeparatedIntegerField": ("strField", "editableForceStrField"),
        "ForeignKey": ("modelField", "neglectField"),
        "OneToOneField": ("modelField", "neglectField"),
        "ManyToManyField": ("m2mField", "neglectField"),
        "ArrayField": ("listField", "listField"),
    }

  def _getFieldNameVsHandlerDict(self, klassLabel, prefix=""):
    return {
        "klassLabel": prefix + klassLabel,
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
      # in SpreadSheetBuilder's fieldPropDict
      return "0"

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
    return self.fieldPropDict[fieldName]["choices"][fieldVal]


  #    row = {
  #        "type": type(field).__name__,
  #        "widgetIsFocusChgTrigger": \
  #            True if hasattr(self, focusChgFxnName) else False,
  #        "widgetIsContentChgTrigger": \
  #            True if(hasattr(self, contentChgFxnName)) else False
  #        }
  #    for i in [
  #        'helpText',
  #        'initData',
  #        'label',
  #        'localize',
  #        'required',
  #        'showHiddenInitial',
  #        'queryset',
  #        'errorMessages',
  #        'choices',
  #        ]:
  #      if hasattr(field, i):
  #        val = getattr(field, i)
  #        if type(val).__name__ == "__proxy__":
  #          # for fields from model form
  #          val = str(val)
  #        elif isinstance(val, dict):
  #          # for errorMessages
  #          newDict = {}
  #          for k, v in val.items():
  #            if type(v).__name__ == "__proxy__":
  #              newDict[k] = str(v)
  #          if len(newDict) > 0:
  #            val = newDict
  #        row[i] =  val

  #    r[fieldName] = row

  #  'Field', 'TextField', 'IntegerField',
  #  'DateField', 'TimeField', 'DateTimeField', 'RegexField', 'EmailField',
  #  'URLField', 'BooleanField', 'NullBooleanField', 'ChoiceField',
  #  'MultipleChoiceField', 'ListField', 'DictField', 'AdapterField',
  #  'FileField', 'ImageField', 'FilePathField', 'ImagePathField', 'DirPathField',
  #  'ComboField', 'MultiValueField',
  #  #'SplitDateTimeField',
  #  'FloatField', 'DecimalField', 'IPAddressField', 'GenericIPAddressField',
  #  'SlugField', 'TypedChoiceField', 'TypedMultipleChoiceField',
  #  'StringGroupFilterField', 'ModelValidateGroupField', 'PythonModuleField',
  #  'PythonClassField', 'QueryIdField', 'QuerysetField', 'EmbeddedField',
  #  'ObjectIdField', 'BinaryField', 'GeoPointField',

  def _neglectFieldFormFieldCreationHandler(self, fieldName, fieldVal):
    pass

  def _nonEditableForceStrFieldFormFieldCreationHandler(
      self,
      fieldName,
      fieldVal,
      ):
    return self.fieldParamTmpl.update({
        "type": "TextField",
        "label": fieldName,
        "initData": fieldVal,
        })

  def _editableForceStrFieldFormFieldCreationHandler(self, fieldName, fieldVal):
    return self.fieldParamTmpl.update({
        "type": "TextField",
        "label": fieldName,
        "initData": fieldVal,
        })

  def _listFieldneglectFieldFormFieldCreationHandler(self, fieldName, fieldVal):
    pass

  def _listFieldnonEditableForceStrFieldFormFieldCreationHandler(
      self,
      fieldName,
      fieldVal,
      ):
    return self.fieldParamTmpl.update({
        "type": "ListField",
        "label": fieldName,
        "initData": fieldVal,
        })

  def _listFieldeditableForceStrFieldFormFieldCreationHandler(
      self,
      fieldName,
      fieldVal,
      ):
    return self.fieldParamTmpl.update({
        "type": "ListField",
        "label": fieldName,
        "initData": fieldVal,
        })

  def _m2mFieldFormFieldCreationHandler(self, fieldName, fieldVal):
    return self.fieldParamTmpl.update({
        "type": "QuerysetField",
        "label": fieldName,
        "initData": fieldVal,
        })

  def _modelFieldFormFieldCreationHandler(self, fieldName, fieldVal):
    return self.fieldParamTmpl.update({
        "type": "QueryIdField",
        "label": fieldName,
        "initData": fieldVal,
        })

  def _boolFieldFormFieldCreationHandler(self, fieldName, fieldVal):
    return self.fieldParamTmpl.update({
        "type": "BooleanField",
        "label": fieldName,
        "initData": fieldVal,
        })

  def _strFieldFormFieldCreationHandler(self, fieldName, fieldVal):
    return self.fieldParamTmpl.update({
        "type": "TextField",
        "label": fieldName,
        "initData": fieldVal,
        })

  def _floatFieldFormFieldCreationHandler(self, fieldName, fieldVal):
    return self.fieldParamTmpl.update({
        "type": "FloatField",
        "label": fieldName,
        "initData": fieldVal,
        })

  def _intFieldFormFieldCreationHandler(self, fieldName, fieldVal):
    if(fieldVal is None):
      return 0
    return fieldVal
    return self.fieldParamTmpl.update({
        "type": "FloatField",
        "label": fieldName,
        "initData": fieldVal,
        })

  def _enumFieldFormFieldCreationHandler(self, fieldName, fieldVal):
    if(fieldVal is None):
      return "None"
    return self.fieldPropDict[fieldName]["choices"][fieldVal]
    return self.fieldParamTmpl.update({
        "type": "ChoiceField",
        "label": fieldName,
        "initData": fieldVal,
        })

