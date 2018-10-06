# -*- coding: utf-8 -*-
#!/usr/bin/env python
##### System wide lib #####

##### Theory lib #####
from theory.apps.command.modelTblFilterBase import ModelTblFilterBase
from theory.apps.model import AppModel
from theory.db import transaction
from theory.utils.importlib import importClass

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
  _drums = {"Terminal": 1}

  @property
  def stdOut(self):
    return self._stdOut

  def run(self):
    self._stdOut = ""
    f = self.paramForm.clean()
    modelModel = AppModel.objects.get(
        app=f["appName"],
        name=f["modelName"]
        )
    modelKls = importClass(modelModel.importPath)
    with transaction.atomic():
      count = modelKls.objects.filter(id__in=f["queryset"]).count()
      if len(f["queryset"]) == count:
        modelKls.objects.filter(id__in=f["queryset"]).delete()
        self._stdOut = "{} models have been deleted".format(count)
      else:
        self._stdOut = (
          "Only {} have been found and hence nothing has been deleted"
        ).format(
          modelKls.objects.filter(
            id__in=f["queryset"]
          ).valuesList("id", flat=True)
        )
