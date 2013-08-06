# -*- coding: utf-8 -*-
#!/usr/bin/env python
##### System wide lib #####
import os
import sys
from time import sleep
from mongoengine import connect
import mongoengine.connection
from mongoengine.connection import get_connection, disconnect, get_db

##### Theory lib #####
from theory.db.backends import *

##### Theory third-party lib #####

##### Local app #####

##### Theory app #####

##### Misc #####

class DatabaseCreation(BaseDatabaseCreation):
  def _createTestDb(self, verbosity, autoclobber):
    testDatabaseName = self._getTestDbName()
    self.connection = connect(db=testDatabaseName,
        port=int(self.settings_dict['PORT']),
        username=self.settings_dict['USER'],
        password=self.settings_dict['PASSWORD'],
        )
    if verbosity >= 1:
      testDbRepr = ''
      if verbosity >= 2:
        testDbRepr = " ('%s')" % testDatabaseName
      print "Creating test database for alias '%s'%s..." % (
          self.connection.alias, testDbRepr)
      print self.connection.database_names()
    self.settings_dict["ORIGINAL_NAME"] = \
        self.settings_dict["NAME"]

  def _destroyTestDb(self, testDatabaseName, verbosity):
    if(verbosity>1):
      print "Dropping database %s" % (testDatabaseName)
    self.connection.drop_database(testDatabaseName)
    self.settings_dict["NAME"] = \
        self.settings_dict["ORIGINAL_NAME"]

  def _closeConnection(self):
    mongoengine.connection.disconnect()
    mongoengine.connection._connection_settings = {}
    mongoengine.connection._connections = {}
    mongoengine.connection._dbs = {}

class DatabaseWrapper(BaseDatabaseWrapper):
  vendor = 'mongoengine'

  def __init__(self, *args, **kwargs):
    super(DatabaseWrapper, self).__init__(*args, **kwargs)
    self._mongoengineConnect()
    self.creation = DatabaseCreation(self.connection, self.settings_dict)
    self.client = DatabaseClient(self.connection, self.settings_dict)
    self.validation = BaseDatabaseValidation(
        self.connection,
        self.settings_dict
        )

  def close(self):
    mongoengine.connection.disconnect()
    mongoengine.connection._connection_settings = {}
    mongoengine.connection._connections = {}
    mongoengine.connection._dbs = {}


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
    args = [self.executable_name, self.settings_dict['NAME']]
    if os.name == 'nt':
      sys.exit(os.system(" ".join(args)))
    else:
      os.execvp(self.executable_name, args)
