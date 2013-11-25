# -*- coding: utf-8 -*-
##### System wide lib #####
import os

##### Theory lib #####

##### Theory third-party lib #####

##### Local app #####
from .base import *

##### Theory app #####

##### Misc #####

env = os.environ.get('EXE_ENV')
if env == 'dev':
    from .dev import *
else:
    env = 'localdev'
    try:
        from .localdev import *
    except ImportError:
        pass

EXE_ENV = env
