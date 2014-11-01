# -*- coding: utf-8 -*-
#!/usr/bin/env python
##### System wide lib #####
from abc import ABCMeta, abstractmethod

##### Theory lib #####
from theory.apps.command.baseCommand import SimpleCommand
from theory.apps.model import AppModel
from theory.conf import settings
from theory.core.bridge import Bridge
from theory.core.exceptions import CommandError
from theory.gui import field
from theory.gui.model import ModelMultipleChoiceField
from theory.utils.importlib import importClass

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
        helpText="The name of applications to be listed",
        initData="theory.apps",
        choices=(set([("theory.apps", "theory.apps")] +
          [(settings.INSTALLED_APPS[i], settings.INSTALLED_APPS[i])
            for i in range(len(settings.INSTALLED_APPS))])),
        )
    modelName = field.ChoiceField(label="Model Name",
        helpText="The name of models to be listed",
        )
    queryset = ModelMultipleChoiceField(
        queryset=AppModel.objects.none(),
        required=False,
        label="Queryset",
        helpText="The queryset to be processed",
        initData=[],
        isSkipInHistory=True,
        )
    queryFilter = field.DictField(
        field.TextField(),
        field.TextField(),
        label="QueryFilter",
        initData={},
        helpText="The simple filter being applied to the query"
        )
    # Not yet in this version
    #pagination = field.IntegerField(label="pagination",
    #    help_text="Number of items per page",
    #    initData=50,
    #    required=False)


    def __init__(self, *args, **kwargs):
      super(SimpleCommand.ParamForm, self).__init__(*args, **kwargs)
      self._preFillFieldProperty()

    #def _validateNonSingularField(self):
    #  # Not being used for now since we can only allow to key in id list,
    #  # but not queryset. In that way, we cannot extract appName and
    #  # modelName from the id list. So in the widget level, we still
    #  # have to treat appName and modelName as required, even though
    #  # appName and modelName are not neccessary required in the field level
    #  try:
    #    field = self.fields["queryset"]
    #    if(not self.isLazy):
    #      field.forceUpdate()
    #    value = field.finalData
    #    value = field.clean(value)
    #    self.emptyForgivenLst = ["appName", "modelName"]
    #  except:
    #    pass

    def _getQuerysetByAppAndModel(self, appName, modelName):
      appModel = AppModel.objects.get(
          app=appName,
          name=modelName
          )
      return importClass(appModel.importPath).objects.all()

    def _preFillFieldProperty(self):
      appName = self.fields["appName"].initData
      self.fields["modelName"].choices = self._getModelNameChoices(appName)

    def fillInitFields(self, cmdModel, cmdArgs, cmdKwargs):
      super(ModelTblFilterBase.ParamForm, self).fillInitFields(
          cmdModel,
          cmdArgs,
          cmdKwargs
          )
      if len(cmdArgs) == 3 or (
          cmdKwargs.has_key("appName")
          and cmdKwargs.has_key("modelName")
          ):
        # This is for QuerysetField preset the form for modelSelect
        appName = self.fields["appName"].initData
        self.fields["modelName"].choices = self._getModelNameChoices(appName)
        modelName = self.fields["modelName"].initData
        self.fields["queryset"].appName = appName
        self.fields["queryset"].modelName = modelName
        self.fields["queryset"].queryset = \
            self._getQuerysetByAppAndModel(
                appName,
                modelName
                )


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
      initChoice = field.choices[0][0]
      field.widget.reset(choices=field.choices)

      field = self.fields["queryset"]
      field.appName = appName
      field.modelName = initChoice

      field.queryset = self._getQuerysetByAppAndModel(
          appName,
          initChoice
          )

    def modelNameFocusChgCallback(self, *args, **kwargs):
      field = self.fields["queryset"]
      self.fields["modelName"].finalData = None
      field.model = self.fields["modelName"].clean(
          self.fields["modelName"].finalData
          )

      field.queryset = self._getQuerysetByAppAndModel(
          field.appName,
          self.fields["modelName"].finalData
          )

  @property
  def queryIdSet(self):
    # Since the ModelChoiceField will accept queryset and id as list,
    # we need a convenience way to extract all id list. Also, we don't
    # want to validate the whole form, as we might change the queryset
    # in the future, we don't want to cache the old data.
    field = self.paramForm.fields["queryset"]
    value = field.finalData
    try:
      value = field.clean(value, True)
    except ValidationError:
      return []
    try:
      return [model.id for model in value]
    except AttributeError:
      return value

  @property
  def selectedIdLst(self):
    return self._selectedIdLst

  @selectedIdLst.setter
  def selectedIdLst(self, selectedIdLst):
    self._selectedIdLst = selectedIdLst

  @property
  def appModelFieldParamMap(self):
    return self._appModelFieldParamMap

  @appModelFieldParamMap.setter
  def appModelFieldParamMap(self, appModelFieldParamMap):
    self._appModelFieldParamMap = appModelFieldParamMap

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
      self.paramForm.fullClean()
      self._applyChangeOnQueryset()
      del self.appModel
    else:
      self._stdOut += "No data found."

  def _fetchQueryset(self):
    formData = self.paramForm.clean()

    if(not hasattr(self, "appModel")):
      appModel = AppModel.objects.get(
          app=formData["appName"],
          name=formData["modelName"]
          )
      self.modelKlass = importClass(appModel.importPath)
      self.appModel = appModel
    if formData["queryset"] is None:
      # For ModelChoiceField
      formData["queryset"] = []
    try:
      # Queryset can be passed as id list
      self.selectedIdLst = \
          self.paramForm.fields["queryset"].initData.valuesList(
              'id',
              flat=True
              )
    except AttributeError:
      self.selectedIdLst = self.paramForm.fields["queryset"].initData

    # The field queryset stored three type of data
    # 1) queryset: as the available choices
    # 2) initData: as the pre-selected choices (often seen in instance)
    # 3) finalData: as the user-selected choices
    # However, adapter only accept finalData. So we create
    # self.selectedIdLst to pass initData and use
    # fields["queryset"].finalData to pass queryset. After bridgeToSelf,
    # adapter will pass the user-selected choices as queryset's finalData.
    self.paramForm.cleanedData["queryset"] = \
        self.paramForm.fields["queryset"].queryset.filter(
            **dict(formData["queryFilter"])
            )
    if(len(self.paramForm.cleanedData["queryset"])>0):
      return True
    return False
