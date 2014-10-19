from __future__ import unicode_literals

import codecs
import os
import re
import warnings

from theory.apps import apps
from theory.conf import settings
from theory.core.exceptions import CommandSyntaxError
from theory.db import model, router
from theory.utils.deprecation import RemovedInTheory19Warning


def checkForMigrations(appConfig, connection):
  # Inner import, else tests imports it too early as it needs settings
  from theory.db.migrations.loader import MigrationLoader
  loader = MigrationLoader(connection)
  if appConfig.label in loader.migratedApps:
    raise CommandError("App '%s' has migrations. Only the sqlmigrate and sqlflush commands can be used when an app has migrations." % appConfig.label)


def sqlCreate(appConfig, style, connection):
  "Returns a list of the CREATE TABLE SQL statements for the given app."

  checkForMigrations(appConfig, connection)

  if connection.settingsDict['ENGINE'] == 'theory.db.backends.dummy':
    # This must be the "dummy" database backend, which means the user
    # hasn't set ENGINE for the database.
    raise CommandSyntaxError("Theory doesn't know which syntax to use for your SQL statements,\n" +
      "because you haven't properly specified the ENGINE setting for the database.\n" +
      "see: https://docs.theoryproject.com/en/dev/ref/settings/#databases")

  # Get installed models, so we generate REFERENCES right.
  # We trim models from the current app so that the sqlreset command does not
  # generate invalid SQL (leaving models out of knownModels is harmless, so
  # we can be conservative).
  appModels = appConfig.getModels(includeAutoCreated=True)
  finalOutput = []
  tables = connection.introspection.tableNames()
  knownModels = set(model for model in connection.introspection.installedModels(tables) if model not in appModels)
  pendingReferences = {}

  for model in router.getMigratableModels(appConfig, connection.alias, includeAutoCreated=True):
    output, references = connection.creation.sqlCreateModel(model, style, knownModels)
    finalOutput.extend(output)
    for refto, refs in references.items():
      pendingReferences.setdefault(refto, []).extend(refs)
      if refto in knownModels:
        finalOutput.extend(connection.creation.sqlForPendingReferences(refto, style, pendingReferences))
    finalOutput.extend(connection.creation.sqlForPendingReferences(model, style, pendingReferences))
    # Keep track of the fact that we've created the table for this model.
    knownModels.add(model)

  # Handle references to tables that are from other apps
  # but don't exist physically.
  notInstalledModels = set(pendingReferences.keys())
  if notInstalledModels:
    alterSql = []
    for model in notInstalledModels:
      alterSql.extend(['-- ' + sql for sql in
        connection.creation.sqlForPendingReferences(model, style, pendingReferences)])
    if alterSql:
      finalOutput.append('-- The following references should be added but depend on non-existent tables:')
      finalOutput.extend(alterSql)

  return finalOutput


def sqlDelete(appConfig, style, connection, closeConnection=True):
  "Returns a list of the DROP TABLE SQL statements for the given app."

  checkForMigrations(appConfig, connection)

  # This should work even if a connection isn't available
  try:
    cursor = connection.cursor()
  except Exception:
    cursor = None

  try:
    # Figure out which tables already exist
    if cursor:
      tableNames = connection.introspection.tableNames(cursor)
    else:
      tableNames = []

    output = []

    # Output DROP TABLE statements for standard application tables.
    toDelete = set()

    referencesToDelete = {}
    appModels = router.getMigratableModels(appConfig, connection.alias, includeAutoCreated=True)
    for model in appModels:
      if cursor and connection.introspection.tableNameConverter(model._meta.dbTable) in tableNames:
        # The table exists, so it needs to be dropped
        opts = model._meta
        for f in opts.localFields:
          if f.rel and f.rel.to not in toDelete:
            referencesToDelete.setdefault(f.rel.to, []).append((model, f))

        toDelete.add(model)

    for model in appModels:
      if connection.introspection.tableNameConverter(model._meta.dbTable) in tableNames:
        output.extend(connection.creation.sqlDestroyModel(model, referencesToDelete, style))
  finally:
    # Close database connection explicitly, in case this output is being piped
    # directly into a database client, to avoid locking issues.
    if cursor and closeConnection:
      cursor.close()
      connection.close()

  return output[::-1]  # Reverse it, to deal with table dependencies.


def sqlFlush(style, connection, onlyTheory=False, resetSequences=True, allowCascade=False):
  """
  Returns a list of the SQL statements used to flush the database.

  If onlyTheory is True, then only table names that have associated Theory
  models and are in INSTALLED_APPS will be included.
  """
  if onlyTheory:
    tables = connection.introspection.theoryTableNames(onlyExisting=True)
  else:
    tables = connection.introspection.tableNames()
  seqs = connection.introspection.sequenceList() if resetSequences else ()
  statements = connection.ops.sqlFlush(style, tables, seqs, allowCascade)
  return statements


def sqlCustom(appConfig, style, connection):
  "Returns a list of the custom table modifying SQL statements for the given app."

  checkForMigrations(appConfig, connection)

  output = []

  appModels = router.getMigratableModels(appConfig, connection.alias)

  for model in appModels:
    output.extend(customSqlForModel(model, style, connection))

  return output


def sqlIndexes(appConfig, style, connection):
  "Returns a list of the CREATE INDEX SQL statements for all models in the given app."

  checkForMigrations(appConfig, connection)

  output = []
  for model in router.getMigratableModels(appConfig, connection.alias, includeAutoCreated=True):
    output.extend(connection.creation.sqlIndexesForModel(model, style))
  return output


def sqlDestroyIndexes(appConfig, style, connection):
  "Returns a list of the DROP INDEX SQL statements for all models in the given app."

  checkForMigrations(appConfig, connection)

  output = []
  for model in router.getMigratableModels(appConfig, connection.alias, includeAutoCreated=True):
    output.extend(connection.creation.sqlDestroyIndexesForModel(model, style))
  return output


def sqlAll(appConfig, style, connection):

  checkForMigrations(appConfig, connection)

  "Returns a list of CREATE TABLE SQL, initial-data inserts, and CREATE INDEX SQL for the given module."
  return sqlCreate(appConfig, style, connection) + sqlCustom(appConfig, style, connection) + sqlIndexes(appConfig, style, connection)


def _splitStatements(content):
  # Private API only called from code that emits a RemovedInTheory19Warning.
  commentRe = re.compile(r"^((?:'[^']*'|[^'])*?)--.*$")
  statements = []
  statement = []
  for line in content.split("\n"):
    cleanedLine = commentRe.sub(r"\1", line).strip()
    if not cleanedLine:
      continue
    statement.append(cleanedLine)
    if cleanedLine.endswith(";"):
      statements.append(" ".join(statement))
      statement = []
  return statements


def customSqlForModel(model, style, connection):
  opts = model._meta
  appDirs = []
  appDir = apps.getAppConfig(model._meta.appLabel).path
  appDirs.append(os.path.normpath(os.path.join(appDir, 'sql')))

  # Deprecated location -- remove in Theory 1.9
  oldAppDir = os.path.normpath(os.path.join(appDir, 'model/sql'))
  if os.path.exists(oldAppDir):
    warnings.warn("Custom SQL location '<appLabel>/model/sql' is "
           "deprecated, use '<appLabel>/sql' instead.",
           RemovedInTheory19Warning)
    appDirs.append(oldAppDir)

  output = []

  # Post-creation SQL should come before any initial SQL data is loaded.
  # However, this should not be done for models that are unmanaged or
  # for fields that are part of a parent model (via model inheritance).
  if opts.managed:
    postSqlFields = [f for f in opts.localFields if hasattr(f, 'postCreateSql')]
    for f in postSqlFields:
      output.extend(f.postCreateSql(style, model._meta.dbTable))

  # Find custom SQL, if it's available.
  backendName = connection.settingsDict['ENGINE'].split('.')[-1]
  sqlFiles = []
  for appDir in appDirs:
    sqlFiles.append(os.path.join(appDir, "%s.%s.sql" % (opts.modelName, backendName)))
    sqlFiles.append(os.path.join(appDir, "%s.sql" % opts.modelName))
  for sqlFile in sqlFiles:
    if os.path.exists(sqlFile):
      with codecs.open(sqlFile, 'r', encoding=settings.FILE_CHARSET) as fp:
        output.extend(connection.ops.prepareSqlScript(fp.read(), _allowFallback=True))
  return output


def emitPreMigrateSignal(createModels, verbosity, interactive, db):
  # Emit the preMigrate signal for every application.
  for appConfig in apps.getAppConfigs():
    if appConfig.modelModule is None:
      continue
    if verbosity >= 2:
      print("Running pre-migrate handlers for application %s" % appConfig.label)
    model.signals.preMigrate.send(
      sender=appConfig,
      appConfig=appConfig,
      verbosity=verbosity,
      interactive=interactive,
      using=db)
    # For backwards-compatibility -- remove in Theory 1.9.
    model.signals.preSyncdb.send(
      sender=appConfig.modelModule,
      app=appConfig.modelModule,
      createModels=createModels,
      verbosity=verbosity,
      interactive=interactive,
      db=db)


def emitPostMigrateSignal(createdModels, verbosity, interactive, db):
  # Emit the postMigrate signal for every application.
  for appConfig in apps.getAppConfigs():
    if appConfig.modelModule is None:
      continue
    if verbosity >= 2:
      print("Running post-migrate handlers for application %s" % appConfig.label)
    model.signals.postMigrate.send(
      sender=appConfig,
      appConfig=appConfig,
      verbosity=verbosity,
      interactive=interactive,
      using=db)
    # For backwards-compatibility -- remove in Theory 1.9.
    model.signals.postSyncdb.send(
      sender=appConfig.modelModule,
      app=appConfig.modelModule,
      createdModels=createdModels,
      verbosity=verbosity,
      interactive=interactive,
      db=db)
