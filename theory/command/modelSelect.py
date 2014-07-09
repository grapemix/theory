# -*- coding: utf-8 -*-
#!/usr/bin/env python
##### System wide lib #####

##### Theory lib #####
from theory.command.modelTblFilterBase import ModelTblFilterBase
from theory.gui import field

##### Theory third-party lib #####

##### Local app #####

##### Theory app #####

##### Misc #####

class ModelSelect(ModelTblFilterBase):
  """
  To select model
  """
  name = "modelSelect"
  verboseName = "modelSelect"

  def _applyChangeOnQueryset(self):
    self.queryset = []
    for model in self.paramForm.clean()["queryset"]:
      self.queryset.append(model.id)
