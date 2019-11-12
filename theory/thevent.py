# -*- coding: utf-8 -*-
#!/usr/bin/env python
##### Patch #####
import gevent
from gevent import monkey; monkey.patch_all()
import grpc.experimental.gevent as grpc_gevent
grpc_gevent.init_gevent()

##### System wide lib #####

##### Theory lib #####

##### Theory third-party lib #####

##### Local app #####

##### Theory app #####

##### Misc #####
# WARNING: ONLY USE gevent from here. DON'T IMPORT YOURSELF
__all__ = ("gevent",)

