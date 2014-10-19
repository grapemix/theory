from __future__ import unicode_literals

from importlib import import_module
import os
import sys

from theory.apps import apps
from theory.db.migrations.recorder import MigrationRecorder
from theory.db.migrations.graph import MigrationGraph
from theory.utils import six
from theory.conf import settings


MIGRATIONS_MODULE_NAME = 'migrations'


class MigrationLoader(object):
  """
  Loads migration files from disk, and their status from the database.

  Migration files are expected to live in the "migrations" directory of
  an app. Their names are entirely unimportant from a code perspective,
  but will probably follow the 1234Name.py convention.

  On initialization, this class will scan those directories, and open and
  read the python files, looking for a class called Migration, which should
  inherit from theory.db.migrations.Migration. See
  theory.db.migrations.migration for what that looks like.

  Some migrations will be marked as "replacing" another set of migrations.
  These are loaded into a separate set of migrations away from the main ones.
  If all the migrations they replace are either unapplied or missing from
  disk, then they are injected into the main set, replacing the named migrations.
  Any dependency pointers to the replaced migrations are re-pointed to the
  new migration.

  This does mean that this class MUST also talk to the database as well as
  to disk, but this is probably fine. We're already not just operating
  in memory.
  """

  def __init__(self, connection, load=True, ignoreNoMigrations=False):
    self.connection = connection
    self.diskMigrations = None
    self.appliedMigrations = None
    self.ignoreNoMigrations = ignoreNoMigrations
    if load:
      self.buildGraph()

  @classmethod
  def migrationsModule(cls, appLabel):
    if appLabel in settings.MIGRATION_MODULES:
      return settings.MIGRATION_MODULES[appLabel]
    else:
      appPackageName = apps.getAppConfig(appLabel).name
      return '%s.%s' % (appPackageName, MIGRATIONS_MODULE_NAME)

  def loadDisk(self):
    """
    Loads the migrations from all INSTALLED_APPS from disk.
    """
    self.diskMigrations = {}
    self.unmigratedApps = set()
    self.migratedApps = set()
    for appConfig in apps.getAppConfigs():
      if appConfig.modelModule is None:
        continue
      # Get the migrations module directory
      moduleName = self.migrationsModule(appConfig.label)
      wasLoaded = moduleName in sys.modules
      try:
        module = import_module(moduleName)
      except ImportError as e:
        # I hate doing this, but I don't want to squash other import errors.
        # Might be better to try a directory check directly.
        if "No module named" in str(e) and MIGRATIONS_MODULE_NAME in str(e):
          self.unmigratedApps.add(appConfig.label)
          continue
        raise
      else:
        # PY3 will happily import empty dirs as namespaces.
        if not hasattr(module, '__file__'):
          continue
        # Module is not a package (e.g. migrations.py).
        if not hasattr(module, '__path__'):
          continue
        # Force a reload if it's already loaded (tests need this)
        if wasLoaded:
          six.moves.reload_module(module)
      self.migratedApps.add(appConfig.label)
      directory = os.path.dirname(module.__file__)
      # Scan for .py files
      migrationNames = set()
      for name in os.listdir(directory):
        if name.endswith(".py"):
          importName = name.rsplit(".", 1)[0]
          if importName[0] not in "_.~":
            migrationNames.add(importName)
      # Load them
      southStyleMigrations = False
      for migrationName in migrationNames:
        try:
          migrationModule = import_module("%s.%s" % (moduleName, migrationName))
        except ImportError as e:
          # Ignore South import errors, as we're triggering them
          if "south" in str(e).lower():
            southStyleMigrations = True
            break
          raise
        if not hasattr(migrationModule, "Migration"):
          raise BadMigrationError("Migration %s in app %s has no Migration class" % (migrationName, appConfig.label))
        # Ignore South-style migrations
        if hasattr(migrationModule.Migration, "forwards"):
          southStyleMigrations = True
          break
        self.diskMigrations[appConfig.label, migrationName] = migrationModule.Migration(migrationName, appConfig.label)
      if southStyleMigrations:
        self.unmigratedApps.add(appConfig.label)

  def getMigration(self, appLabel, namePrefix):
    "Gets the migration exactly named, or raises KeyError"
    return self.graph.nodes[appLabel, namePrefix]

  def getMigrationByPrefix(self, appLabel, namePrefix):
    "Returns the migration(s) which match the given app label and name _prefix_"
    # Do the search
    results = []
    for l, n in self.diskMigrations:
      if l == appLabel and n.startswith(namePrefix):
        results.append((l, n))
    if len(results) > 1:
      raise AmbiguityError("There is more than one migration for '%s' with the prefix '%s'" % (appLabel, namePrefix))
    elif len(results) == 0:
      raise KeyError("There no migrations for '%s' with the prefix '%s'" % (appLabel, namePrefix))
    else:
      return self.diskMigrations[results[0]]

  def checkKey(self, key, currentApp):
    if (key[1] != "__first__" and key[1] != "__latest__") or key in self.graph:
      return key
    # Special-case __first__, which means "the first migration" for
    # migrated apps, and is ignored for unmigrated apps. It allows
    # makemigrations to declare dependencies on apps before they even have
    # migrations.
    if key[0] == currentApp:
      # Ignore __first__ references to the same app (#22325)
      return
    if key[0] in self.unmigratedApps:
      # This app isn't migrated, but something depends on it.
      # The model will get auto-added into the state, though
      # so we're fine.
      return
    if key[0] in self.migratedApps:
      try:
        if key[1] == "__first__":
          return list(self.graph.rootNodes(key[0]))[0]
        else:
          return list(self.graph.leafNodes(key[0]))[0]
      except IndexError:
        if self.ignoreNoMigrations:
          return None
        else:
          raise ValueError("Dependency on app with no migrations: %s" % key[0])
    raise ValueError("Dependency on unknown app: %s" % key[0])

  def buildGraph(self):
    """
    Builds a migration dependency graph using both the disk and database.
    You'll need to rebuild the graph if you apply migrations. This isn't
    usually a problem as generally migration stuff runs in a one-shot process.
    """
    # Load disk data
    self.loadDisk()
    # Load database data
    if self.connection is None:
      self.appliedMigrations = set()
    else:
      recorder = MigrationRecorder(self.connection)
      self.appliedMigrations = recorder.appliedMigrations()
    # Do a first pass to separate out replacing and non-replacing migrations
    normal = {}
    replacing = {}
    for key, migration in self.diskMigrations.items():
      if migration.replaces:
        replacing[key] = migration
      else:
        normal[key] = migration
    # Calculate reverse dependencies - i.e., for each migration, what depends on it?
    # This is just for dependency re-pointing when applying replacements,
    # so we ignore runBefore here.
    reverseDependencies = {}
    for key, migration in normal.items():
      for parent in migration.dependencies:
        reverseDependencies.setdefault(parent, set()).add(key)
    # Carry out replacements if we can - that is, if all replaced migrations
    # are either unapplied or missing.
    for key, migration in replacing.items():
      # Ensure this replacement migration is not in appliedMigrations
      self.appliedMigrations.discard(key)
      # Do the check. We can replace if all our replace targets are
      # applied, or if all of them are unapplied.
      appliedStatuses = [(target in self.appliedMigrations) for target in migration.replaces]
      canReplace = all(appliedStatuses) or (not any(appliedStatuses))
      if not canReplace:
        continue
      # Alright, time to replace. Step through the replaced migrations
      # and remove, repointing dependencies if needs be.
      for replaced in migration.replaces:
        if replaced in normal:
          # We don't care if the replaced migration doesn't exist;
          # the usage pattern here is to delete things after a while.
          del normal[replaced]
        for childKey in reverseDependencies.get(replaced, set()):
          if childKey in migration.replaces:
            continue
          normal[childKey].dependencies.remove(replaced)
          normal[childKey].dependencies.append(key)
      normal[key] = migration
      # Mark the replacement as applied if all its replaced ones are
      if all(appliedStatuses):
        self.appliedMigrations.add(key)
    # Finally, make a graph and load everything into it
    self.graph = MigrationGraph()
    for key, migration in normal.items():
      self.graph.addNode(key, migration)
    # Add all internal dependencies first to ensure __first__ dependencies
    # find the correct root node.
    for key, migration in normal.items():
      for parent in migration.dependencies:
        if parent[0] != key[0] or parent[1] == '__first__':
          # Ignore __first__ references to the same app (#22325)
          continue
        self.graph.addDependency(key, parent)
    for key, migration in normal.items():
      for parent in migration.dependencies:
        if parent[0] == key[0]:
          # Internal dependencies already added.
          continue
        parent = self.checkKey(parent, key[0])
        if parent is not None:
          self.graph.addDependency(key, parent)
      for child in migration.runBefore:
        child = self.checkKey(child, key[0])
        if child is not None:
          self.graph.addDependency(child, key)

  def detectConflicts(self):
    """
    Looks through the loaded graph and detects any conflicts - apps
    with more than one leaf migration. Returns a dict of the app labels
    that conflict with the migration names that conflict.
    """
    seenApps = {}
    conflictingApps = set()
    for appLabel, migrationName in self.graph.leafNodes():
      if appLabel in seenApps:
        conflictingApps.add(appLabel)
      seenApps.setdefault(appLabel, set()).add(migrationName)
    return dict((appLabel, seenApps[appLabel]) for appLabel in conflictingApps)

  def projectState(self, nodes=None, atEnd=True):
    """
    Returns a ProjectState object representing the most recent state
    that the migrations we loaded represent.

    See graph.makeState for the meaning of "nodes" and "atEnd"
    """
    return self.graph.makeState(nodes=nodes, atEnd=atEnd, realApps=list(self.unmigratedApps))


class BadMigrationError(Exception):
  """
  Raised when there's a bad migration (unreadable/bad format/etc.)
  """
  pass


class AmbiguityError(Exception):
  """
  Raised when more than one migration matches a name prefix
  """
  pass
