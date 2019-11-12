# -*- coding: utf-8 -*-
##### System wide lib #####

##### Theory lib #####
from theory.test.testcases import TestCase
from theory.test.util import tag

##### Theory third-party lib #####

##### Local app #####

##### Theory app #####

##### Misc #####
from testBase.command.geventCmd import GeventCmd

__all__ = ('TestGeventCmdTestCase',)

class TestGeventCmdTestCase(TestCase):
  @tag('gevent')
  def testGeventCmd(self):
    cmd = GeventCmd()
    cmd.paramForm = cmd.ParamForm()

    self.assertTrue(cmd.paramForm.isValid())
    r = cmd.run()
    self.assertTrue(isinstance(r, (bytes, bytearray)))
