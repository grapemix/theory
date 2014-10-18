from __future__ import unicode_literals

from theory.apps.registry import Apps
from theory.db import model
from theory.utils.encoding import python2UnicodeCompatible
from theory.utils.timezone import now


class MigrationRecorder(object):
  """
  Deals with storing migration records in the database.

  Because this table is actually itself used for dealing with modal
  creation, it's the one thing we can't do normally via syncdb or migrations.
  We manually handle table creation/schema updating (using schema backend)
  and then have a floating modal to do queries with.

  If a migration is unapplied its row is removed from the table. Having
  a row in the table always means a migration is applied.
  """

  @python2UnicodeCompatible
  class Migration(model.Model):
    app = model.CharField(maxLength=255)
    name = model.CharField(maxLength=255)
    applied = model.DateTimeField(default=now)

    class Meta:
      apps = Apps()
      appLabel = "migrations"
      dbTable = "theoryMigrations"

    def __str__(self):
      return "Migration %s for %s" % (self.name, self.app)

  def __init__(self, connection):
    self.connection = connection

  @property
  def migrationQs(self):
    return self.Migration.objects.using(self.connection.alias)

  def ensureSchema(self):
    """
    Ensures the table exists and has the correct schema.
    """
    # If the table's there, that's fine - we've never changed its schema
    # in the codebase.
    if self.Migration._meta.dbTable in self.connection.introspection.getTableList(self.connection.cursor()):
      return
    # Make the table
    with self.connection.schemaEditor() as editor:
      editor.createModel(self.Migration)

  def appliedMigrations(self):
    """
    Returns a set of (app, name) of applied migrations.
    """
    self.ensureSchema()
    return set(tuple(x) for x in self.migrationQs.valuesList("app", "name"))

  def recordApplied(self, app, name):
    """
    Records that a migration was applied.
    """
    self.ensureSchema()
    self.migrationQs.create(app=app, name=name)

  def recordUnapplied(self, app, name):
    """
    Records that a migration was unapplied.
    """
    self.ensureSchema()
    self.migrationQs.filter(app=app, name=name).delete()

  def flush(self):
    """
    Deletes all migration records. Useful if you're testing migrations.
    """
    self.migrationQs.all().delete()
