# -*- coding: utf-8 -*-
##### System wide lib #####
from ludibrio import Stub

##### Theory lib #####
from theory.command.baseCommand import SimpleCommand, AsyncCommand, AsyncContainer
from theory.core.bridge import Bridge
from theory.gui import field
from theory.model import *
from theory.utils import unittest

##### Theory third-party lib #####

##### Local app #####

##### Theory app #####

##### Misc #####
from tests.base.command import *

__all__ = ('BridgeTestCase', )

class ThirdpartyClass(object):

  def saveCmdForTest(self, cmd):
    self.cmd = cmd

class BridgeTestCase(unittest.TestCase):
  def setUp(self):
    self.bridge = Bridge()
    self.asyncChain1CommandModel = AsyncChain1.getCmdModel()
    self.asyncChain2CommandModel = AsyncChain2.getCmdModel()
    self.adapterBufferModel = AdapterBuffer()
    AdapterBuffer.objects.all().delete()

  def testParamFormAssignment(self):
    firstCmd = AsyncChain1()
    firstCmd.paramForm = firstCmd.ParamForm()
    firstCmd.paramForm.fields["verbosity"].finalData = 1
    self.assertTrue(firstCmd.paramForm.is_valid())
    firstCmd.run()

    self.assertEqual(firstCmd.paramForm.clean()["verbosity"], 1)

    firstCmd = AsyncChain1()
    # test param form non existed here
    firstCmd.paramForm = firstCmd.ParamForm()
    firstCmd.paramForm.fields["verbosity"].finalData = 2
    self.assertTrue(firstCmd.paramForm.is_valid())
    firstCmd.run()

    self.assertEqual(firstCmd.paramForm.clean()["verbosity"], 2)

  def testGetCmdComplex(self):
    self.asyncChain1CommandModel = AsyncChain1.getCmdModel()
    cmd = self.bridge.getCmdComplex(self.asyncChain1CommandModel, [], {"verbosity": 99})
    self.assertEqual(cmd.paramForm.fields["verbosity"].initData, 99)
    self.assertEqual(cmd.paramForm.fields["verbosity"].finalData, 99)
    self.assertEqual(cmd.paramForm.clean()["verbosity"], 99)

  def testBridgeToDb(self):
    secondCmdModel = self.asyncChain2CommandModel

    firstCmd = AsyncChain1()
    firstCmd.paramForm = firstCmd.ParamForm()
    firstCmd.run()

    Command(name=firstCmd.name, app="", mood=[""]).save()
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
        "tests.base.command.asyncChain1.AsyncChain1")
    self.assertEqual(self.adapterBufferModel.toCmd.classImportPath,
        "tests.base.command.asyncChain2.AsyncChain2")
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
        thirdpartyObj.cmd.paramForm.cleaned_data['stdIn'],
        u'asyncChain1')
