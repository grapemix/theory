# -*- coding: utf-8 -*-
#!/usr/bin/env python
import os
import sys
from theory.utils.unittest.loader import defaultTestLoader

def collector():
  # import __main__ triggers code re-execution
  __main__ = sys.modules['__main__']
  setupDir = os.path.abspath(os.path.dirname(__main__.__file__))
  return defaultTestLoader.discover(setupDir)
