# -*- coding: utf-8 -*-
#!/usr/bin/env python
##### System wide lib #####

##### Theory lib #####
from theory.apps.command.modelTblFilterBase import ModelTblFilterBase

##### Theory third-party lib #####

##### Local app #####

##### Theory app #####

##### Misc #####

__all__ = ("modelTblEdit",)

class ModelTblEdit(ModelTblFilterBase):
  """
  To edit a model
  """
  name = "modelTblEdit"
  verboseName = "model table edit"
