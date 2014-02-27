# -*- coding: utf-8 -*-
##### System wide lib #####
import os

##### Theory lib #####
from theory.model import Command
from theory.gui.util import LocalFileObject

##### Theory third-party lib #####

##### Local app #####
from .baseCommandTestCase import BaseCommandTestCase

##### Theory app #####

##### Misc #####

__all__ = ('IndentFormatFixTestCase',)

class IndentFormatFixTestCase(BaseCommandTestCase):
  def __init__(self, *args, **kwargs):
    super(IndentFormatFixTestCase, self).__init__(*args, **kwargs)
    self.cmdModel = Command.objects.get(name="indentFormatFix")
    self.thisTestCaseFilesAbsPath = os.path.join( \
        os.path.dirname(os.path.dirname(__file__)), \
        "testsFile",\
        "indentFormatFixTestCase",\
        "4space",
        )

  def _restoreFile(self, filename):
    originFilename = filename + ".orig"
    os.rename(originFilename, filename)

  def _compareFile(self, filename):
    correctFilename = filename + ".correct"
    newFileObj = open(filename, "rb")
    correctFileObj = open(correctFilename, "rb")
    self.assertEqual(newFileObj.read(), correctFileObj.read())
    newFileObj.close()
    correctFileObj.close()

  def testSimplePath(self):
    fileObj = LocalFileObject(self.thisTestCaseFilesAbsPath)
    cmd = self._getCmd(self.cmdModel, [[fileObj], 1, True])
    self._validateParamForm(cmd)
    self._execeuteCommand(cmd, self.cmdModel)
    self._compareFile(self.thisTestCaseFilesAbsPath)
    self._restoreFile(self.thisTestCaseFilesAbsPath)

    cmd = self._getCmd(
        self.cmdModel,
        kwargs={"filenameLst": [fileObj,], "writtenMode": 1}
        )
    self._validateParamForm(cmd)
    self._execeuteCommand(cmd, self.cmdModel)
    self._compareFile(self.thisTestCaseFilesAbsPath)
    self._restoreFile(self.thisTestCaseFilesAbsPath)

if __name__ == '__main__':
  unittest.main()
