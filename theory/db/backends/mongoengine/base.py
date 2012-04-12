# -*- coding: utf-8 -*-
##### System wide lib #####
import os
import sys
from mongoengine import connect

##### Theory lib #####
from theory.db.backends import *

##### Theory third-party lib #####

##### Local app #####

##### Theory app #####

##### Misc #####

class DatabaseCreation(BaseDatabaseCreation):
  def _createTestDb(self, verbosity, autoclobber):
    testDatabaseName = self._getTestDbName()
    self.connection.connection = connect(testDatabaseName, port=self.connection.settings_dict['PORT'])

  def _destroyTestDb(self, testDatabaseName, verbosity):
    if(verbosity>1):
      print "Dropping database %s" % (testDatabaseName)
    self.connection.connection.drop_database(testDatabaseName)

class DatabaseWrapper(BaseDatabaseWrapper):
  vendor = 'mongoengine'

  def __init__(self, *args, **kwargs):
    super(DatabaseWrapper, self).__init__(*args, **kwargs)
    self._mongoengineConnect()
    self.creation = DatabaseCreation(self)
    self.client = DatabaseClient(self)
    self.validation = BaseDatabaseValidation(self)

  def close(self):
    self.connection.disconnect()

  def _mongoengineConnect(self):
    if(self.connection is None):
      self.connection = connect(self.settings_dict["NAME"],
          port=int(self.settings_dict["PORT"]))


class DatabaseClient(BaseDatabaseClient):
  executable_name = 'mongo'
  def runshell(self):
    args = [self.executable_name, self.connection.settings_dict['NAME']]
    if os.name == 'nt':
      sys.exit(os.system(" ".join(args)))
    else:
      os.execvp(self.executable_name, args)
