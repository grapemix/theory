# -*- coding: utf-8 -*-
##### System wide lib #####
from mongoengine import connect
from mongoengine.connection import get_db, get_connection, ConnectionError
import pymongo

##### Theory lib #####
from theory.conf import settings
from theory.db.backends.mongoEngine.base import DatabaseCreation
from theory.model import Command
from theory.utils import unittest

##### Theory third-party lib #####

##### Local app #####

##### Theory app #####

##### Misc #####

__all__ = ('BackendsTestCase',)

class BackendsTestCase(unittest.TestCase):
  def setUp(self):
    pass

  def testCurrentConnectionExist(self):
    conn = get_connection()
    self.assertTrue(
        isinstance(conn, pymongo.mongo_client.MongoClient) or
        isinstance(conn, pymongo.connection.Connection)
    )

  def testCurrentConnectionHasTestDb(self):
    self.assertEqual(get_db().name, "test_theory")

  #def testCloseCurrentConnection(self):
  #  db = get_db()
  #  db.logout()
  #  db.connection.end_request()
  #  db.connection.disconnect()
  #  get_connection().close()
  #  #self.assertNotEqual(db.name, 'theory')

  def testDbExist(self):
    db = get_db()
    self.assertTrue(isinstance(db, pymongo.database.Database))

  def testDbIsTestDb(self):
    db = get_db()
    self.assertEqual(db.name, 'test_theory')

# This should be used for testing switch db in the future
#
#
#  def testTestDbExist(self):
#    self.assertRaises(ConnectionError, connect, 'test_theory', alias='testDb')
#
#
#    connect('test_theory', alias='testdb')
#    conn = get_connection('testdb')
#
#    db = get_db()
#    self.assertTrue(isinstance(db, pymongo.database.Database))
#    self.assertEqual(db.name, 'test_theory')
#
#    conn = get_connection()
#    dbCreator = DatabaseCreation(conn)
#    dbCreator._createTestDb(1, None)

  def testCollectionNameDuringQuery(self):
    self.assertEqual(Command._get_collection_name(), "theory_command")

  def testCollectionNameDuringCreation(self):
    cmd = Command(name="testCmd", app="testApp", mood="testMood")
    self.assertEqual(cmd._get_collection_name(), "theory_command")
