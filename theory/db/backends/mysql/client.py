import os
import sys

from theory.db.backends import BaseDatabaseClient


class DatabaseClient(BaseDatabaseClient):
  executableName = 'mysql'

  def runshell(self):
    settingsDict = self.connection.settingsDict
    args = [self.executableName]
    db = settingsDict['OPTIONS'].get('db', settingsDict['NAME'])
    user = settingsDict['OPTIONS'].get('user', settingsDict['USER'])
    passwd = settingsDict['OPTIONS'].get('passwd', settingsDict['PASSWORD'])
    host = settingsDict['OPTIONS'].get('host', settingsDict['HOST'])
    port = settingsDict['OPTIONS'].get('port', settingsDict['PORT'])
    defaultsFile = settingsDict['OPTIONS'].get('readDefaultFile')
    # Seems to be no good way to set sqlMode with CLI.

    if defaultsFile:
      args += ["--defaults-file=%s" % defaultsFile]
    if user:
      args += ["--user=%s" % user]
    if passwd:
      args += ["--password=%s" % passwd]
    if host:
      if '/' in host:
        args += ["--socket=%s" % host]
      else:
        args += ["--host=%s" % host]
    if port:
      args += ["--port=%s" % port]
    if db:
      args += [db]

    if os.name == 'nt':
      sys.exit(os.system(" ".join(args)))
    else:
      os.execvp(self.executableName, args)
