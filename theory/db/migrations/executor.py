from __future__ import unicode_literals

from theory.db import migrations
from theory.apps.registry import apps as globalApps
from .loader import MigrationLoader
from .recorder import MigrationRecorder


class MigrationExecutor(object):
  """
  End-to-end migration execution - loads migrations, and runs them
  up or down to a specified set of targets.
  """

  def __init__(self, connection, progressCallback=None):
    self.connection = connection
    self.loader = MigrationLoader(self.connection)
    self.recorder = MigrationRecorder(self.connection)
    self.progressCallback = progressCallback

  def migrationPlan(self, targets):
    """
    Given a set of targets, returns a list of (Migration instance, backwards?).
    """
    plan = []
    applied = set(self.loader.appliedMigrations)
    for target in targets:
      # If the target is (appLabel, None), that means unmigrate everything
      if target[1] is None:
        for root in self.loader.graph.rootNodes():
          if root[0] == target[0]:
            for migration in self.loader.graph.backwardsPlan(root):
              if migration in applied:
                plan.append((self.loader.graph.nodes[migration], True))
                applied.remove(migration)
      # If the migration is already applied, do backwards mode,
      # otherwise do forwards mode.
      elif target in applied:
        backwardsPlan = self.loader.graph.backwardsPlan(target)[:-1]
        # We only do this if the migration is not the most recent one
        # in its app - that is, another migration with the same app
        # label is in the backwards plan
        if any(node[0] == target[0] for node in backwardsPlan):
          for migration in backwardsPlan:
            if migration in applied:
              plan.append((self.loader.graph.nodes[migration], True))
              applied.remove(migration)
      else:
        for migration in self.loader.graph.forwardsPlan(target):
          if migration not in applied:
            plan.append((self.loader.graph.nodes[migration], False))
            applied.add(migration)
    return plan

  def migrate(self, targets, plan=None, fake=False):
    """
    Migrates the database up to the given targets.
    """
    if plan is None:
      plan = self.migrationPlan(targets)
    for migration, backwards in plan:
      if not backwards:
        self.applyMigration(migration, fake=fake)
      else:
        self.unapplyMigration(migration, fake=fake)

  def collectSql(self, plan):
    """
    Takes a migration plan and returns a list of collected SQL
    statements that represent the best-efforts version of that plan.
    """
    statements = []
    for migration, backwards in plan:
      with self.connection.schemaEditor(collectSql=True) as schemaEditor:
        projectState = self.loader.projectState((migration.appLabel, migration.name), atEnd=False)
        if not backwards:
          migration.apply(projectState, schemaEditor, collectSql=True)
        else:
          migration.unapply(projectState, schemaEditor, collectSql=True)
      statements.extend(schemaEditor.collectedSql)
    return statements

  def applyMigration(self, migration, fake=False):
    """
    Runs a migration forwards.
    """
    if self.progressCallback:
      self.progressCallback("applyStart", migration, fake)
    if not fake:
      # Test to see if this is an already-applied initial migration
      if self.detectSoftApplied(migration):
        fake = True
      else:
        # Alright, do it normally
        with self.connection.schemaEditor() as schemaEditor:
          projectState = self.loader.projectState((migration.appLabel, migration.name), atEnd=False)
          migration.apply(projectState, schemaEditor)
    # For replacement migrations, record individual statuses
    if migration.replaces:
      for appLabel, name in migration.replaces:
        self.recorder.recordApplied(appLabel, name)
    else:
      self.recorder.recordApplied(migration.appLabel, migration.name)
    # Report progress
    if self.progressCallback:
      self.progressCallback("applySuccess", migration, fake)

  def unapplyMigration(self, migration, fake=False):
    """
    Runs a migration backwards.
    """
    if self.progressCallback:
      self.progressCallback("unapplyStart", migration, fake)
    if not fake:
      with self.connection.schemaEditor() as schemaEditor:
        projectState = self.loader.projectState((migration.appLabel, migration.name), atEnd=False)
        migration.unapply(projectState, schemaEditor)
    # For replacement migrations, record individual statuses
    if migration.replaces:
      for appLabel, name in migration.replaces:
        self.recorder.recordUnapplied(appLabel, name)
    else:
      self.recorder.recordUnapplied(migration.appLabel, migration.name)
    # Report progress
    if self.progressCallback:
      self.progressCallback("unapplySuccess", migration, fake)

  def detectSoftApplied(self, migration):
    """
    Tests whether a migration has been implicitly applied - that the
    tables it would create exist. This is intended only for use
    on initial migrations (as it only looks for CreateModel).
    """
    projectState = self.loader.projectState((migration.appLabel, migration.name), atEnd=True)
    apps = projectState.render()
    foundCreateMigration = False
    # Bail if the migration isn't the first one in its app
    if [name for app, name in migration.dependencies if app == migration.appLabel]:
      return False
    # Make sure all create modal are done
    for operation in migration.operations:
      if isinstance(operation, migrations.CreateModel):
        modal = apps.getModel(migration.appLabel, operation.name)
        if modal._meta.swapped:
          # We have to fetch the modal to test with from the
          # main app cache, as it's not a direct dependency.
          modal = globalApps.getModel(modal._meta.swapped)
        if modal._meta.dbTable not in self.connection.introspection.getTableList(self.connection.cursor()):
          return False
        foundCreateMigration = True
    # If we get this far and we found at least one CreateModel migration,
    # the migration is considered implicitly applied.
    return foundCreateMigration
