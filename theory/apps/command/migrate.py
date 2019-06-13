from __future__ import unicode_literals
# -*- coding: utf-8 -*-
#!/usr/bin/env python
##### System wide lib #####
from collections import OrderedDict
from importlib import import_module
import itertools
import traceback
try:
  from StringIO import StringIO
except:
  from io import StringIO

##### Theory lib #####
from theory.apps.command.baseCommand import SimpleCommand
from theory.gui import field
from theory.core.bridge import Bridge

from theory.apps import apps
from theory.core.exceptions import CommandError
from theory.gui.color import noStyle
from theory.core.sql import customSqlForModel, emitPostMigrateSignal, emitPreMigrateSignal
from theory.db import connections, router, transaction, DEFAULT_DB_ALIAS
from theory.db.migrations.executor import MigrationExecutor
from theory.db.migrations.loader import MigrationLoader, AmbiguityError
from theory.db.migrations.state import ProjectState
from theory.db.migrations.autodetector import MigrationAutodetector
from theory.utils.moduleLoading import moduleHasSubmodule


##### Theory third-party lib #####

##### Local app #####

##### Theory app #####

##### Misc #####

#class TextPrinter(StringIO):
#  def write(self, *args, **kwargs):
#    if "ending" in kwargs:
#      del kwargs["ending"]
#    return TextPrinter.write(*args, **kwargs)

class Migrate(SimpleCommand):
  """
  Updates database schema. Manages both apps with migrations and those without.
  """
  name = "migrate"
  verboseName = "migrate"
  _notations = ["Command",]
  _drums = {"Terminal": 1, }

  #def addArguments(self, parser):
  #  parser.addArgument('appLabel', nargs='?',
  #    help='App label of an application to synchronize the state.')
  #  parser.addArgument('migrationName', nargs='?',
  #    help='Database state will be brought to the state after that migration.')
  #  parser.addArgument('--noinput', action='storeFalse', dest='interactive', default=True,
  #    help='Tells Theory to NOT prompt the user for input of any kind.')


  class ParamForm(SimpleCommand.ParamForm):
    appLabel = field.TextField(
        label="Application Name",
        helpText=" The name of application being created",
        required=False,
        maxLen=32
        )
    isInitialData = field.BooleanField(
        label="is initial data",
        helpText='Tells Theory not to load any initial data after database synchronization.',
        initData=False,
        )
    database = field.TextField(
        label="database",
        helpText=(
          'Nominates a database to synchronize.',
          'Defaults to the "default" database.'
          ),
        initData=DEFAULT_DB_ALIAS,
        )
    migrationName = field.TextField(
        label="Migration Name",
        helpText=(
          'Database state will be brought to the state after that migration.'
          ),
        required=False,
        maxLen=64
        )
    isFake = field.BooleanField(
        label="is fake",
        helpText='Mark migrations as run without actually running them',
        initData=False,
        )
    isList = field.BooleanField(
        label="is list",
        helpText='Show a list of all known migrations and which are applied',
        required=False,
        initData=False,
        )
    isShowTraceback = field.BooleanField(
        label="is show traceback",
        helpText='Show traceback if they are available.',
        required=False,
        initData=False,
        )
    isTestDatabase = field.BooleanField(
        label="is test database",
        helpText='is test database',
        required=False,
        initData=False,
        )
    isTestFlush = field.BooleanField(
        label="is test flushing database",
        helpText='is test flushing database',
        required=False,
        initData=False,
        )

  def run(self):
    options = self.paramForm.clean()

    self.verbosity = options["verbosity"]
    self.interactive = False
    self.isShowTraceback = options["isShowTraceback"]
    self.isInitialData = options['isInitialData']
    self.isTestDatabase = options["isTestDatabase"]

    bridge = Bridge()
    self.stdout = StringIO()
    self.style = noStyle()

    # Import the 'management' module within each installed app, to register
    # dispatcher events.
    #for appConfig in apps.getAppConfigs():
    #  if moduleHasSubmodule(appConfig.module, "management"):
    #    import_module('.management', appConfig.name)

    # Get the database we're operating from
    db = options.get('database')
    connection = connections[db]

    # If they asked for a migration listing, quit main execution flow and show it
    if options["isList"]:
      self._stdOut = self.stdout.getvalue()
      self.stdout.close()
      return self.showMigrationList(connection, [options['appLabel']] if options['appLabel'] else None)

    # Work out which apps have migrations and which do not
    executor = MigrationExecutor(connection, self.migrationProgressCallback)

    # Before anything else, see if there's conflicting apps and drop out
    # hard if there are any
    conflicts = executor.loader.detectConflicts()
    if conflicts:
      nameStr = "; ".join(
        "%s in %s" % (", ".join(names), app)
        for app, names in conflicts.items()
      )
      raise CommandError("Conflicting migrations detected (%s).\nTo fix them run 'python manage.py makemigrations --merge'" % nameStr)

    # If they supplied command line arguments, work out what they mean.
    runSyncdb = False
    targetAppLabelsOnly = True
    if options['appLabel'] and options['migrationName']:
      appLabel, migrationName = options['appLabel'], options['migrationName']
      if appLabel not in executor.loader.migratedApps:
        raise CommandError("App '%s' does not have migrations (you cannot selectively sync unmigrated apps)" % appLabel)
      if migrationName == "zero":
        targets = [(appLabel, None)]
      else:
        try:
          migration = executor.loader.getMigrationByPrefix(appLabel, migrationName)
        except AmbiguityError:
          raise CommandError("More than one migration matches '%s' in app '%s'. Please be more specific." % (
            migrationName, appLabel))
        except KeyError:
          raise CommandError("Cannot find a migration matching '%s' from app '%s'." % (
            migrationName, appLabel))
        targets = [(appLabel, migration.name)]
      targetAppLabelsOnly = False
    elif options['appLabel']:
      appLabel = options['appLabel']
      if appLabel not in executor.loader.migratedApps:
        raise CommandError("App '%s' does not have migrations (you cannot selectively sync unmigrated apps)" % appLabel)
      targets = [key for key in executor.loader.graph.leafNodes() if key[0] == appLabel]
    else:
      targets = executor.loader.graph.leafNodes()
      runSyncdb = True

    plan = executor.migrationPlan(targets)

    # Print some useful info
    if self.verbosity >= 1:
      self.stdout.write(self.style.MIGRATE_HEADING("Operations to perform:"))
      if runSyncdb and executor.loader.unmigratedApps:
        self.stdout.write(self.style.MIGRATE_LABEL("  Synchronize unmigrated apps: ") + (", ".join(executor.loader.unmigratedApps)))
      if targetAppLabelsOnly:
        self.stdout.write(self.style.MIGRATE_LABEL("  Apply all migrations: ") + (", ".join(set(a for a, n in targets)) or "(none)"))
      else:
        if targets[0][1] is None:
          self.stdout.write(self.style.MIGRATE_LABEL("  Unapply all migrations: ") + "%s" % (targets[0][0], ))
        else:
          self.stdout.write(self.style.MIGRATE_LABEL("  Target specific migration: ") + "%s, from %s" % (targets[0][1], targets[0][0]))

    # Run the syncdb phase.
    # If you ever manage to get rid of this, I owe you many, many drinks.
    # Note that preMigrate is called from inside here, as it needs
    # the list of models about to be installed.
    if runSyncdb and executor.loader.unmigratedApps:
      if self.verbosity >= 1:
        self.stdout.write(self.style.MIGRATE_HEADING("Synchronizing apps without migrations:"))
      createdModels = self.syncApps(connection, executor.loader.unmigratedApps)
    else:
      createdModels = []

    # The test runner requires us to flush after a syncdb but before migrations,
    # so do that here.
    if options.get("isTestFlush", False):
      bridge.executeEzCommand(
          'theory',
          'flush',
          [],
          {
            "verbosity": max(self.verbosity - 1, 0),
            "database": db,
            "isResetSequence": False,
            "isInhibitPostMigrate": True,
          },
      )

    # Migrate!
    if self.verbosity >= 1:
      self.stdout.write(self.style.MIGRATE_HEADING("Running migrations:"))
    if not plan:
      if self.verbosity >= 1:
        self.stdout.write("  No migrations to apply.")
        # If there's changes that aren't in migrations yet, tell them how to fix it.
        autodetector = MigrationAutodetector(
          executor.loader.projectState(),
          ProjectState.fromApps(apps),
        )
        changes = autodetector.changes(graph=executor.loader.graph)
        if changes:
          self.stdout.write(self.style.NOTICE("  Your models have changes that are not yet reflected in a migration, and so won't be applied."))
          self.stdout.write(self.style.NOTICE("  Run 'manage.py makemigrations' to make new migrations, and then re-run 'manage.py migrate' to apply them."))
    else:
      executor.migrate(targets, plan, fake=options.get("fake", False))

    # Send the postMigrate signal, so individual apps can do whatever they need
    # to do at this point.
    emitPostMigrateSignal(createdModels, self.verbosity, self.interactive, connection.alias)
    self._stdOut = self.stdout.getvalue()
    self.stdout.close()

  def migrationProgressCallback(self, action, migration, fake=False):
    if self.verbosity >= 1:
      if action == "applyStart":
        self.stdout.write("  Applying %s..." % migration)
        self.stdout.flush()
      elif action == "applySuccess":
        if fake:
          self.stdout.write(self.style.MIGRATE_SUCCESS(" FAKED"))
        else:
          self.stdout.write(self.style.MIGRATE_SUCCESS(" OK"))
      elif action == "unapplyStart":
        self.stdout.write("  Unapplying %s..." % migration)
        self.stdout.flush()
      elif action == "unapplySuccess":
        if fake:
          self.stdout.write(self.style.MIGRATE_SUCCESS(" FAKED"))
        else:
          self.stdout.write(self.style.MIGRATE_SUCCESS(" OK"))

  def syncApps(self, connection, appLabels):
    "Runs the old syncdb-style operation on a list of appLabels."
    cursor = connection.cursor()

    try:
      # Get a list of already installed *models* so that references work right.
      tables = connection.introspection.tableNames(cursor)
      seenModels = connection.introspection.installedModels(tables)
      createdModels = set()
      pendingReferences = {}

      # Build the manifest of apps and models that are to be synchronized
      allModels = [
        (appConfig.label,
          router.getMigratableModels(appConfig, connection.alias, includeAutoCreated=True))
        for appConfig in apps.getAppConfigs()
        if appConfig.modelModule is not None and appConfig.label in appLabels
      ]

      def modelInstalled(model):
        opts = model._meta
        converter = connection.introspection.tableNameConverter
        # Note that if a model is unmanaged we short-circuit and never try to install it
        self._stdOut = self.stdout.getvalue()
        #self.stdout.close()
        return not ((converter(opts.dbTable) in tables) or
          (opts.autoCreated and converter(opts.autoCreated._meta.dbTable) in tables))

      manifest = OrderedDict(
        (appName, list(filter(modelInstalled, modelList)))
        for appName, modelList in allModels
      )

      createModels = set(itertools.chain(*manifest.values()))
      emitPreMigrateSignal(createModels, self.verbosity, self.interactive, connection.alias)

      # Create the tables for each model
      if self.verbosity >= 1:
        self.stdout.write("  Creating tables...\n")
      with transaction.atomic(using=connection.alias, savepoint=connection.features.canRollbackDdl):
        for appName, modelList in manifest.items():
          for model in modelList:
            # Create the model's database table, if it doesn't already exist.
            if self.verbosity >= 3:
              self.stdout.write("    Processing %s.%s model\n" % (appName, model._meta.objectName))
            sql, references = connection.creation.sqlCreateModel(model, noStyle(), seenModels)
            seenModels.add(model)
            createdModels.add(model)
            for refto, refs in references.items():
              pendingReferences.setdefault(refto, []).extend(refs)
              if refto in seenModels:
                sql.extend(connection.creation.sqlForPendingReferences(refto, noStyle(), pendingReferences))
            sql.extend(connection.creation.sqlForPendingReferences(model, noStyle(), pendingReferences))
            if self.verbosity >= 1 and sql:
              self.stdout.write("    Creating table %s\n" % model._meta.dbTable)
            for statement in sql:
              cursor.execute(statement)
            tables.append(connection.introspection.tableNameConverter(model._meta.dbTable))
    finally:
      cursor.close()

    # The connection may have been closed by a syncdb handler.
    cursor = connection.cursor()
    try:
      # Install custom SQL for the app (but only if this
      # is a model we've just created)
      if self.verbosity >= 1:
        self.stdout.write("  Installing custom SQL...\n")
      for appName, modelList in manifest.items():
        for model in modelList:
          if model in createdModels:
            customSql = customSqlForModel(model, noStyle(), connection)
            if customSql:
              if self.verbosity >= 2:
                self.stdout.write("    Installing custom SQL for %s.%s model\n" % (appName, model._meta.objectName))
              try:
                with transaction.atomic(using=connection.alias):
                  for sql in customSql:
                    cursor.execute(sql)
              except Exception as e:
                self.stderr.write("    Failed to install custom SQL for %s.%s model: %s\n" % (appName, model._meta.objectName, e))
                if self.isShowTraceback:
                  traceback.printExc()
            else:
              if self.verbosity >= 3:
                self.stdout.write("    No custom SQL for %s.%s model\n" % (appName, model._meta.objectName))

      if self.verbosity >= 1:
        self.stdout.write("  Installing indexes...\n")

      # Install SQL indices for all newly created models
      for appName, modelList in manifest.items():
        for model in modelList:
          if model in createdModels:
            indexSql = connection.creation.sqlIndexesForModel(model, noStyle())
            if indexSql:
              if self.verbosity >= 2:
                self.stdout.write("    Installing index for %s.%s model\n" % (appName, model._meta.objectName))
              try:
                with transaction.atomic(using=connection.alias, savepoint=connection.features.canRollbackDdl):
                  for sql in indexSql:
                    cursor.execute(sql)
              except Exception as e:
                #self.stderr.write("    Failed to install index for %s.%s model: %s\n" % (appName, model._meta.objectName, e))
                self.stdout.write("    Failed to install index for %s.%s model: %s\n" % (appName, model._meta.objectName, e))
    finally:
      cursor.close()

    # Load initialData fixtures (unless that has been disabled)
    if self.isInitialData:
      for appLabel in appLabels:
        bridge.executeEzCommand(
            'theory',
            'loaddata',
            [],
            {
              "fixtureLabel": "initialData",
              "verbosity": self.verbosity,
              "database": connection.alias,
              "appLabel": appLabel,
              "isHideEmpty": True
            }
        )

    return createdModels

  def showMigrationList(self, connection, appNames=None):
    """
    Shows a list of all migrations on the system, or only those of
    some named apps.
    """
    # Load migrations from disk/DB
    loader = MigrationLoader(connection)
    graph = loader.graph
    # If we were passed a list of apps, validate it
    if appNames:
      invalidApps = []
      for appName in appNames:
        if appName not in loader.migratedApps:
          invalidApps.append(appName)
      if invalidApps:
        raise CommandError("No migrations present for: %s" % (", ".join(invalidApps)))
    # Otherwise, show all apps in alphabetic order
    else:
      appNames = sorted(loader.migratedApps)
    # For each app, print its migrations in order from oldest (roots) to
    # newest (leaves).
    for appName in appNames:
      self.stdout.write(appName, self.style.MIGRATE_LABEL)
      shown = set()
      for node in graph.leafNodes(appName):
        for planNode in graph.forwardsPlan(node):
          if planNode not in shown and planNode[0] == appName:
            # Give it a nice title if it's a squashed one
            title = planNode[1]
            if graph.nodes[planNode].replaces:
              title += " (%s squashed migrations)" % len(graph.nodes[planNode].replaces)
            # Mark it as applied/unapplied
            if planNode in loader.appliedMigrations:
              self.stdout.write(" [X] %s" % title)
            else:
              self.stdout.write(" [ ] %s" % title)
            shown.add(planNode)
      # If we didn't print anything, then a small message
      if not shown:
        self.stdout.write(" (no migrations)", self.style.MIGRATE_FAILURE)
