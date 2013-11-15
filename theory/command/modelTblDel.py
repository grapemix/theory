# -*- coding: utf-8 -*-
#!/usr/bin/env python
##### System wide lib #####

##### Theory lib #####
from theory.command.modelTblFilterBase import ModelTblFilterBase

##### Theory third-party lib #####

##### Local app #####

##### Theory app #####

##### Misc #####

__all__ = ("modelTblDel",)

class ModelTblDel(ModelTblFilterBase):
  """
  To delete a model
  """
  name = "modelTblDel"
  verboseName = "model table delete"

  def _applyChangeOnQueryset(self):
    for model in self.paramForm.clean()["queryset"]:
      model.delete()
    self._stdOut += "{0} model has been deleted."\
        .format(len(self.paramForm.clean()["queryset"]))

