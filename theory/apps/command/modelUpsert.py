# -*- coding: utf-8 -*-
#!/usr/bin/env python
##### System wide lib #####
from copy import deepcopy

##### Theory lib #####
from theory.apps.adapter.terminalAdapter import TerminalForm
from theory.apps.command.baseCommand import SimpleCommand
from theory.apps.model import AppModel
from theory.conf import settings
from theory.gui import field
from theory.gui.etk.element import getNewUiParam
from theory.gui.etk.form import StepFormBase
#from theory.gui.model import GuiModelForm
from theory.gui.model import ModelForm, ModelChoiceField
from theory.utils.importlib import importClass

##### Theory third-party lib #####

##### Local app #####

##### Theory app #####

##### Misc #####

class ModelUpsert(SimpleCommand):
  """
  To update model if an instance id is provided. Otherwise, this class will
  insert a model.
  """
  name = "modelUpsert"
  verboseName = "modelUpsert"
  _drums = {"Dummy": 1,}

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
    queryset = ModelChoiceField(
        queryset=AppModel.objects.all(),
        required=False,
        label="instance id",
        helpText="The instance to be edited",
        initData=None,
        isSkipInHistory=True,
        )

    isInNewWindow = field.BooleanField(
        label="Is in new window",
        helpText="Is shown in new window",
        required=False,
        initData=False,
        )
    # Not yet in this version
    #queryset = field.QuerysetField(
    #    required=False,
    #    label="Queryset",
    #    helpText="The queryset to be processed",
    #    initData=[],
    #    isSkipInHistory=True,
    #    )

    def __init__(self, *args, **kwargs):
      super(SimpleCommand.ParamForm, self).__init__(*args, **kwargs)
      self._preFillFieldProperty()

    def _getQuerysetByAppAndModel(self, appName, modelName):
      appModel = AppModel.objects.get(
          app=appName,
          name=modelName
          )
      return importClass(appModel.importPath).objects.all()

    def fillInitFields(self, cmdModel, cmdArgs, cmdKwargs):
      super(ModelUpsert.ParamForm, self).fillInitFields(
          cmdModel,
          cmdArgs,
          cmdKwargs
          )
      if len(cmdArgs) == 2:
        # This is for QuerysetField preset the form for modelSelect
        appName = self.fields["appName"].initData
        self.fields["modelName"].choices = self._getModelNameChoices(appName)
      elif cmdKwargs.has_key("appName") and cmdKwargs.has_key("modelName"):
        # For perseting by kwargs
        self.fields["modelName"].choices = \
            self._getModelNameChoices(cmdKwargs["appName"])
      self.fields["queryset"].queryset = \
          self._getQuerysetByAppAndModel(
              self.fields["appName"].finalData,
              self.fields["modelName"].finalData
              )

    def _preFillFieldProperty(self):
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
      modelName = field.choices[0][0]
      field.widget.reset(choices=field.choices)

      field.queryset = \
          self._getQuerysetByAppAndModel(
              appName,
              modelName
              )

    def modelNameFocusChgCallback(self, *args, **kwargs):
      field = self.fields["queryset"]
      self.fields["modelName"].finalData = None
      field.model = self.fields["modelName"].clean(
          self.fields["modelName"].finalData
          )

      field.queryset = self._getQuerysetByAppAndModel(
          self.fields["appName"].finalData,
          self.fields["modelName"].finalData
          )


  def getModelFormKlass(self, appModel, modelKlass):
    class DynamicModelForm(ModelForm, StepFormBase):
      class Meta:
        model = modelKlass
        #fields = appModel.formField
        exclude = []
    return DynamicModelForm

  def postApplyChange(self):
    pass

  def cleanParamForm(self, btn, dummy):
    if(self.modelForm.isValid()):
      self.modelForm.save()
      if self.paramForm.clean()["isInNewWindow"]:
        self._uiParam["cleanUpCrtFxn"](None, None)
      self.postApplyChange()

      self._uiParam["bx"].clear()

      o = TerminalForm()
      o.fields["stdOut"].initData = "Model has been saved successfully."
      o.generateForm(**self._uiParam)
    else:
      # TODO: integrate with std reactor error system
      self.modelForm.showErrInFieldLabel()

  def run(self, *args, **kwargs):
    f = self.paramForm.clean()
    if not f["isInNewWindow"]:
      self._uiParam["bx"].clear()

    appModel = AppModel.objects.get(app=f["appName"], name=f["modelName"])
    self.modelKlass = importClass(appModel.importPath)
    modelFormKlass = self.getModelFormKlass(appModel, self.modelKlass)
    self.instance = None
    if(f["queryset"] is not None):
      self.modelForm = modelFormKlass(instance=f["queryset"])
    else:
      self.modelForm = modelFormKlass()
    self.modelForm._nextBtnClick = self.cleanParamForm

    if f["isInNewWindow"]:
      self._uiParam = getNewUiParam()

    self.modelForm.generateForm(**self._uiParam)
    self.modelForm.generateStepControl(
        cleanUpCrtFxn=self._uiParam["cleanUpCrtFxn"]
        )
