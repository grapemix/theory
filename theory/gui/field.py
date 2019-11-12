# -*- coding: utf-8 -*-
#!/usr/bin/env python
##### System wide lib #####

##### Theory lib #####
from theory.conf import settings
from theory.utils.importlib import importModule

##### Theory third-party lib #####

##### Local app #####

##### Theory app #####

##### Misc #####

# 1) Developer should import this class instead of specific tookkit's field
# 2) Try your best to use 'from theory.gui import field' instead of
#    'from theory.gui.field import *' to avoid the name collision
#    between field and mongoenigne.

def _importModule():
  supportModuleLst = (
    'Field', 'TextField', 'IntegerField',
    'DateField', 'TimeField', 'DateTimeField', 'RegexField', 'EmailField',
    'URLField', 'BooleanField', 'NullBooleanField', 'ChoiceField',
    'MultipleChoiceField', 'ListField', 'DictField', 'AdapterField',
    'FileField', 'ImageField', 'FilePathField', 'ImagePathField', 'DirPathField',
    'ComboField', 'MultiValueField',
    #'SplitDateTimeField',
    'FloatField', 'DecimalField', 'IPAddressField', 'GenericIPAddressField',
    'SlugField', 'TypedChoiceField', 'TypedMultipleChoiceField',
    'StringGroupFilterField', 'ModelValidateGroupField', 'PythonModuleField',
    'PythonClassField', 'DynamicModelIdField', 'DynamicModelSetField',
    'QuerysetField', 'ObjectIdField', 'BinaryField', 'GeoPointField',
  )

  module = importModule("theory.gui.{0}.field".format(settings.UI_TOOLKIT))
  # WARNING: make sure all UI's dbus import are not inside the fxn or
  # grpc+gevent hell will be shown

  for field in supportModuleLst:
    if(hasattr(module, field)):
        globals()[field] = getattr(module, field)
        #vars()[field] = getattr(module, field)

_importModule()
