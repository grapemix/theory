# -*- coding: utf-8 -*-
#!/usr/bin/env python
##### System wide lib #####
from mongoengine import *
from mongoengine.base import TopLevelDocumentMetaclass
import sys

##### Theory lib #####

##### Theory third-party lib #####

##### Local app #####

##### Theory app #####

##### Misc #####

class ModelMetaClass(TopLevelDocumentMetaclass):
  def __new__(cls, name, bases, attrs):
    super_new = super(ModelMetaClass, cls).__new__
    new_class = super_new(cls, name, bases, attrs)

    # Figure out the app_label by looking one level up.
    # For 'django.contrib.sites.models', this would be 'sites'.
    model_module = sys.modules[new_class.__module__]
    model_module_token = model_module.__name__.split('.')
    if(model_module_token[-2]=="model"):
      # for case like appLabel.model.modelFile.modelKlass
      app_label = model_module_token[-3]
    else:
      # for case like appLabel.model.modelKlass
      app_label = model_module_token[-2]

    try:
      new_class._meta["collection"] = "%s_%s" % (app_label, new_class._meta["collection"])
    except KeyError:
      pass
    new_class._meta["app_label"] = app_label

    return new_class


