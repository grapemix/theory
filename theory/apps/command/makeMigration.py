# -*- coding: utf-8 -*-
#!/usr/bin/env python
##### System wide lib #####
import sys
import os
import operator
try:
  from StringIO import StringIO
except:
  from io import StringIO

##### Theory lib #####
from theory.apps.command.baseCommand import SimpleCommand
from theory.gui import field


from theory.apps import apps
from theory.db.migrations import Migration
from theory.db.migrations.loader import MigrationLoader
from theory.db.migrations.autodetector import MigrationAutodetector
from theory.db.migrations.questioner import MigrationQuestioner, InteractiveMigrationQuestioner
from theory.db.migrations.state import ProjectState
from theory.db.migrations.writer import MigrationWriter
from theory.gui.color import noStyle
from theory.utils.six import iteritems
from theory.utils.six.moves import reduce

##### Theory third-party lib #####

##### Local app #####

##### Theory app #####

##### Misc #####

class MakeMigration(SimpleCommand):
  """
  Creates new migration(s) for apps.
  """
  name = "makeMigration"
  verboseName = "makeMigration"
  _notations = ["Command",]
  _drums = {"Terminal": 1, }

  class ParamForm(SimpleCommand.ParamForm):
    appLabelLst = field.ListField(
        field.TextField(maxLen=32),
        label="Application Name",
        helpText='Specify the app label(s) to create migrations for.',
        required=False,
        initData=[],
        )
    isDryRun = field.BooleanField(
        label="is dry run",
        helpText=(
          "Just show what migrations would be made; "
          "don't actually write them."
          ),
        required=False,
        initData=False,
        )
    isMerge = field.BooleanField(
        label="is merge",
        helpText="Enable fixing of migration conflicts.",
        required=False,
        initData=False,
        )
    isEmpty = field.BooleanField(
        label="is empty",
        helpText="Create an empty migration.",
        required=False,
        initData=False,
        )

  @property
  def stdOut(self):
    return self._stdOut

  def run(self):
    options = self.paramForm.clean()

    self.verbosity = options.get('verbosity')
    self.interactive = False
    self.dryRun = options.get('isDryRun', False)
    self.merge = options.get('isMerge', False)
    self.empty = options.get('isEmpty', False)
    self.stdout = StringIO()
    self.style = noStyle()

    # Make sure the app they asked for exists
    appLabels = set(options["appLabelLst"])
    badAppLabels = set()
    for appLabel in appLabels:
      try:
        apps.getAppConfig(appLabel)
      except LookupError:
        badAppLabels.add(appLabel)
    if badAppLabels:
      for appLabel in badAppLabels:
        self.stdout.write("App '%s' could not be found. Is it in INSTALLED_APPS?" % appLabel)
        self._stdOut = self.stdout.getvalue()
        self.stdout.close()
      return

    # Load the current graph state. Pass in None for the connection so
    # the loader doesn't try to resolve replaced migrations from DB.
    loader = MigrationLoader(None, ignoreNoMigrations=True)

    # Before anything else, see if there's conflicting apps and drop out
    # hard if there are any and they don't want to merge
    conflicts = loader.detectConflicts()

    # If appLabels is specified, filter out conflicting migrations for unspecified apps
    if appLabels:
      conflicts = dict(
        (appLabel, conflict) for appLabel, conflict in iteritems(conflicts)
        if appLabel in appLabels
      )

    if conflicts and not self.merge:
      nameStr = "; ".join(
        "%s in %s" % (", ".join(names), app)
        for app, names in conflicts.items()
      )
      raise CommandError("Conflicting migrations detected (%s).\nTo fix them run 'python manage.py makemigrations --merge'" % nameStr)

    # If they want to merge and there's nothing to merge, then politely exit
    if self.merge and not conflicts:
      self.stdout.write("No conflicts detected to merge.")
      self._stdOut = self.stdout.getvalue()
      self.stdout.close()
      return

    # If they want to merge and there is something to merge, then
    # divert into the merge code
    if self.merge and conflicts:
      self._stdOut = self.stdout.getvalue()
      self.stdout.close()
      return self.handleMerge(loader, conflicts)

    # Set up autodetector
    autodetector = MigrationAutodetector(
      loader.projectState(),
      ProjectState.fromApps(apps),
      InteractiveMigrationQuestioner(specifiedApps=appLabels, dryRun=self.dryRun),
    )

    # If they want to make an empty migration, make one for each app
    if self.empty:
      if not appLabels:
        raise CommandError("You must supply at least one app label when using --empty.")
      # Make a fake changes() result we can pass to arrangeForGraph
      changes = dict(
        (app, [Migration("custom", app)])
        for app in appLabels
      )
      changes = autodetector.arrangeForGraph(changes, loader.graph)
      self.writeMigrationFiles(changes)
      self._stdOut = self.stdout.getvalue()
      self.stdout.close()
      return

    # Detect changes
    changes = autodetector.changes(
      graph=loader.graph,
      trimToApps=appLabels or None,
      convertApps=appLabels or None,
    )

    # No changes? Tell them.
    if not changes and self.verbosity >= 1:
      if len(appLabels) == 1:
        self.stdout.write("No changes detected in app '%s'" % appLabels.pop())
      elif len(appLabels) > 1:
        self.stdout.write("No changes detected in apps '%s'" % ("', '".join(appLabels)))
      else:
        self.stdout.write("No changes detected")
      self._stdOut = self.stdout.getvalue()
      self.stdout.close()
      return

    self.writeMigrationFiles(changes)

  def writeMigrationFiles(self, changes):
    """
    Takes a changes dict and writes them out as migration files.
    """
    directoryCreated = {}
    for appLabel, appMigrations in changes.items():
      if self.verbosity >= 1:
        self.stdout.write(self.style.MIGRATE_HEADING("Migrations for '%s':" % appLabel) + "\n")
      for migration in appMigrations:
        # Describe the migration
        writer = MigrationWriter(migration)
        if self.verbosity >= 1:
          self.stdout.write("  %s:\n" % (self.style.MIGRATE_LABEL(writer.filename),))
          for operation in migration.operations:
            self.stdout.write("    - %s\n" % operation.describe())
        if not self.dryRun:
          # Write the migrations file to the disk.
          migrationsDirectory = os.path.dirname(writer.path)
          if not directoryCreated.get(appLabel, False):
            if not os.path.isdir(migrationsDirectory):
              os.mkdir(migrationsDirectory)
            initPath = os.path.join(migrationsDirectory, "__init__.py")
            if not os.path.isfile(initPath):
              open(initPath, "w").close()
            # We just do this once per app
            directoryCreated[appLabel] = True
          migrationString = writer.asString()
          with open(writer.path, "wb") as fh:
            fh.write(migrationString)
        elif self.verbosity == 3:
          # Alternatively, makemigrations --dry-run --verbosity 3
          # will output the migrations to stdout rather than saving
          # the file to the disk.
          self.stdout.write(self.style.MIGRATE_HEADING("Full migrations file '%s':" % writer.filename) + "\n")
          self.stdout.write("%s\n" % writer.asString())

  def handleMerge(self, loader, conflicts):
    """
    Handles merging together conflicted migrations interactively,
    if it's safe; otherwise, advises on how to fix it.
    """
    if self.interactive:
      questioner = InteractiveMigrationQuestioner()
    else:
      questioner = MigrationQuestioner(defaults={'askMerge': True})
    for appLabel, migrationNames in conflicts.items():
      # Grab out the migrations in question, and work out their
      # common ancestor.
      mergeMigrations = []
      for migrationName in migrationNames:
        migration = loader.getMigration(appLabel, migrationName)
        migration.ancestry = loader.graph.forwardsPlan((appLabel, migrationName))
        mergeMigrations.append(migration)
      commonAncestor = None
      for level in zip(*[m.ancestry for m in mergeMigrations]):
        if reduce(operator.eq, level):
          commonAncestor = level[0]
        else:
          break
      if commonAncestor is None:
        raise ValueError("Could not find common ancestor of %s" % migrationNames)
      # Now work out the operations along each divergent branch
      for migration in mergeMigrations:
        migration.branch = migration.ancestry[
          (migration.ancestry.index(commonAncestor) + 1):
        ]
        migration.mergedOperations = []
        for nodeApp, nodeName in migration.branch:
          migration.mergedOperations.extend(
            loader.getMigration(nodeApp, nodeName).operations
          )
      # In future, this could use some of the Optimizer code
      # (canOptimizeThrough) to automatically see if they're
      # mergeable. For now, we always just prompt the user.
      if self.verbosity > 0:
        self.stdout.write(self.style.MIGRATE_HEADING("Merging %s" % appLabel))
        for migration in mergeMigrations:
          self.stdout.write(self.style.MIGRATE_LABEL("  Branch %s" % migration.name))
          for operation in migration.mergedOperations:
            self.stdout.write("    - %s\n" % operation.describe())
      if questioner.askMerge(appLabel):
        # If they still want to merge it, then write out an empty
        # file depending on the migrations needing merging.
        numbers = [
          MigrationAutodetector.parseNumber(migration.name)
          for migration in mergeMigrations
        ]
        try:
          biggestNumber = max([x for x in numbers if x is not None])
        except ValueError:
          biggestNumber = 1
        subclass = type("Migration", (Migration, ), {
          "dependencies": [(appLabel, migration.name) for migration in mergeMigrations],
        })
        newMigration = subclass("%04iMerge" % (biggestNumber + 1), appLabel)
        writer = MigrationWriter(newMigration)
        with open(writer.path, "wb") as fh:
          fh.write(writer.asString())
        if self.verbosity > 0:
          self.stdout.write("\nCreated new merge migration %s" % writer.path)
