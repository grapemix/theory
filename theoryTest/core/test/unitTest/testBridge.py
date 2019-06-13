# -*- coding: utf-8 -*-
##### System wide lib #####

##### Theory lib #####
from theory.apps.model import Adapter, AdapterBuffer, Command
from theory.gui import field
from theory.test.testcases import TestCase

##### Theory third-party lib #####

##### Local app #####

##### Theory app #####

##### Misc #####
from testBase.command import *
from testBase.bridge import Bridge

__all__ = ('BridgeTestCase', )

class ThirdpartyClass(object):

  def saveCmdForTest(self, cmd):
    self.cmd = cmd

class BridgeTestCase(TestCase):
  fixtures = ["adapter",]
  def setUp(self):
    self.bridge = Bridge()
    self.asyncChain1CommandModel = AsyncChain1.getCmdModel()
    self.asyncChain2CommandModel = AsyncChain2.getCmdModel()
    self.adapterBufferModel = AdapterBuffer()

  def testParamFormAssignment(self):
    firstCmd = AsyncChain1()
    firstCmd.paramForm = firstCmd.ParamForm()
    firstCmd.paramForm.fields["verbosity"].finalData = 1
    self.assertTrue(firstCmd.paramForm.isValid())
    firstCmd.run(paramFormData={"verbosity": 1})

    self.assertEqual(firstCmd.paramForm.clean()["verbosity"], 1)

    firstCmd = AsyncChain1()
    # test param form non existed here
    firstCmd.paramForm = firstCmd.ParamForm()
    firstCmd.paramForm.fields["verbosity"].finalData = 2
    self.assertTrue(firstCmd.paramForm.isValid())
    firstCmd.run(paramFormData={"verbosity": 2})

    self.assertEqual(firstCmd.paramForm.clean()["verbosity"], 2)

  def testGetCmdComplex(self):
    self.asyncChain1CommandModel = AsyncChain1.getCmdModel()
    cmd = self.bridge.getCmdComplex(self.asyncChain1CommandModel, [], {"verbosity": 99})
    self.assertEqual(cmd.paramForm.fields["verbosity"].finalData, 99)
    self.assertEqual(cmd.paramForm.clean()["verbosity"], 99)

  def testBridgeToDb(self):
    secondCmdModel = self.asyncChain2CommandModel

    firstCmd = AsyncChain1()
    firstCmd.paramForm = firstCmd.ParamForm()
    firstCmd.run(paramFormData={})

    secondCmdModel.save()
    data = self.bridge.bridgeToDb(firstCmd, secondCmdModel)

    self.assertEqual(data, '{"stdIn": "asyncChain1"}')
    self.assertEqual(AdapterBuffer.objects.count(), 1)
    savedAdapterBufferModel = AdapterBuffer.objects.all()[0]
    self.assertEqual(savedAdapterBufferModel.toCmd.id, secondCmdModel.id)
    self.assertEqual(savedAdapterBufferModel.data, data)

  def testBridgeFromDb(self):
    self.adapterBufferModel.fromCmd = self.asyncChain1CommandModel
    secondCmdModel = self.asyncChain2CommandModel

    # thirdparty is nextStep command so far
    thirdpartyObj = ThirdpartyClass()

    self.adapterBufferModel.toCmd = secondCmdModel
    self.adapterBufferModel.data = '{"stdIn": "asyncChain1"}'
    self.adapterBufferModel.adapter = Adapter.objects.get(name="StdPipe")
    self.assertEqual(self.adapterBufferModel.fromCmd.classImportPath,
        "testBase.command.asyncChain1.AsyncChain1")
    self.assertEqual(self.adapterBufferModel.toCmd.classImportPath,
        "testBase.command.asyncChain2.AsyncChain2")
    self.bridge.bridgeFromDb(
        self.adapterBufferModel,
        thirdpartyObj.saveCmdForTest)
    self.assertTrue(isinstance(thirdpartyObj.cmd, AsyncChain2))
    self.assertEqual(
        thirdpartyObj.cmd.paramForm.fields['stdIn'].finalData,
        u'asyncChain1')
    self.assertEqual(
        thirdpartyObj.cmd.paramForm.fields['stdIn'].finalData,
        u'asyncChain1')
    self.assertEqual(
        thirdpartyObj.cmd.paramForm.cleanedData['stdIn'],
        u'asyncChain1')

  def test_execeuteCommand(self):
    self.assertEqual(
        self.asyncChain1CommandModel.runMode,
        Command.RUN_MODE_ASYNC
        )
    firstCmd = AsyncChain1()
    firstCmd.paramForm = firstCmd.ParamForm()
    self.bridge._executeCommand(firstCmd, self.asyncChain1CommandModel)
    self.assertEqual(firstCmd._stdOut, "asyncChain1")
    self.assertTrue(firstCmd.paramForm.isValid())

    cmdModel = SimpleChain1.getCmdModel()
    firstCmd = SimpleChain1()
    firstCmd.paramForm = firstCmd.ParamForm()
    self.bridge._executeCommand(firstCmd, cmdModel)
    self.assertTrue(firstCmd.paramForm.isValid())
