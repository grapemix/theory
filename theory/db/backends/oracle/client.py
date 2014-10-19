import os
import sys

from theory.db.backends import BaseDatabaseClient


class DatabaseClient(BaseDatabaseClient):
  executableName = 'sqlplus'

  def runshell(self):
    connString = self.connection._connectString()
    args = [self.executableName, "-L", connString]
    if os.name == 'nt':
      sys.exit(os.system(" ".join(args)))
    else:
      os.execvp(self.executableName, args)
