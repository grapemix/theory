# -*- coding: utf-8 -*-
##### System wide lib #####
from ludibrio import Stub
import os
import sys

##### Theory lib #####
from theory.command.baseCommand import SimpleCommand, AsyncCommand, AsyncContainer
from theory.core.bridge import Bridge
from theory.utils import unittest
from theory.model import Adapter, Command, Parameter

##### Theory third-party lib #####

##### Local app #####

##### Theory app #####

##### Misc #####

__all__ = ('BridgeTestCase',)


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
  def setUp(self):
    self.bridge = Bridge()

    if(self.__module__ not in sys.path):
      sys.path.append(self.__module__)

    # should move to setup if test db bug is fixed
    self.simpleChain1CommandModel = Command(name="SimpleChain1", app="test", mood=["test",])
    self.simpleChain2CommandModel = Command(name="SimpleChain2", app="test", mood=["test",], param=[Parameter(name="stdIn",type="String")])

    self.asyncChain1CommandModel = Command(name="AsyncChain1", app="test", mood=["test",])
    self.asyncChain2CommandModel = Command(name="AsyncChain2", app="test", mood=["test",], param=[Parameter(name="stdIn",type="String")])

    #Adapter(name="StdPipe", importPath=u"theory.adapter.stdPipeAdapter.StdPipeAdapter", property=[u'stdErr', u'stdIn', u'stdOut']).save()

  def _getMockCommandObject(self, cmd, classImportPath):
    with Stub(proxy=cmd) as cmd:
      cmd.classImportPath >> "%s.%s" % (self.__module__, classImportPath)
    return cmd

  def testSimpleCommandToSimpleCommand(self):
    firstCmd = SimpleChain1()

    #(firstCmd, firstCmdStorage) = self.bridge.getCmdComplex(self.simpleChain1CommandModel, [], {})
    #firstCmd.run()
    firstCmd.run()

    secondCmdModel = self.simpleChain2CommandModel
    secondCmdModel = self._getMockCommandObject(secondCmdModel, "SimpleChain2")
    (chain2Class, secondCmdStorage) = self.bridge.bridge(firstCmd, secondCmdModel)
    #print chain2Class, secondCmdStorage
    (secondCmd, secondCmdStorage) = self.bridge.getCmdComplex(secondCmdModel, [], secondCmdStorage)
    #print secondCmd, secondCmdStorage, secondCmdStorage._stdIn, secondCmd._stdIn
    #cmd.delay(storage)
    #asyncContainer = AsyncContainer()
    #result = asyncContainer.run(cmd, [])
    result = secondCmd.run()
    #return result
    #cmd.run()

    self.assertEqual(secondCmd.run(), "simpleChain1 received")

  def testAsyncCommandToSimpleCommand(self):
    firstCmd = AsyncChain1()
    firstCmd.run()

    secondCmdModel = self.simpleChain2CommandModel
    secondCmdModel = self._getMockCommandObject(secondCmdModel, "SimpleChain2")
    (chain2Class, storage) = self.bridge.bridge(firstCmd, secondCmdModel)
    (secondCmd, secondCmdStorage) = self.bridge.getCmdComplex(secondCmdModel, [], storage)

    self.assertEqual(secondCmd.run(), "asyncChain1 received")

  def testSimpleCommandToAsyncCommand(self):
    firstCmd = SimpleChain1()
    firstCmd.run()

    secondCmdModel = self.asyncChain2CommandModel
    secondCmdModel = self._getMockCommandObject(secondCmdModel, "AsyncChain2")
    (chain2Class, storage) = self.bridge.bridge(firstCmd, secondCmdModel)
    (cmd, storage) = self.bridge.getCmdComplex(secondCmdModel, [], storage)
    self.assertEqual(cmd.run(), "simpleChain1 received")


  def testAsyncCommandToAsyncCommand(self):
    firstCmd = AsyncChain1()
    firstCmd.run()

    secondCmdModel = self.asyncChain2CommandModel
    secondCmdModel = self._getMockCommandObject(secondCmdModel, "AsyncChain2")
    (chain2Class, storage) = self.bridge.bridge(firstCmd, secondCmdModel)
    (cmd, storage) = self.bridge.getCmdComplex(secondCmdModel, [], storage)
    result = cmd.run()
    self.assertEqual(cmd.run(), "asyncChain1 received")
