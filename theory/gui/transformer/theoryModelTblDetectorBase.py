# -*- coding: utf-8 -*-
#!/usr/bin/env python
##### System wide lib #####

##### Theory lib #####

##### Theory third-party lib #####

##### Local app #####
from theory.gui.transformer.theoryModelDetectorBase import TheoryModelDetectorBase

##### Theory app #####

##### Misc #####

class TheoryModelTblDetectorBase(TheoryModelDetectorBase):
  """This class detect the data type from theory fields specific for table,
  but it does not handle any data type."""

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
        "ForeignKey": ("modelField", "modelField"),
        "OneToOneField": ("modelField", "modelField"),
        "ManyToManyField": ("modelField", "modelField"),
        "ArrayField": ("listField", "listField"),
    }
