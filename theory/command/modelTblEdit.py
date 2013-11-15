# -*- coding: utf-8 -*-
#!/usr/bin/env python
##### System wide lib #####

##### Theory lib #####
from theory.command.modelTblFilterBase import ModelTblFilterBase

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

  def _applyChangeOnQueryset(self):
    for model in self.paramForm.clean()["queryset"]:
      model.save()
    self._stdOut += "{0} model has been saved."\
        .format(len(self.paramForm.clean()["queryset"]))

