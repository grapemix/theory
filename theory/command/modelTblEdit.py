# -*- coding: utf-8 -*-
#!/usr/bin/env python
##### System wide lib #####

##### Theory lib #####
from theory.command.baseCommand import SimpleCommand
from theory.conf import settings
from theory.core.bridge import Bridge
from theory.gui import field
from theory.utils.importlib import import_class

##### Theory third-party lib #####

##### Local app #####

##### Theory app #####

##### Misc #####

__all__ = ("modelTblEdit",)

class ModelTblEdit(SimpleCommand):
  """
  To edit a model
  """
  name = "modelTblEdit"
  verboseName = "model table edit"
  _gongs = ["QuerysetAsSpreadsheet", ]
  _drums = {"Terminal": 1,}

  class ParamForm(SimpleCommand.ParamForm):
    appName = field.ChoiceField(label="Application Name",
        help_text="Commands provided by this application",
        choices=(set([("theory", "theory")] +
          [(settings.INSTALLED_APPS[i], settings.INSTALLED_APPS[i])
            for i in range(len(settings.INSTALLED_APPS))])),
        )
    modelName = field.TextField(label="Model Name",
        help_text="The name of the model to be listed",
        )
    queryset = field.QuerysetField(required=False, label="Queryset",
        help_text="The queryset to be processed", initData=[])
    # Not yet in this version
    #pagination = field.IntegerField(label="pagination",
    #    help_text="Number of items per page",
    #    initData=50,
    #    required=False)

  @property
  def queryset(self):
    return self._queryset

  @queryset.setter
  def queryset(self, queryset):
    self._queryset = queryset

  def _saveEditChanges(self):
    for model in self.paramForm.clean()["queryset"]:
      model.save()
    self._stdOut += "{0} model has been saved."\
        .format(len(self.paramForm.clean()["queryset"]))

  def run(self):
    self._stdOut = ""
    isQuerysetNonEmpty = self._fetchQueryset()
    if(isQuerysetNonEmpty):
      bridge = Bridge()
      (delMe, newParamForm) = bridge.bridgeToSelf(self)
      self.paramForm = newParamForm
      self.paramForm.full_clean()
      self._saveEditChanges()
    else:
      self._stdOut += "No data found."

  def _fetchQueryset(self):
    formData = self.paramForm.clean()

    if(len(formData["queryset"]) > 0):
      self.queryset = formData["queryset"]
      return True
    else:
      modelName = formData["modelName"]
      modelName = modelName[0].upper() + modelName[1:]
      self.modelKlass = import_class(
          "%s.model.%s" % (formData["appName"], modelName)
      )
      self.queryset = self.modelKlass.objects.all()
      if(len(self.queryset)>0):
        return True
    return False
