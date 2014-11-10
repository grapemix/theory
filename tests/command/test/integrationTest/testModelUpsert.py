# -*- coding: utf-8 -*-
##### System wide lib #####

##### Theory lib #####
from theory.apps.model import Command
from theory.conf import settings

##### Theory third-party lib #####

##### Local app #####
from .baseCommandTestCase import BaseCommandTestCase

##### Theory app #####

##### Misc #####

__all__ = ('ModelUpsertTestCase',)

class ModelUpsertTestCase(BaseCommandTestCase):
  fixtures = ["theory", "combinatoryAppConfig"]
  def __init__(self, *args, **kwargs):
    super(ModelUpsertTestCase, self).__init__(*args, **kwargs)
    self.cmdModel = Command.objects.get(name="modelUpsert")

  def setUp(self):
    self.cmd = self._getCmd(
        self.cmdModel,
        kwargs={
          #"appName": "testBase",
          #"modelName": "CombinatoryModelWithDefaultValue",
          "appName": "theory.apps",
          "modelName": "Command",
          }
        )
    Command(app="testApp", name="testCmd").save()
    self._validateParamForm(self.cmd)
    if not hasattr(settings, "dimensionHints"):
      settings.dimensionHints = {
          "minWidth": 640,
          "minHeight": 480,
          "maxWidth": 640,
          "maxHeight": 480,
          }


  def testAddingFormCreation(self):
    self._executeCommand(self.cmd, self.cmdModel, uiParam=self.uiParam)
    self.cmd.paramForm._nextBtnClick()

  def testListFieldError(self):
    self._executeCommand(self.cmd, self.cmdModel, uiParam=self.uiParam)
    self.cmd.paramForm._nextBtnClick()

    self.cmd.modelForm._nextBtnClick(None, None)
    self.assertEqual(
        self.cmd.modelForm.errors,
        {
          "app": [u"This field is required.",],
          "moodSet": [u"This field is required.",],
          "name": [u"This field is required.",],
          "sourceFile": [u"This field is required.",],
          }
        )

  def testAsAdding(self):
    self._executeCommand(self.cmd, self.cmdModel, uiParam=self.uiParam)
    self.cmd.paramForm._nextBtnClick()

    self.cmd.modelForm.fields["app"].finalData = "testBase"
    self.cmd.modelForm.fields["name"].finalData = "testCmd2"
    self.cmd.modelForm.fields["moodSet"].finalData = [1,2,]
    self.cmd.modelForm.fields["sourceFile"].finalData = \
        "testBase.command.testCmd"

    self.cmd.modelForm._nextBtnClick(None, None)
    self.assertEqual(self.cmd.modelForm.errors, {})
    self.assertEqual(Command.objects.filter(name="testCmd2").count(), 1)

    self.assertEqual(
        list(Command.objects.get(name="testCmd2").moodSet.valuesList(
          "id",
          flat=True
          )),
        [1,2]
        )

  def testAsEditing(self):
    self.assertEqual(
        list(Command.objects.get(pk=1).moodSet.valuesList(
          "id",
          flat=True
          )),
        [1]
        )
    # getCmdComplex will validate the form automatically
    self.cmd = self._getCmd(
        self.cmdModel,
        kwargs={
          "appName": "theory.apps",
          "modelName": "Command",
          "queryset": "1",
          }
        )
    self._validateParamForm(self.cmd)

    self._executeCommand(self.cmd, self.cmdModel, uiParam=self.uiParam)
    self.cmd.paramForm._nextBtnClick()

    self.assertEqual(self.cmd.modelForm.instance.pk, 1)
    self.cmd.modelForm.fields["moodSet"].finalData = [1,2]
    self.cmd.modelForm.fields["comment"].finalData = "new comment"
    self.cmd.cleanParamForm(None, None)
    self.assertEqual(self.cmd.modelForm.errors, {})

    self.assertEqual(
        list(Command.objects.get(pk=1).moodSet.valuesList(
          "id",
          flat=True
          )),
        [1,2]
        )

    self.assertEqual(
        Command.objects.get(pk=1).comment,
        "new comment"
        )

  def testPureSaving(self):
    self._executeCommand(self.cmd, self.cmdModel, uiParam=self.uiParam)
    self.cmd.paramForm._nextBtnClick()

    self.cmd.modelForm.fields["app"].finalData = "testBase"
    self.cmd.modelForm.fields["name"].finalData = "testCmd2"
    self.cmd.modelForm.fields["moodSet"].finalData = [1,2]
    self.cmd.modelForm.fields["sourceFile"].finalData = \
        "testBase.command.testCmd"

    self.cmd.cleanParamForm(None, None)
    self.assertEqual(self.cmd.modelForm.errors, {})

    self.assertEqual(Command.objects.filter(name="testCmd2").count(), 1)

    self.assertEqual(
        list(Command.objects.get(name="testCmd2").moodSet.valuesList(
          "id",
          flat=True
          )),
        [1,2]
        )

if __name__ == '__main__':
  unittest.main()
