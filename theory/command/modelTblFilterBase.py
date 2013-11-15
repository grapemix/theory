# -*- coding: utf-8 -*-
#!/usr/bin/env python
##### System wide lib #####
from abc import ABCMeta, abstractmethod

##### Theory lib #####
from theory.command.baseCommand import SimpleCommand
from theory.conf import settings
from theory.core.bridge import Bridge
from theory.gui import field
from theory.model import AppModel
from theory.utils.importlib import import_class

##### Theory third-party lib #####

##### Local app #####

##### Theory app #####

##### Misc #####

__all__ = ("modelTblFilterBase",)

class ModelTblFilterBase(SimpleCommand):
  """
  It is a abstract base for all model tabel filter related command.
  """
  __metaclass__ = ABCMeta
  _gongs = ["QuerysetAsSpreadsheet", ]
  _drums = {"Terminal": 1,}

  class ParamForm(SimpleCommand.ParamForm):
    appName = field.ChoiceField(label="Application Name",
        help_text="The name of applications to be listed",
        initData="theory",
        choices=(set([("theory", "theory")] +
          [(settings.INSTALLED_APPS[i], settings.INSTALLED_APPS[i])
            for i in range(len(settings.INSTALLED_APPS))])),
        )
    modelName = field.ChoiceField(label="Model Name",
        help_text="The name of models to be listed",
        )
    queryset = field.QuerysetField(
        required=False,
        label="Queryset",
        help_text="The queryset to be processed",
        initData=[],
        isSkipInHistory=True,
        )
    queryFilter = field.DictField(
        field.TextField(),
        field.TextField(),
        label="QueryFilter",
        initData={},
        help_text="The simple filter being applied to the query"
        )
    # Not yet in this version
    #pagination = field.IntegerField(label="pagination",
    #    help_text="Number of items per page",
    #    initData=50,
    #    required=False)


    def __init__(self, *args, **kwargs):
      super(SimpleCommand.ParamForm, self).__init__(*args, **kwargs)
      self.preFillFields()

    def preFillFields(self):
      appName = self.fields["appName"].initData
      self.fields["modelName"].choices = self._getModelNameChoices(appName)

    def _getModelNameChoices(self, appName):
      return set(
          [(i.name, i.name) for i in AppModel.objects.filter(app=appName)]
      )

    def appNameFocusChgCallback(self, *args, **kwargs):
      field = self.fields["appName"]
      appName = field.clean(field.finalData)
      field.finalData = None

      field = self.fields["modelName"]
      field.choices = self._getModelNameChoices(appName)
      field.widget.reset(choices=field.choices)

      field = self.fields["queryset"]
      field.app = appName

    def modelNameFocusChgCallback(self, *args, **kwargs):
      field = self.fields["queryset"]
      self.fields["modelName"].finalData = None
      field.model = self.fields["modelName"].clean(
          self.fields["modelName"].finalData
          )

  @property
  def queryset(self):
    return self._queryset

  @queryset.setter
  def queryset(self, queryset):
    self._queryset = queryset

  @abstractmethod
  def _applyChangeOnQueryset(self):
    pass

  def run(self):
    self._stdOut = ""
    isQuerysetNonEmpty = self._fetchQueryset()
    if(isQuerysetNonEmpty):
      bridge = Bridge()
      (delMe, newParamForm) = bridge.bridgeToSelf(self)
      self.paramForm = newParamForm
      self.paramForm.full_clean()
      self._applyChangeOnQueryset()
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
      self.queryset = self.modelKlass.objects.filter(
          **dict(formData["queryFilter"])
          )
      if(len(self.queryset)>0):
        return True
    return False
