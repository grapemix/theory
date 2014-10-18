import os
import sys

from theory.db.backends import BaseDatabaseClient


class DatabaseClient(BaseDatabaseClient):
  executableName = 'sqlite3'

  def runshell(self):
    args = [self.executableName,
        self.connection.settingsDict['NAME']]
    if os.name == 'nt':
      sys.exit(os.system(" ".join(args)))
    else:
      os.execvp(self.executableName, args)
