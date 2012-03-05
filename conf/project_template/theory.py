# -*- coding: utf-8 -*-
#!/usr/bin/env python
from theory.core.loader import wakeup
import imp
try:
    imp.find_module('settings') # Assumed to be in the same directory.
except ImportError:
    import sys
    sys.stderr.write("Error: Can't find the file 'settings.py' in the directory containing %r. It appears you've customized things.\n" % __file__)
    sys.exit(1)

import settings

if __name__ == "__main__":
    wakeup(settings)
