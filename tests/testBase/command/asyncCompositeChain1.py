# -*- coding: utf-8 -*-
##### System wide lib #####
from ludibrio import Stub

##### Theory lib #####
from theory.command.baseCommand import AsyncCommand
from theory.core.bridge import Bridge
from theory.gui import field

##### Theory third-party lib #####

##### Local app #####
from .asyncChain1 import AsyncChain1
from .simpleChain2 import SimpleChain2

##### Theory app #####

##### Misc #####

class AsyncCompositeChain1(AsyncChain1):

  class ParamForm(AsyncCommand.ParamForm):
    queryset = field.QuerysetField()

  def run(self, *args, **kwargs):
    super(AsyncCompositeChain1, self).run(*args, **kwargs)
    secondCmdModel = self.paramForm.clean()["queryset"]
    bridge = Bridge()
    secondCmdModel = SimpleChain2.getCmdModel()
    (chain2Class, secondCmdStorage) = bridge.bridge(self, secondCmdModel)
    secondCmd = \
        bridge.getCmdComplex(secondCmdModel, [], secondCmdStorage)
    return secondCmd.run()
