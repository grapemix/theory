# -*- coding: utf-8 -*-
##### System wide lib #####
import os

##### Theory lib #####
from theory.model import Command

##### Theory third-party lib #####

##### Local app #####
from .baseCommandTestCase import BaseCommandTestCase

##### Theory app #####

##### Misc #####

__all__ = ('FilenameScannerTestCase',)

class FilenameScannerTestCase(BaseCommandTestCase):
  def __init__(self, *args, **kwargs):
    super(FilenameScannerTestCase, self).__init__(*args, **kwargs)
    self.cmdModel = Command.objects.get(name="filenameScanner")
    self.thisTestCaseFilesAbsPath = \
        os.path.dirname(__file__)

  def testSimplePath(self):
    cmd = self._getCmd(self.cmdModel, [[self.thisTestCaseFilesAbsPath,]])
    self._validateParamForm(cmd)
    self._execeuteCommand(cmd, self.cmdModel)
    self.assertIn(__file__, self.cmd.filenameLst)

    cmd = self._getCmd(self.cmdModel, kwargs={"rootLst": [self.thisTestCaseFilesAbsPath,]})
    self._validateParamForm(cmd)
    self._execeuteCommand(cmd, self.cmdModel)
    self.assertIn(__file__, self.cmd.filenameLst)

if __name__ == '__main__':
  unittest.main()
