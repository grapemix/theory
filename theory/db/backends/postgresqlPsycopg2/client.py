import os
import sys

from theory.db.backends import BaseDatabaseClient


class DatabaseClient(BaseDatabaseClient):
  executableName = 'psql'

  def runshell(self):
    settingsDict = self.connection.settingsDict
    args = [self.executableName]
    if settingsDict['USER']:
      args += ["-U", settingsDict['USER']]
    if settingsDict['HOST']:
      args.extend(["-h", settingsDict['HOST']])
    if settingsDict['PORT']:
      args.extend(["-p", str(settingsDict['PORT'])])
    args += [settingsDict['NAME']]
    if os.name == 'nt':
      sys.exit(os.system(" ".join(args)))
    else:
      os.execvp(self.executableName, args)
