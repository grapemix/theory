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
    if(name=="Model"):
      attrs["__metaclass__"] = TopLevelDocumentMetaclass
    new_class = super_new(cls, name, bases, attrs)
    attrs["__metaclass__"] = ModelMetaClass

    # Figure out the app_label by looking one level up.
    # For 'django.contrib.sites.models', this would be 'sites'.
    model_module = sys.modules[new_class.__module__]
    app_label = model_module.__name__.split('.')[-2]

    if(hasattr(new_class, "_meta")):
      new_class._meta["collection"] = "%s_%s" % (app_label, new_class._meta["collection"])
      new_class._meta["app_label"] = app_label

    return new_class

class Model(Document):
  __metaclass__ = ModelMetaClass
  #__metaclass__ = TopLevelDocumentMetaclass

  #meta = { "abstract": False }
  #meta = { "abstract": True }

  '''
  meta = { "app_label": sys.modules[__module__].__name__.split('.')[-2] , "allow_inheritance": True}
  @classmethod
  def _get_collection_name(cls):
    """Returns the collection name for this class.
    """
    return cls._meta.get('app_label', "theory") + cls._meta.get('collection', None)
  '''
