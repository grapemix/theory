# -*- coding: utf-8 -*-
##### System wide lib #####
import json

##### Theory lib #####
from theory.apps.model import Command, AdapterBuffer
from theory.core.bridge import Bridge

##### Theory third-party lib #####

##### Local app #####
from .baseCommandTestCase import BaseCommandTestCase

##### Theory app #####

##### Misc #####
from tests.testBase.command import *

__all__ = ('NextStepTestCase',)

class NextStepTestCase(BaseCommandTestCase):
  def __init__(self, *args, **kwargs):
    super(NextStepTestCase, self).__init__(*args, **kwargs)
    self.cmdModel = Command.objects.get(name="nextStep")

  def _getMockBridge(self, bridge, cmd):
    bridge.bridgeFromDb = lambda adapterBufferModel: cmd
    return bridge

  def _createAdapterBuffer(self):
    bridge = Bridge()
    AdapterBuffer.objects.all().delete()
    Command.objects.all().delete()

    firstCmdModel = AsyncChain1.getCmdModel()
    firstCmdModel.save()
    secondCmdModel = SimpleChain2.getCmdModel()
    secondCmdModel.save()
    firstCmd = bridge.getCmdComplex(firstCmdModel, [], {})
    firstCmd.run()

    storage = bridge.bridgeToDb(firstCmd, secondCmdModel)
    realFirstCmdModel = Command.objects.get(name="AsyncChain1")
    realSecondCmdModel = Command.objects.get(name="SimpleChain2")
    abm = AdapterBuffer(fromCmd=realFirstCmdModel, toCmd=realSecondCmdModel, data=storage)
    abm.save()

    secondCmd = bridge.getCmdComplex(secondCmdModel, [], json.loads(storage))
    self.bridge = self._getMockBridge(Bridge(), secondCmd)

  def setUp(self, *args, **kwargs):
    self._createAdapterBuffer()
    super(NextStepTestCase, self).setUp(*args, **kwargs)

  def stopTestRunByArgs(self):
    cmd = self._getCmd(self.cmdModel, [AdapterBuffer.objects.all()[0].id,])
    self._validateParamForm(cmd)
    cmd.bridge = self.bridge
    self._execeuteCommand(cmd, self.cmdModel)
    self.assertTrue(AdapterBuffer.objects.count(), 0)
    # Note: We cannot test the output of the command being executed
    # because the nextStep command have not supported to pipe up
    # command being executed, in that way, we cannot get the output
    # of the command being executed and tested the result
    #self.assertEqual(cmd.run(), "simpleChain1 received")

  def stopTestRunByKwargs(self):
    cmd = self._getCmd(self.cmdModel, kwargs={"commandReady": AdapterBuffer.objects.all()[0].id})
    self._validateParamForm(cmd)
    cmd.bridge = self.bridge
    self._execeuteCommand(cmd, self.cmdModel)
    self.assertTrue(AdapterBuffer.objects.count(), 0)

if __name__ == '__main__':
  unittest.main()
