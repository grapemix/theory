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

class Model(Document):
  __metaclass__ = TopLevelDocumentMetaclass

  meta = { "abstract": True }

  def __init__(self, *args, **kwargs):
    self.meta = {}
    self.meta["collection"] = "%s_%s" % (sys.modules[self.__module__].__name__.split('.')[-2], self._get_collection_name())
    super(Model, self).__init__(*args, **kwargs)

