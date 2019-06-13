# -*- coding: utf-8 -*-
#!/usr/bin/env python
from __future__ import unicode_literals
##### System wide lib #####
try:
  from cStringIO import StringIO
except:
  from io import StringIO
import glob
import gzip
import os
import warnings
import zipfile

##### Theory lib #####
from theory.apps.command.baseCommand import SimpleCommand
from theory.conf import settings
from theory.gui import field

from theory.apps import apps
from theory.core import serializers
from theory.core.bridge import Bridge
from theory.core.exceptions import CommandError
from theory.gui.color import noStyle
from theory.db import (connections, router, transaction, DEFAULT_DB_ALIAS,
   IntegrityError, DatabaseError)
from theory.utils import lruCache
from theory.utils.encoding import forceText
from theory.utils.functional import cachedProperty
from theory.utils._os import upath
from itertools import product

try:
  import bz2
  hasBz2 = True
except ImportError:
  hasBz2 = False


##### Theory third-party lib #####

##### Local app #####

##### Theory app #####

##### Misc #####

class Loaddata(SimpleCommand):
  """
  Installs the named fixture(s) in the database.
  """
  name = "loaddata"
  verboseName = "loaddata"
  _notations = ["Command",]
  _drums = {"Terminal": 1, }

  missingArgsMessage = ("No database fixture specified. Please provide the "
              "path of at least one fixture in the command line.")

  class ParamForm(SimpleCommand.ParamForm):
    fixtureLabelLst = field.ListField(
        field.TextField(maxLen=256),
        label="Fixture Label",
        helpText="Fixture labels",
        )
    database = field.TextField(
        label="database",
        helpText=(
          'Nominates a specific database to load fixture into.',
          'Defaults to the "default" database.'
          ),
        initData=DEFAULT_DB_ALIAS,
        )
    appLabel = field.TextField(
        label="Application Label",
        helpText=" The name of application being loaded",
        maxLen=32
        )
    isIgnorenonexistent = field.BooleanField(
        label="is ignore non existent",
        helpText=(
          'Ignores entries in the serialized data for fields that do not ',
          'currently exist on the model.'
          ),
        required=False,
        initData=False,
        )
    isHideEmpty = field.BooleanField(
        label="is hiding empty",
        helpText="is hiding empty",
        required=False,
        initData=False,
        )


  def run(self):
    options = self.paramForm.clean()
    self.stdout = StringIO()

    self.ignore = options.get('ignore')
    self.using = options.get('database')
    self.appLabel = options.get('appLabel')
    self.hideEmpty = options.get('isHideEmpty')
    self.verbosity = options.get('verbosity')
    fixtureLabelLst = options.get("fixtureLabelLst")

    with transaction.atomic(using=self.using):
      self.loaddata(fixtureLabelLst)

    # Close the DB connection -- unless we're still in a transaction. This
    # is required as a workaround for an  edge case in MySQL: if the same
    # connection is used to create tables, load data, and query, the query
    # can return incorrect results. See Theory #7572, MySQL #37735.
    if transaction.getAutocommit(self.using):
      connections[self.using].close()

    self._stdOut = self.stdout.getvalue()
    self.stdout.close()

  def loaddata(self, fixtureLabels):
    connection = connections[self.using]

    # Keep a count of the installed objects and fixture
    self.fixtureCount = 0
    self.loadedObjectCount = 0
    self.fixtureObjectCount = 0
    self.models = set()

    self.serializationFormats = serializers.getPublicSerializerFormats()
    # Forcing binary mode may be revisited after dropping Python 2 support (see #22399)
    self.compressionFormats = {
      None: (open, 'rb'),
      'gz': (gzip.GzipFile, 'rb'),
      'zip': (SingleZipReader, 'r'),
    }
    if hasBz2:
      self.compressionFormats['bz2'] = (bz2.BZ2File, 'r')

    with connection.constraintChecksDisabled():
      for fixtureLabel in fixtureLabels:
        self.loadLabel(fixtureLabel)

    # Since we disabled constraint checks, we must manually check for
    # any invalid keys that might have been added
    tableNames = [model._meta.dbTable for model in self.models]
    try:
      connection.checkConstraints(tableNames=tableNames)
    except Exception as e:
      e.args = ("Problem installing fixture: %s" % e,)
      raise

    # If we found even one object in a fixture, we need to reset the
    # database sequences.
    if self.loadedObjectCount > 0:
      sequenceSql = connection.ops.sequenceResetSql(noStyle(), self.models)
      if sequenceSql:
        if self.verbosity >= 2:
          self.stdout.write("Resetting sequences\n")
        with connection.cursor() as cursor:
          for line in sequenceSql:
            cursor.execute(line)

    if self.verbosity >= 1:
      if self.fixtureCount == 0 and self.hideEmpty:
        pass
      elif self.fixtureObjectCount == self.loadedObjectCount:
        self.stdout.write("Installed %d object(s) from %d fixture(s)" %
          (self.loadedObjectCount, self.fixtureCount))
      else:
        self.stdout.write("Installed %d object(s) (of %d) from %d fixture(s)" %
          (self.loadedObjectCount, self.fixtureObjectCount, self.fixtureCount))

  def loadLabel(self, fixtureLabel):
    """
    Loads fixture files for a given label.
    """
    for fixtureFile, fixtureDir, fixtureName in self.findFixtures(fixtureLabel):
      _, serFmt, cmpFmt = self.parseName(os.path.basename(fixtureFile))
      openMethod, mode = self.compressionFormats[cmpFmt]
      fixture = openMethod(fixtureFile, mode)
      try:
        self.fixtureCount += 1
        objectsInFixture = 0
        loadedObjectsInFixture = 0
        if self.verbosity >= 2:
          self.stdout.write("Installing %s fixture '%s' from %s." %
            (serFmt, fixtureName, humanize(fixtureDir)))

        objects = serializers.deserialize(serFmt, fixture,
          using=self.using, ignorenonexistent=self.ignore)

        for obj in objects:
          objectsInFixture += 1
          if router.allowMigrate(self.using, obj.object.__class__):
            loadedObjectsInFixture += 1
            self.models.add(obj.object.__class__)
            try:
              obj.save(using=self.using)
            except (DatabaseError, IntegrityError) as e:
              e.args = ("Could not load %(appLabel)s.%(objectName)s(pk=%(pk)s): %(errorMsg)s" % {
                'appLabel': obj.object._meta.appLabel,
                'objectName': obj.object._meta.objectName,
                'pk': obj.object.pk,
                'errorMsg': forceText(e)
              },)
              raise

        self.loadedObjectCount += loadedObjectsInFixture
        self.fixtureObjectCount += objectsInFixture
      except Exception as e:
        if not isinstance(e, CommandError):
          e.args = ("Problem installing fixture '%s': %s" % (fixtureFile, e),)
        raise
      finally:
        fixture.close()

      # Warn if the fixture we loaded contains 0 objects.
      if objectsInFixture == 0:
        warnings.warn(
          "No fixture data found for '%s'. (File format may be "
          "invalid.)" % fixtureName,
          RuntimeWarning
        )

  @lruCache.lruCache(maxsize=None)
  def findFixtures(self, fixtureLabel):
    """
    Finds fixture files for a given label.
    """
    fixtureName, serFmt, cmpFmt = self.parseName(fixtureLabel)
    databases = [self.using, None]
    cmpFmts = list(self.compressionFormats.keys()) if cmpFmt is None else [cmpFmt]
    serFmts = serializers.getPublicSerializerFormats() if serFmt is None else [serFmt]

    if self.verbosity >= 2:
      self.stdout.write("Loading '%s' fixture..." % fixtureName)

    if os.path.isabs(fixtureName):
      fixtureDirs = [os.path.dirname(fixtureName)]
      fixtureName = os.path.basename(fixtureName)
    else:
      fixtureDirs = self.fixtureDirs
      if os.path.sep in fixtureName:
        fixtureDirs = [os.path.join(dir_, os.path.dirname(fixtureName))
                for dir_ in fixtureDirs]
        fixtureName = os.path.basename(fixtureName)

    suffixes = ('.'.join(ext for ext in combo if ext)
        for combo in product(databases, serFmts, cmpFmts))
    targets = set('.'.join((fixtureName, suffix)) for suffix in suffixes)

    fixtureFiles = []
    for fixtureDir in fixtureDirs:
      if self.verbosity >= 2:
        self.stdout.write("Checking %s for fixture..." % humanize(fixtureDir))
      fixtureFilesInDir = []
      for candidate in glob.iglob(os.path.join(fixtureDir, fixtureName + '*')):
        if os.path.basename(candidate) in targets:
          # Save the fixtureDir and fixtureName for future error messages.
          fixtureFilesInDir.append((candidate, fixtureDir, fixtureName))

      if self.verbosity >= 2 and not fixtureFilesInDir:
        self.stdout.write("No fixture '%s' in %s." %
                 (fixtureName, humanize(fixtureDir)))

      # Check kept for backwards-compatibility; it isn't clear why
      # duplicates are only allowed in different directories.
      if len(fixtureFilesInDir) > 1:
        raise CommandError(
          "Multiple fixture named '%s' in %s. Aborting." %
          (fixtureName, humanize(fixtureDir)))
      fixtureFiles.extend(fixtureFilesInDir)

    if fixtureName != 'initialData' and not fixtureFiles:
      # Warning kept for backwards-compatibility; why not an exception?
      warnings.warn("No fixture named '%s' found." % fixtureName)

    return fixtureFiles

  @cachedProperty
  def fixtureDirs(self):
    """
    Return a list of fixture directories.

    The list contains the 'fixture' subdirectory of each installed
    application, if it exists, the directories in FIXTURE_DIRS, and the
    current directory.
    """
    dirs = []
    for appConfig in apps.getAppConfigs():
      if self.appLabel and appConfig.label != self.appLabel:
        continue
      appDir = os.path.join(appConfig.path, 'fixture')
      if os.path.isdir(appDir):
        dirs.append(appDir)
    dirs.extend(list(settings.FIXTURE_DIRS))
    dirs.append('')
    dirs = [upath(os.path.abspath(os.path.realpath(d))) for d in dirs]
    return dirs

  def parseName(self, fixtureName):
    """
    Splits fixture name in name, serialization format, compression format.
    """
    parts = fixtureName.rsplit('.', 2)

    if len(parts) > 1 and parts[-1] in self.compressionFormats:
      cmpFmt = parts[-1]
      parts = parts[:-1]
    else:
      cmpFmt = None

    if len(parts) > 1:
      if parts[-1] in self.serializationFormats:
        serFmt = parts[-1]
        parts = parts[:-1]
      else:
        raise CommandError(
          "Problem installing fixture '%s': %s is not a known "
          "serialization format." % (''.join(parts[:-1]), parts[-1]))
    else:
      serFmt = None

    name = '.'.join(parts)

    return name, serFmt, cmpFmt


class SingleZipReader(zipfile.ZipFile):

  def __init__(self, *args, **kwargs):
    zipfile.ZipFile.__init__(self, *args, **kwargs)
    if len(self.namelist()) != 1:
      raise ValueError("Zip-compressed fixture must contain one file.")

  def read(self):
    return zipfile.ZipFile.read(self, self.namelist()[0])


def humanize(dirname):
  return "'%s'" % dirname if dirname else 'absolute path'
