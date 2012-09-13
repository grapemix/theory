# -*- coding: utf-8 -*-
#!/usr/bin/env python
##### System wide lib #####
from abc import ABCMeta, abstractmethod

##### Theory lib #####

##### Theory third-party lib #####

##### Local app #####

##### Theory app #####

##### Misc #####

class BaseAdapter(object):
  abstract = True
  def run(self):
    """This function should be called after all properties were being assigned.
    """
    return True

class BaseUIAdapter(BaseAdapter):
  abstract = True
  """Any adapter which interacted with UI should inheritage from this class.
  This class should be platform semi-independent. All UI related param is
  passed to fields and then to widget transparently."""

  @abstractmethod
  def render(self, *args, **kwargs):
    pass
