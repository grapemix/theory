# -*- coding: utf-8 -*-
#!/usr/bin/env python
##### System wide lib #####
from mongoengine import *
from .base import ModelMetaClass
import sys

##### Theory lib #####

##### Theory third-party lib #####

##### Local app #####

##### Theory app #####

##### Misc #####

class Model(Document):
  __metaclass__ = ModelMetaClass

  meta = { "abstract": True }

  def __init__(self, *args, **kwargs):
    self.meta = {}
    super(Model, self).__init__(*args, **kwargs)

