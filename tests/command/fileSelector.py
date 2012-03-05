# -*- coding: utf-8 -*-
##### System wide lib #####
import unittest

##### Theory lib #####
from theory.command import fileSelector
from theory.conf import settings

##### Theory third-party lib #####

##### Local app #####

##### Theory app #####

##### Misc #####

class TestFileSelector(unittest.TestCase):

  def setUp(self):
    self.selector = fileSelector.FileSelector()

  def testSimplePath(self):
    self.selector.roots = ["./",]
    print self.selector.run()
    print self.selector._files

    # should raise an exception for an immutable sequence
    #self.assertRaises(TypeError, random.shuffle, (1,2,3))

if __name__ == '__main__':
  unittest.main()
