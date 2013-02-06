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

__all__ = ('BridgeTestCase', 'SimpleChain1', \
    'SimpleChain2', 'AsyncChain1', \
    'AsyncChain2', 'AsyncCompositeChain1', )

class BaseChain(object):
  name = ""

  @classmethod
  def getCmdModel(self):
    className = self.name[0].upper() + self.name[1:]
    cmdModel = Command(name=className, app="test", mood=["test",])
    with Stub(proxy=cmdModel) as cmdModel:
      cmdModel.classImportPath >> "tests.unitTest.core.tests.%s" % className
    return cmdModel

class BaseChain1(BaseChain):
  _gongs = ["StdPipe", ]

  class ParamForm(SimpleCommand.ParamForm):
    customField = field.TextField(required=False)

class SimpleChain1(BaseChain1, SimpleCommand):
  name = "simpleChain1"
  verboseName = "simpleChain1"

  def run(self):
    self._stdOut = "simpleChain1"

class AsyncChain1(BaseChain1, AsyncCommand):
  name = "asyncChain1"
  verboseName = "asyncChain1"
  _stdOut = name

  def run(self):
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
    secondCmd = \
        bridge.getCmdComplex(secondCmdModel, [], secondCmdStorage)
    return secondCmd.run()

class BaseChain2(BaseChain):
  _notations = ["StdPipe", ]
  _stdIn = ""
  _propertyForTesting = ""

  class ParamForm(SimpleCommand.ParamForm):
    customField = field.TextField(required=False)
    stdIn = field.TextField()

  @classmethod
  def getCmdModel(self):
    cmdModel = super(BaseChain2, self).getCmdModel()
    cmdModel.param = [Parameter(name="stdIn",type="String")]
    return cmdModel

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

  @property
  def propertyForTesting(self):
    return self._propertyForTesting

  @propertyForTesting.setter
  def propertyForTesting(self, propertyForTesting):
    self._propertyForTesting = propertyForTesting

  def run(self):
    self.propertyForTesting = "propertyForTesting generated"
    return self.paramForm.clean()["stdIn"] + " received"

class SimpleChain2(BaseChain2, SimpleCommand):
  name = "simpleChain2"
  verboseName = "simpleChain2"

class AsyncChain2(BaseChain2, AsyncCommand):
  name = "asyncChain2"
  verboseName = "asyncChain2"

class BridgeTestCase(unittest.TestCase):
  def setUp(self):
    self.bridge = Bridge()
    self.asyncChain1CommandModel = AsyncChain1.getCmdModel()
    self.asyncChain2CommandModel = AsyncChain2.getCmdModel()
    self.adapterBufferModel = AdapterBuffer()

  def _getMockCommandObject(self, cmd, classImportPath):
    with Stub(proxy=cmd) as cmd:
      cmd.classImportPath >> "%s.%s" % (self.__module__, classImportPath)
    return cmd

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
    secondCmdModel = self._getMockCommandObject(secondCmdModel, "AsyncChain2")

    firstCmd = AsyncChain1()
    firstCmd.paramForm = firstCmd.ParamForm()
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
    tailInst = self.bridge.bridgeFromDb(self.adapterBufferModel)
    self.assertTrue(isinstance(tailInst, AsyncChain2))
    self.assertEqual(tailInst.paramForm.fields['stdIn'].finalData, u'asyncChain1')
    self.assertEqual(tailInst.paramForm.fields['stdIn'].finalData, u'asyncChain1')
    self.assertEqual(tailInst.paramForm.cleaned_data['stdIn'], u'asyncChain1')
