from theory.db.backends.schema import BaseDatabaseSchemaEditor
from theory.db.model import NOT_PROVIDED


class DatabaseSchemaEditor(BaseDatabaseSchemaEditor):

  sqlRenameTable = "RENAME TABLE %(oldTable)s TO %(newTable)s"

  sqlAlterColumnNull = "MODIFY %(column)s %(type)s NULL"
  sqlAlterColumnNotNull = "MODIFY %(column)s %(type)s NOT NULL"
  sqlAlterColumnType = "MODIFY %(column)s %(type)s"
  sqlRenameColumn = "ALTER TABLE %(table)s CHANGE %(oldColumn)s %(newColumn)s %(type)s"

  sqlDeleteUnique = "ALTER TABLE %(table)s DROP INDEX %(name)s"

  sqlCreateFk = "ALTER TABLE %(table)s ADD CONSTRAINT %(name)s FOREIGN KEY (%(column)s) REFERENCES %(toTable)s (%(toColumn)s)"
  sqlDeleteFk = "ALTER TABLE %(table)s DROP FOREIGN KEY %(name)s"

  sqlDeleteIndex = "DROP INDEX %(name)s ON %(table)s"

  sqlDeletePk = "ALTER TABLE %(table)s DROP PRIMARY KEY"

  alterStringSetNull = 'MODIFY %(column)s %(type)s NULL;'
  alterStringDropNull = 'MODIFY %(column)s %(type)s NOT NULL;'

  sqlCreatePk = "ALTER TABLE %(table)s ADD CONSTRAINT %(name)s PRIMARY KEY (%(columns)s)"
  sqlDeletePk = "ALTER TABLE %(table)s DROP PRIMARY KEY"

  def quoteValue(self, value):
    # Inner import to allow module to fail to load gracefully
    import MySQLdb.converters
    return MySQLdb.escape(value, MySQLdb.converters.conversions)

  def skipDefault(self, field):
    """
    MySQL doesn't accept default values for longtext and longblob
    and implicitly treats these columns as nullable.
    """
    return field.dbType(self.connection) in {'longtext', 'longblob'}

  def addField(self, modal, field):
    super(DatabaseSchemaEditor, self).addField(modal, field)

    # Simulate the effect of a one-off default.
    if self.skipDefault(field) and field.default not in {None, NOT_PROVIDED}:
      effectiveDefault = self.effectiveDefault(field)
      self.execute('UPDATE %(table)s SET %(column)s = %%s' % {
        'table': self.quoteName(modal._meta.dbTable),
        'column': self.quoteName(field.column),
      }, [effectiveDefault])
