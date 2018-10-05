# -*- coding: utf-8 -*-
#!/usr/bin/env python
##### System wide lib #####
from abc import ABCMeta, abstractmethod
import json

##### Theory lib #####
from theory.apps.command.baseCommand import SimpleCommand
from theory.apps.model import AppModel
from theory.conf import settings
from theory.gui import field
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
        dynamicChoiceLst=(
          set(
            [("theory.apps", "theory.apps")] \
            + [
                (appName, appName)
                for appName in settings.INSTALLED_APPS
            ]
          )
        ),
        uiPropagate=[
          ("fields", "queryset", "appName",),
        ],
        )
    modelName = field.ChoiceField(
        label="Model Name",
        helpText="The name of models to be listed",
        initData=None,
        dynamicChoiceLst=(
          [(i.name, i.name) for i in AppModel.objects.only(
            "name"
          ).filter(app="theory.apps")]),
        uiPropagate=[
          ("fields", "queryset", "mdlName",),
        ],
        )
    queryset = field.QuerysetField(
        required=False,
        label="Queryset",
        helpText="The queryset to be processed",
        initData=None,
        isSkipInHistory=True,
        )
    queryFilter = field.DictField(
        field.TextField(),
        field.TextField(),
        label="QueryFilter",
        initData={},
        helpText="The simple filter being applied to the query"
        )
    pageNum = field.IntegerField(
        label="page number",
        initData=1,
        required=False
        )
    pageSize = field.IntegerField(
        label="page size",
        helpText="Number of items per page",
        initData=500,
        required=False
        )

    def _getQuerysetByAppAndModel(self, appName, modelName):
      appModel = AppModel.objects.only("importPath").get(
          app=appName,
          name=modelName
          )
      return importClass(appModel.importPath).objects.all()

    def _updateQueryset(self, appName, modelName):
      self.fields["queryset"].appName = appName
      self.fields["queryset"].modelName = modelName
      self.fields["queryset"].queryset = \
          self._getQuerysetByAppAndModel(
              appName,
              modelName
              )

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
        self.fields["modelName"].dynamicChoiceLst = self._getModelNameChoices(appName)
        modelName = self.fields["modelName"].dynamicChoiceLst[0][0]
        self._updateQueryset(appName, modelName)

    def _getModelNameChoices(self, appName):
      return list(set(
          [(i.name, i.name) for i in AppModel.objects.only(
            "name"
          ).filter(app=appName)]
      ))

    def appNameFocusChgCallback(self, appName):
      return {
          "modelName": {
            "choices": self._getModelNameChoices(appName),
            "initData": None,
          },
      }

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
    formData = self.paramForm.clean()
    try:
      # Queryset can be passed as id list
      self.selectedIdLst = \
          self.paramForm.fields["queryset"].initData.valuesList(
              'id',
              flat=True
              )
    except AttributeError:
      # For initData being assigned in Form directly
      self.selectedIdLst = self.paramForm.fields["queryset"].initData

    self.actionQ.append({
        "action": "upsertSpreadSheet",
        "val": json.dumps({
          "appName": formData["appName"],
          "mdlName": formData["modelName"],
          "isEditable": True,
          "selectedIdLst": self.selectedIdLst,
          "pageNum": formData["pageNum"],
          "pageSize": formData["pageSize"],
          })
        })
