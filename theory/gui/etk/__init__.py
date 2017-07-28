# -*- coding: utf-8 -*-
#!/usr/bin/env python
from efl.dbus_mainloop import DBusEcoreMainLoop

__all__ = ("getDbusMainLoop",)

def getDbusMainLoop():
  return DBusEcoreMainLoop()
