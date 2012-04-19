# -*- coding: utf-8 -*-
#!/usr/bin/env python
"""Main entry point"""

import sys
if sys.argv[0].endswith("__main__.py"):
  sys.argv[0] = "unittest2"

__unittest = True

from theory.utils.unittest.main import main_
main_()
