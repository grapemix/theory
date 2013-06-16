# -*- coding: utf-8 -*-
##### System wide lib #####
from ludibrio import Stub

##### Theory lib #####
from theory.core.bridge import Bridge

##### Theory third-party lib #####

##### Local app #####
from .asyncChain1 import AsyncChain1
from .simpleChain2 import SimpleChain2

##### Theory app #####

##### Misc #####

class AsyncCompositeChain1(AsyncChain1):

  def run(self, secondCmdModel, *args, **kwargs):
    super(AsyncCompositeChain1, self).__init__(*args, **kwargs)
    bridge = Bridge()
    secondCmdModel = SimpleChain2.getCmdModel()
    (chain2Class, secondCmdStorage) = bridge.bridge(self, secondCmdModel)
    secondCmd = \
        bridge.getCmdComplex(secondCmdModel, [], secondCmdStorage)
    return secondCmd.run()
