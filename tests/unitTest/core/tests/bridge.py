# -*- coding: utf-8 -*-
##### System wide lib #####
from ludibrio import Stub

##### Theory lib #####
from theory.command.baseCommand import SimpleCommand, AsyncCommand, AsyncContainer
from theory.core.bridge import Bridge
from theory.model import *
from theory.utils import unittest

##### Theory third-party lib #####

##### Local app #####

##### Theory app #####

##### Misc #####

__all__ = ('BridgeTestCase', 'SimpleChain1', \
    'SimpleChain2', 'AsyncChain1', \
    'AsyncChain2', 'AsyncCompositeChain1', )

class BaseChain1(object):
  params = []
  _gongs = ["StdPipe", ]

class SimpleChain1(BaseChain1, SimpleCommand):
  name = "simpleChain1"
  verboseName = "simpleChain1"

  def run(self, *args, **kwargs):
    self._stdOut = "simpleChain1"

class AsyncChain1(BaseChain1, AsyncCommand):
  name = "asyncChain1"
  verboseName = "asyncChain1"
  _stdOut = name
  def run(self, *args, **kwargs):
    self._stdOut = "asyncChain1"

class AsyncCompositeChain1(AsyncChain1):
  def _getMockCommandObject(self, cmd, classImportPath):
    with Stub(proxy=cmd) as cmd:
      cmd.classImportPath >> "%s.%s" % (self.__module__, classImportPath)
    return cmd

  def run(self, secondCmdModel, *args, **kwargs):
    super(AsyncCompositeChain1, self).__init__(*args, **kwargs)
    bridge = Bridge()
    secondCmdModel = self._getMockCommandObject(secondCmdModel, "SimpleChain2")
    (chain2Class, secondCmdStorage) = bridge.bridge(self, secondCmdModel)
    (secondCmd, secondCmdStorage) = \
        bridge.getCmdComplex(secondCmdModel, [], secondCmdStorage)
    return secondCmd.run()

class BaseChain2(object):
  params = []
  _notations = ["StdPipe", ]
  _stdIn = ""

  @property
  def stdIn(self):
    return self._stdIn

  @stdIn.setter
  def stdIn(self, stdIn):
    """
    :param stdIn: stdIn comment
    :type stdIn: stdIn type
    """
    self._stdIn = stdIn

class SimpleChain2(BaseChain2, SimpleCommand):
  name = "simpleChain2"
  verboseName = "simpleChain2"
  def run(self, *args, **kwargs):
    #print "????"
    return self.stdIn + " received"


class AsyncChain2(BaseChain2, AsyncCommand):
  name = "asyncChain2"
  verboseName = "asyncChain2"

  def run(self, *args, **kwargs):
    #print "???!"
    return self.stdIn + " received"

class BridgeTestCase(unittest.TestCase):
  """TODO: Add more test"""
  def setUp(self):
    self.bridge = Bridge()
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

  def testBridgeToDb(self):
    secondCmdModel = self.asyncChain2CommandModel
    secondCmdModel = self._getMockCommandObject(secondCmdModel, "AsyncChain2")

    firstCmd = AsyncChain1()
    firstCmd.run()

    data = self.bridge.bridgeToDb(firstCmd, secondCmdModel)

    self.assertEqual(data, '{"stdIn": "asyncChain1"}')
    self.adapterBufferModel.fromCmd = self.asyncChain1CommandModel
    self.adapterBufferModel.toCmd = self.asyncChain2CommandModel
    self.adapterBufferModel.data = data

  def testBridgeFromDb(self):
    self.adapterBufferModel.fromCmd = self.asyncChain1CommandModel
    secondCmdModel = self.asyncChain2CommandModel
    secondCmdModel = self._getMockCommandObject(secondCmdModel, "AsyncChain2")
    self.adapterBufferModel.toCmd = secondCmdModel
    self.adapterBufferModel.data = '{"stdIn": "asyncChain1"}'
    (tailClass, data) = self.bridge.bridgeFromDb(self.adapterBufferModel)
    self.assertTrue(isinstance(tailClass, AsyncChain2))
    self.assertEqual(data, {u'stdIn': u'asyncChain1'})
