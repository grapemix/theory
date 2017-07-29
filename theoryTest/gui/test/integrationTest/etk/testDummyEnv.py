# -*- coding: utf-8 -*-
##### System wide lib #####
from efl.elementary.window import StandardWindow

##### Theory lib #####
from theory.gui.etk.element import Box

##### Theory third-party lib #####

##### Local app #####

##### Theory app #####

##### Misc #####

__all__ = ('getDummyEnv',)

def getDummyEnv():
  dummyWin = StandardWindow("theory", "Theory", autodel=True)

  # Copied from gui.etk.widget._createContainer
  dummyBx = Box()
  dummyBx.win = dummyWin
  dummyBx.generate()
  return (dummyWin, dummyBx)

