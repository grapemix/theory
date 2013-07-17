# -*- coding: utf-8 -*-
#!/usr/bin/env python
##### System wide lib #####
import os
import sys
from mongoengine import connect
from mongoengine.connection import get_connection, disconnect

##### Theory lib #####
from theory.db.backends import *

##### Theory third-party lib #####

##### Local app #####

##### Theory app #####

##### Misc #####

class DatabaseCreation(BaseDatabaseCreation):
  def _createTestDb(self, verbosity, autoclobber):
    testDatabaseName = self._getTestDbName()
    connect(db=testDatabaseName,
        port=int(self.connection.settings_dict['PORT']),
        username=self.connection.settings_dict['USER'],
        password=self.connection.settings_dict['PASSWORD'],
        )
    self.connection.settings_dict["ORIGINAL_NAME"] = \
        self.connection.settings_dict["NAME"]

  def _destroyTestDb(self, testDatabaseName, verbosity):
    if(verbosity>1):
      print "Dropping database %s" % (testDatabaseName)
    connection = get_connection()
    connection.drop_database(testDatabaseName)
    self.connection.settings_dict["NAME"] = \
        self.connection.settings_dict["ORIGINAL_NAME"]

  def _closeConnection(self):
    disconnect()

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
          port=int(self.settings_dict["PORT"]),
          username=self.settings_dict['USER'],
          password=self.settings_dict['PASSWORD'],
          )

class DatabaseClient(BaseDatabaseClient):
  executable_name = 'mongo'
  def runshell(self):
    args = [self.executable_name, self.connection.settings_dict['NAME']]
    if os.name == 'nt':
      sys.exit(os.system(" ".join(args)))
    else:
      os.execvp(self.executable_name, args)
