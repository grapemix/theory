# -*- coding: utf-8 -*-
##### System wide lib #####
import os
import unittest

##### Theory lib #####
from theory.command import fileSelector
from theory.conf import settings

##### Theory third-party lib #####

##### Local app #####

##### Theory app #####

##### Misc #####

__all__ = ('TestFileSelector',)

class TestFileSelector(unittest.TestCase):

  def setUp(self):
    self.selector = fileSelector.FileSelector()
    self.thisTestCaseFilesAbsPath = os.path.join(os.path.dirname(os.path.dirname(__file__)), "testsFile", "fileSelector")

  def testSimplePath(self):
    self.selector.roots = [self.thisTestCaseFilesAbsPath,]
    self.selector.run()
    self.assertIn('/opt/crystal/venv/panel/src/theory/tests/unitTest/command/testsFile/fileSelector/empty.py', self.selector._files)

    # should raise an exception for an immutable sequence
    #self.assertRaises(TypeError, random.shuffle, (1,2,3))

if __name__ == '__main__':
  unittest.main()
