# -*- coding: utf-8 -*-
##### System wide lib #####
from ludibrio import Stub
import os
import sys

##### Theory lib #####
from theory.command.baseCommand import SimpleCommand, AsyncCommand, AsyncContainer
from theory.core.bridge import Bridge
from theory.utils import unittest
from theory.model import *

##### Theory third-party lib #####

##### Local app #####

##### Theory app #####

##### Misc #####
from tests.base.command import *

__all__ = ('BridgeTestCase',)

class BridgeTestCase(unittest.TestCase):
  def setUp(self):
    self.bridge = Bridge()

    if(self.__module__ not in sys.path):
      sys.path.append(self.__module__)

    # TODO: should move to setup if test db bug is fixed
    self.simpleChain1CommandModel = \
        Command(name="SimpleChain1", app="test", mood=["test",])
    self.simpleChain2CommandModel = \
        Command(name="SimpleChain2", app="test", mood=["test",], \
        param=[Parameter(name="stdIn",type="String")])

    self.asyncChain1CommandModel = \
        Command(name="AsyncChain1", app="test", mood=["test",])
    self.asyncChain2CommandModel = \
        Command(name="AsyncChain2", app="test", mood=["test",], \
        param=[Parameter(name="stdIn",type="String")])

    self.adapterBufferModel = AdapterBuffer()

  def _getMockCommandObject(self, cmd, classImportPath):
    with Stub(proxy=cmd) as cmd:
      cmd.classImportPath >> "%s.%s" % (self.__module__, classImportPath)
    return cmd

  def testSimpleCommandToSimpleCommand(self):
    firstCmd = SimpleChain1()
    firstCmd.paramForm = firstCmd.ParamForm()

    self.assertTrue(firstCmd.paramForm.is_valid())
    firstCmd.run()

    secondCmdModel = self.simpleChain2CommandModel
    secondCmdModel = self._getMockCommandObject(secondCmdModel, "SimpleChain2")
    (chain2Class, secondCmdStorage) = self.bridge.bridge(firstCmd, secondCmdModel)
    secondCmd = self.bridge.getCmdComplex(secondCmdModel, [], secondCmdStorage)
    result = secondCmd.run()

    self.assertEqual(secondCmd.run(), "simpleChain1 received")
    self.assertTrue(secondCmd.paramForm.is_valid())
    self.assertEqual(secondCmd.paramForm.clean()["stdIn"], 'simpleChain1')

  def testAsyncCommandToSimpleCommand(self):
    firstCmd = AsyncChain1()
    firstCmd.paramForm = firstCmd.ParamForm()
    firstCmd.run()

    secondCmdModel = self.simpleChain2CommandModel
    secondCmdModel = self._getMockCommandObject(secondCmdModel, "SimpleChain2")
    (chain2Class, storage) = self.bridge.bridge(firstCmd, secondCmdModel)
    secondCmd = self.bridge.getCmdComplex(secondCmdModel, [], storage)

    self.assertEqual(secondCmd.run(), "asyncChain1 received")

  def testSimpleCommandToAsyncCommand(self):
    firstCmd = SimpleChain1()
    firstCmd.paramForm = firstCmd.ParamForm()
    firstCmd.run()

    secondCmdModel = self.asyncChain2CommandModel
    secondCmdModel = self._getMockCommandObject(secondCmdModel, "AsyncChain2")
    (chain2Class, storage) = self.bridge.bridge(firstCmd, secondCmdModel)
    cmd = self.bridge.getCmdComplex(secondCmdModel, [], storage)
    self.assertEqual(cmd.run(), "simpleChain1 received")


  def testAsyncCommandToAsyncCommand(self):
    firstCmd = AsyncChain1()
    firstCmd.paramForm = firstCmd.ParamForm()
    firstCmd.run()

    secondCmdModel = self.asyncChain2CommandModel
    secondCmdModel = self._getMockCommandObject(secondCmdModel, "AsyncChain2")
    (chain2Class, storage) = self.bridge.bridge(firstCmd, secondCmdModel)
    cmd = self.bridge.getCmdComplex(secondCmdModel, [], storage)
    result = cmd.run()
    self.assertEqual(cmd.run(), "asyncChain1 received")


  def testAsyncCompositeCommandToAsyncCommand(self):
    firstCmd = AsyncCompositeChain1()
    firstCmd.paramForm = firstCmd.ParamForm()
    secondCmdModel = self.simpleChain2CommandModel
    self.assertEqual(firstCmd.run(secondCmdModel), "asyncChain1 received")

  def testSimpleCommandToSelf(self):
    firstCmd = SimpleChain1()
    firstCmd.paramForm = firstCmd.ParamForm()
    firstCmd.run()
    self.bridge.bridgeToSelf(firstCmd)
