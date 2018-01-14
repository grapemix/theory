# -*- coding: utf-8 -*-
#!/usr/bin/env python
##### System wide lib #####

##### Theory lib #####

##### Theory third-party lib #####

##### Local app #####
from . import BaseUIAdapter

##### Theory app #####

##### Misc #####

class DummyAdapter(BaseUIAdapter):
  """
  This adapter do nothing but just not rendering anything. One use case for
  this adapter is to avoid the auto bx cleaning from reactor because some
  command execute other command which might had its drum. In that case, a
  command is rendering something within its context and want to preserve the
  new rendering piece.
  """
  def render(self, *args, **kwargs):
    return []
