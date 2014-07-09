# -*- coding: utf-8 -*-
#!/usr/bin/env python
##### System wide lib #####
from copy import deepcopy

##### Theory lib #####
from theory.conf import settings
from theory.command.baseCommand import SimpleCommand
from theory.gui import field
from theory.gui.etk.element import getNewUiParam
from theory.gui.etk.form import StepFormBase
#from theory.gui.model import GuiModelForm
from theory.gui.model import ModelForm
from theory.model import AppModel
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
        help_text="The name of applications to be listed",
        initData="theory",
        choices=(set([("theory", "theory")] +
          [(settings.INSTALLED_APPS[i], settings.INSTALLED_APPS[i])
            for i in range(len(settings.INSTALLED_APPS))])),
        )
    modelName = field.ChoiceField(label="Model Name",
        help_text="The name of models to be listed",
        )
    instanceId = field.TextField(
        max_length=50,
        required=False,
        label="instance id",
        help_text="The instance to be edited",
        isSkipInHistory=True,
        )
    isInNewWindow = field.BooleanField(
        label="Is in new window",
        help_text="Is shown in new window",
        required=False,
        initData=False,
        )
    # Not yet in this version
    #queryset = field.QuerysetField(
    #    required=False,
    #    label="Queryset",
    #    help_text="The queryset to be processed",
    #    initData=[],
    #    isSkipInHistory=True,
    #    )

    def __init__(self, *args, **kwargs):
      super(SimpleCommand.ParamForm, self).__init__(*args, **kwargs)
      self._preFillFieldProperty()

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
      field.widget.reset(choices=field.choices)

  def getModelFormKlass(self, importPath):
    class DynamicModelForm(ModelForm, StepFormBase):
      class Meta:
        model = importPath
    return DynamicModelForm

  def postApplyChange(self):
    pass

  def cleanParamForm(self, btn, dummy):
    if(self.modelForm.is_valid()):
      dataInDict = self.modelForm.clean()
      if self.instance is None:
        self.instance = self.modelForm.instance
      for k, v in dataInDict.iteritems():
        setattr(self.instance, k, v)
      self.instance.save()
      if self.paramForm.clean()["isInNewWindow"]:
        self._uiParam["cleanUpCrtFxn"](None)
      self.postApplyChange()
    else:
      # TODO: integrate with std reactor error system
      self.modelForm.showErrInFieldLabel()

  def run(self, *args, **kwargs):
    f = self.paramForm.clean()
    if not f["isInNewWindow"]:
      self._uiParam["bx"].clear()

    appModel = AppModel.objects.get(app=f["appName"], name=f["modelName"])
    modelFormKlass = self.getModelFormKlass(appModel.importPath)
    self.instance = None
    self.modelKlass = importClass(appModel.importPath)
    if(f["instanceId"]!=""):
      self.instance = self.modelKlass.objects.get(id=f["instanceId"])
      self.modelForm = modelFormKlass(instance=self.instance)
    else:
      self.modelForm = modelFormKlass()
    self.modelForm._nextBtnClick = self.cleanParamForm

    if f["isInNewWindow"]:
      self._uiParam = getNewUiParam()

    self.modelForm.generateForm(**self._uiParam)
    self.modelForm.generateStepControl(
        cleanUpCrtFxn=self._uiParam["cleanUpCrtFxn"]
        )
