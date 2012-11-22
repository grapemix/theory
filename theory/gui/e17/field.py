# -*- coding: utf-8 -*-
#!/usr/bin/env python
##### System wide lib #####

##### Theory lib #####
from theory.gui.common import field
from theory.gui.common.field import Field
from theory.gui.widget import *

##### Theory third-party lib #####

##### Local app #####

##### Theory app #####

##### Misc #####


"""
Field classes.
"""

__all__ = (
  'Field', 'TextField', 'IntegerField',
  #'DateField', 'TimeField', 'DateTimeField', 'TimeField',
  'RegexField', 'EmailField', 'FileField', 'ImageField', 'URLField',
  'BooleanField', 'NullBooleanField', 'ChoiceField', 'MultipleChoiceField',
  'ListField', 'DictField', 'AdapterField',
  #'ComboField', 'MultiValueField', 'SplitDateTimeField',
  'FloatField', 'DecimalField', 'IPAddressField', 'GenericIPAddressField',
  'FilePathField', 'SlugField', 'TypedChoiceField', 'TypedMultipleChoiceField',
  'StringGroupFilterField', 'ModelValidateGroupField',
)


class TextField(field.TextField):
  widget = TextInput
  lineBreak = "<br/>"

class IntegerField(field.IntegerField):
  widget = NumericInput
  def widget_attrs(self, widget):
    attrs = super(IntegerField, self).widget_attrs(widget)
    attrs.update({"isWeightExpand": False, "isFillAlign": False})
    return attrs

class FloatField(field.FloatField):
  widget = NumericInput

class DecimalField(field.DecimalField):
  widget = NumericInput

class RegexField(field.RegexField):
  pass

class EmailField(field.EmailField):
  pass

class FileField(field.FileField):
  pass

class ImageField(field.ImageField):
  pass

class URLField(field.URLField):
  pass

class BooleanField(field.BooleanField):
  pass

class NullBooleanField(field.NullBooleanField):
  pass

class ListField(field.ListField):
  pass

class DictField(field.DictField):
  pass

class AdapterField(field.AdapterField):
  pass

class ChoiceField(field.ChoiceField):
  pass

class FilePathField(field.FilePathField):
  pass

class TypedChoiceField(field.TypedChoiceField):
  pass

class MultipleChoiceField(field.MultipleChoiceField):
  pass

class TypedMultipleChoiceField(field.TypedMultipleChoiceField):
  pass

class IPAddressField(field.IPAddressField):
  pass

class GenericIPAddressField(field.GenericIPAddressField):
  pass

class SlugField(field.SlugField):
  pass

class StringGroupFilterField(Field):
  widget = StringGroupFilterInput

class ModelValidateGroupField(Field):
  widget = ModelValidateGroupInput
