# -*- coding: utf-8 -*-
##### System wide lib #####
from ludibrio import Stub
import os
import sys

##### Theory lib #####
from theory.utils import unittest
#from theory.db.models import QuerySet
from theory.model import *

##### Theory third-party lib #####

##### Local app #####

##### Theory app #####

##### Misc #####
from tests.testBase.command import *
from tests.testBase.bridge import Bridge

__all__ = ('BridgeTestCase',)

class BridgeTestCase(unittest.TestCase):
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

    self.assertTrue(firstCmd.paramForm.is_valid())
    self.bridge._execeuteCommand(firstCmd, firstCmd.getCmdModel())

    secondCmdModel = self.simpleChain2CommandModel
    secondCmdModel = self._getMockCommandObject(secondCmdModel, "SimpleChain2")
    (chain2Class, secondCmdStorage) = self.bridge.bridge(firstCmd, secondCmdModel)
    secondCmd = self.bridge.getCmdComplex(secondCmdModel, [], secondCmdStorage)
    self.bridge._execeuteCommand(secondCmd, secondCmdModel)

    self.assertEqual(secondCmd._stdOut, "simpleChain1 received")
    self.assertTrue(secondCmd.paramForm.is_valid())
    self.assertEqual(secondCmd.paramForm.clean()["stdIn"], 'simpleChain1')

  def testAsyncCommandToSimpleCommand(self):
    firstCmd = AsyncChain1()
    firstCmd.paramForm = firstCmd.ParamForm()
    self.bridge._execeuteCommand(firstCmd, firstCmd.getCmdModel())

    secondCmdModel = self.simpleChain2CommandModel
    secondCmdModel = self._getMockCommandObject(secondCmdModel, "SimpleChain2")
    (chain2Class, storage) = self.bridge.bridge(firstCmd, secondCmdModel)
    secondCmd = self.bridge.getCmdComplex(secondCmdModel, [], storage)

    self.bridge._execeuteCommand(secondCmd, secondCmdModel)
    self.assertEqual(secondCmd._stdOut, "asyncChain1 received")

  def testSimpleCommandToAsyncCommand(self):
    firstCmd = SimpleChain1()
    firstCmd.paramForm = firstCmd.ParamForm()
    self.bridge._execeuteCommand(firstCmd, firstCmd.getCmdModel())

    secondCmdModel = self.asyncChain2CommandModel
    secondCmdModel = self._getMockCommandObject(secondCmdModel, "AsyncChain2")
    (chain2Class, storage) = self.bridge.bridge(firstCmd, secondCmdModel)
    cmd = self.bridge.getCmdComplex(secondCmdModel, [], storage)
    self.bridge._execeuteCommand(cmd, secondCmdModel)
    self.assertEqual(cmd._stdOut, "simpleChain1 received")

  def testAsyncCommandToAsyncCommand(self):
    firstCmd = AsyncChain1()
    firstCmd.paramForm = firstCmd.ParamForm()
    self.bridge._execeuteCommand(firstCmd, firstCmd.getCmdModel())

    secondCmdModel = self.asyncChain2CommandModel
    secondCmdModel = self._getMockCommandObject(secondCmdModel, "AsyncChain2")
    (chain2Class, storage) = self.bridge.bridge(firstCmd, secondCmdModel)
    cmd = self.bridge.getCmdComplex(secondCmdModel, [], storage)
    self.bridge._execeuteCommand(cmd, secondCmdModel)
    self.assertEqual(cmd._stdOut, "asyncChain1 received")

  def testAsyncCompositeCommandToAsyncCommand(self):
    firstCmd = AsyncCompositeChain1()
    firstCmd.paramForm = firstCmd.ParamForm()

    secondCmdModel = self.asyncChain2CommandModel
    secondCmdModel.save()

    mockLst = [secondCmdModel]
    with Stub(type=QuerySet, proxy=mockLst) as queryset:
      pass

    firstCmd.paramForm.fields["queryset"].finalData = queryset
    self.bridge._execeuteCommand(firstCmd, firstCmd.getCmdModel())

  def testSimpleCommandToSelf(self):
    firstCmd = SimpleChain1()
    firstCmd.paramForm = firstCmd.ParamForm()
    firstCmd.run()
    self.bridge.bridgeToSelf(firstCmd)
