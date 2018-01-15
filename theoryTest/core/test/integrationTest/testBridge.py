# -*- coding: utf-8 -*-
##### System wide lib #####
from ludibrio import Stub
import os
import sys

##### Theory lib #####
from theory.apps.model import AdapterBuffer
from theory.db.model.query import QuerySet
from theory.test.testcases import TestCase

##### Theory third-party lib #####

##### Local app #####

##### Theory app #####

##### Misc #####
from testBase.command import *
from testBase.bridge import Bridge

__all__ = ('TestBridgeTestCase',)

class TestBridgeTestCase(TestCase):
  fixtures = ["adapter",]
  def setUp(self):
    self.bridge = Bridge()

    if(self.__module__ not in sys.path):
      sys.path.append(self.__module__)

    # TODO: should move to setup if test db bug is fixed
    self.simpleChain1CommandModel = SimpleChain1.getCmdModel()
    self.simpleChain2CommandModel = SimpleChain2.getCmdModel()
    self.asyncChain1CommandModel = AsyncChain1.getCmdModel()
    self.asyncChain2CommandModel = AsyncChain2.getCmdModel()

    self.adapterBufferModel = AdapterBuffer()

  def _getMockCommandObject(self, cmd, classImportPath):
    with Stub(proxy=cmd) as cmd:
      cmd.classImportPath >> "%s.%s" % (self.__module__, classImportPath)
    return cmd

  def testSimpleCommandToSimpleCommand(self):
    firstCmd = SimpleChain1()
    firstCmd.paramForm = firstCmd.ParamForm()

    self.assertTrue(firstCmd.paramForm.isValid())
    self.bridge._executeCommand(firstCmd, firstCmd.getCmdModel())

    secondCmdModel = self.simpleChain2CommandModel
    secondCmdModel = self._getMockCommandObject(secondCmdModel, "SimpleChain2")
    (chain2Class, secondCmdStorage) = self.bridge.bridge(firstCmd, secondCmdModel)
    secondCmd = self.bridge.getCmdComplex(secondCmdModel, [], secondCmdStorage)
    self.bridge._executeCommand(secondCmd, secondCmdModel)

    self.assertEqual(secondCmd._stdOut, "simpleChain1 received")
    self.assertTrue(secondCmd.paramForm.isValid())
    self.assertEqual(secondCmd.paramForm.clean()["stdIn"], 'simpleChain1')

  def testAsyncCommandToSimpleCommand(self):
    firstCmd = AsyncChain1()
    firstCmd.paramForm = firstCmd.ParamForm()
    self.bridge._executeCommand(firstCmd, firstCmd.getCmdModel())

    secondCmdModel = self.simpleChain2CommandModel
    secondCmdModel = self._getMockCommandObject(secondCmdModel, "SimpleChain2")
    (chain2Class, storage) = self.bridge.bridge(firstCmd, secondCmdModel)
    secondCmd = self.bridge.getCmdComplex(secondCmdModel, [], storage)

    self.bridge._executeCommand(secondCmd, secondCmdModel)
    self.assertEqual(secondCmd._stdOut, "asyncChain1 received")

  def testSimpleCommandToAsyncCommand(self):
    firstCmd = SimpleChain1()
    firstCmd.paramForm = firstCmd.ParamForm()
    self.bridge._executeCommand(firstCmd, firstCmd.getCmdModel())

    secondCmdModel = self.asyncChain2CommandModel
    secondCmdModel = self._getMockCommandObject(secondCmdModel, "AsyncChain2")
    (chain2Class, storage) = self.bridge.bridge(firstCmd, secondCmdModel)
    cmd = self.bridge.getCmdComplex(secondCmdModel, [], storage)
    self.bridge._executeCommand(cmd, secondCmdModel)
    self.assertEqual(cmd._stdOut, "simpleChain1 received")

  def testAsyncCommandToAsyncCommand(self):
    firstCmd = AsyncChain1()
    firstCmd.paramForm = firstCmd.ParamForm()
    self.bridge._executeCommand(firstCmd, firstCmd.getCmdModel())

    secondCmdModel = self.asyncChain2CommandModel
    secondCmdModel = self._getMockCommandObject(secondCmdModel, "AsyncChain2")
    (chain2Class, storage) = self.bridge.bridge(firstCmd, secondCmdModel)
    cmd = self.bridge.getCmdComplex(secondCmdModel, [], storage)
    self.bridge._executeCommand(cmd, secondCmdModel)
    self.assertEqual(cmd._stdOut, "asyncChain1 received")

  def testAsyncCompositeCommandToAsyncCommand(self):
    firstCmd = AsyncCompositeChain1()
    firstCmd.paramForm = firstCmd.ParamForm()

    secondCmdModel = self.asyncChain2CommandModel
    secondCmdModel.save()

    queryset = secondCmdModel.__class__.objects.filter(id=secondCmdModel.id)

    firstCmd.paramForm.fields["queryset"].finalData = queryset

    self.bridge._executeCommand(firstCmd, firstCmd.getCmdModel())

  def testSimpleCommandToSelf(self):
    firstCmd = SimpleChain1()
    firstCmd.paramForm = firstCmd.ParamForm()
    firstCmd.run()
    self.bridge.bridgeToSelf(firstCmd)
