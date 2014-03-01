# -*- coding: utf-8 -*-
#!/usr/bin/env python
##### System wide lib #####

##### Theory lib #####

##### Theory third-party lib #####

##### Local app #####
from theory.gui.transformer.mongoModelDetectorBase import MongoModelDetectorBase

##### Theory app #####

##### Misc #####

class MongoModelTblDetectorBase(MongoModelDetectorBase):
  """This class detect the data type from MongoDB fields specific for table,
  but it does not handle any data type."""

  def _buildTypeCatMap(self):
    self._typeCatMap = {
        #"dbFieldName": ("fieldCategory", "fieldCategoryAsChild"),
        "BinaryField": ("neglectField", "neglectField"),
        "DynamicField": ("neglectField", "neglectField"),
        "FileField": ("neglectField", "neglectField"),
        "ImageField": ("neglectField", "neglectField"),
        "ComplexDateTimeField": (
          "nonEditableForceStrField",
          "nonEditableForceStrField"
          ),
        "DateTimeField": (
          "nonEditableForceStrField",
          "nonEditableForceStrField"
          ),
        "UUIDField": ("nonEditableForceStrField", "nonEditableForceStrField"),
        "ObjectIdField": (
          "nonEditableForceStrField",
          "nonEditableForceStrField"
          ),
        "SequenceField": (
          "nonEditableForceStrField",
          "nonEditableForceStrField"
          ),
        "DictField": ("nonEditableForceStrField", "nonEditableForceStrField"),
        "EmailField": ("editableForceStrField", "editableForceStrField"),
        "URLField": ("editableForceStrField", "editableForceStrField"),
        "GeoPointField": ("editableForceStrField", "editableForceStrField"),
        "BooleanField": ("boolField", "editableForceStrField"),
        "DecimalField": ("floatField", "editableForceStrField"),
        "FloatField": ("floatField", "editableForceStrField"),
        # Not a native mongo db field
        "EnumField": ("enumField", "editableForceStrField"),
        "IntField": ("intField", "editableForceStrField"),
        "StringField": ("strField", "editableForceStrField"),
        "MapField": ("nonEditableForceStrField", "nonEditableForceStrField"),
        "ReferenceField": ("modelField", "modelField"),
        "GenericReferenceField": ("modelField", "modelField"),
        "EmbeddedDocumentField": ("embeddedField", "embeddedField"),
        "GenericEmbeddedDocumentField": ("embeddedField", "embeddedField"),
        "ListField": ("listField", "listField"),
        "SortedListField": ("listField", "listField"),
    }
