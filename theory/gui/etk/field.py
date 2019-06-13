# -*- coding: utf-8 -*-
#!/usr/bin/env python
##### System wide lib #####

##### Theory lib #####
from theory.gui.common import baseField
from theory.gui.common.baseField import *
from theory.gui.etk.widget import *

##### Theory third-party lib #####

##### Local app #####

##### Theory app #####

##### Misc #####


"""
Field classes.
"""

__all__ = (
  'Field', 'TextField', 'IntegerField',
  'DateField', 'TimeField', 'DateTimeField',
  'RegexField', 'EmailField', 'FileField', 'ImageField', 'URLField',
  'BooleanField', 'NullBooleanField', 'ChoiceField', 'MultipleChoiceField',
  'ListField', 'DictField', 'AdapterField',
  'ComboField', 'MultiValueField',
  #'SplitDateTimeField',
  'FloatField', 'DecimalField', 'IPAddressField', 'GenericIPAddressField',
  'FilePathField', 'SlugField', 'TypedChoiceField', 'TypedMultipleChoiceField',
  'StringGroupFilterField', 'ModelValidateGroupField', 'PythonModuleField',
  'PythonClassField', 'QuerysetField', 'BinaryField', 'GeoPointField',
)


class TextField(baseField.TextField):
  widget = TextInput
  lineBreak = "<br/>"

class IntegerField(baseField.IntegerField):
  widget = NumericInput
  def widget_attrs(self, widget):
    attrs = super(IntegerField, self).widget_attrs(widget)
    attrs.update({"isWeightExpand": False, "isFillAlign": False})
    return attrs

class FloatField(baseField.FloatField):
  widget = NumericInput

class DecimalField(baseField.DecimalField):
  widget = NumericInput
