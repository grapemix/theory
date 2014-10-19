# -*- coding: utf-8 -*-
##### System wide lib #####
from elementary import Window, ELM_WIN_BASIC

##### Theory lib #####
from theory.gui.etk.element import Box

##### Theory third-party lib #####

##### Local app #####

##### Theory app #####

##### Misc #####

__all__ = ('getDummyEnv',)

def getDummyEnv():
  dummyWin = Window("theory", ELM_WIN_BASIC)

  # Copied from gui.etk.widget._createContainer
  dummyBx = Box()
  dummyBx.win = dummyWin
  dummyBx.generate()
  return (dummyWin, dummyBx)

