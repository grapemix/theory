import hashlib
import operator

from theory.db.backends.creation import BaseDatabaseCreation
from theory.db.backends.utils import truncateName
from theory.db.model.fields.related import ManyToManyField
from theory.db.transaction import atomic
from theory.utils.encoding import forceBytes
from theory.utils.log import getLogger
from theory.utils.six.moves import reduce
from theory.utils import six

logger = getLogger('theory.db.backends.schema')


class BaseDatabaseSchemaEditor(object):
  """
  This class (and its subclasses) are responsible for emitting schema-changing
  statements to the databases - modal creation/removal/alteration, field
  renaming, index fiddling, and so on.

  It is intended to eventually completely replace DatabaseCreation.

  This class should be used by creating an instance for each set of schema
  changes (e.g. a syncdb run, a migration file), and by first calling start(),
  then the relevant actions, and then commit(). This is necessary to allow
  things like circular foreign key references - FKs will only be created once
  commit() is called.
  """

  # Overrideable SQL templates
  sqlCreateTable = "CREATE TABLE %(table)s (%(definition)s)"
  sqlCreateTableUnique = "UNIQUE (%(columns)s)"
  sqlRenameTable = "ALTER TABLE %(oldTable)s RENAME TO %(newTable)s"
  sqlRetablespaceTable = "ALTER TABLE %(table)s SET TABLESPACE %(newTablespace)s"
  sqlDeleteTable = "DROP TABLE %(table)s CASCADE"

  sqlCreateColumn = "ALTER TABLE %(table)s ADD COLUMN %(column)s %(definition)s"
  sqlAlterColumn = "ALTER TABLE %(table)s %(changes)s"
  sqlAlterColumnType = "ALTER COLUMN %(column)s TYPE %(type)s"
  sqlAlterColumnNull = "ALTER COLUMN %(column)s DROP NOT NULL"
  sqlAlterColumnNotNull = "ALTER COLUMN %(column)s SET NOT NULL"
  sqlAlterColumnDefault = "ALTER COLUMN %(column)s SET DEFAULT %(default)s"
  sqlAlterColumnNoDefault = "ALTER COLUMN %(column)s DROP DEFAULT"
  sqlDeleteColumn = "ALTER TABLE %(table)s DROP COLUMN %(column)s CASCADE"
  sqlRenameColumn = "ALTER TABLE %(table)s RENAME COLUMN %(oldColumn)s TO %(newColumn)s"

  sqlCreateCheck = "ALTER TABLE %(table)s ADD CONSTRAINT %(name)s CHECK (%(check)s)"
  sqlDeleteCheck = "ALTER TABLE %(table)s DROP CONSTRAINT %(name)s"

  sqlCreateUnique = "ALTER TABLE %(table)s ADD CONSTRAINT %(name)s UNIQUE (%(columns)s)"
  sqlDeleteUnique = "ALTER TABLE %(table)s DROP CONSTRAINT %(name)s"

  sqlCreateFk = "ALTER TABLE %(table)s ADD CONSTRAINT %(name)s FOREIGN KEY (%(column)s) REFERENCES %(toTable)s (%(toColumn)s) DEFERRABLE INITIALLY DEFERRED"
  sqlCreateInlineFk = None
  sqlDeleteFk = "ALTER TABLE %(table)s DROP CONSTRAINT %(name)s"

  sqlCreateIndex = "CREATE INDEX %(name)s ON %(table)s (%(columns)s)%(extra)s"
  sqlDeleteIndex = "DROP INDEX %(name)s"

  sqlCreatePk = "ALTER TABLE %(table)s ADD CONSTRAINT %(name)s PRIMARY KEY (%(columns)s)"
  sqlDeletePk = "ALTER TABLE %(table)s DROP CONSTRAINT %(name)s"

  def __init__(self, connection, collectSql=False):
    self.connection = connection
    self.collectSql = collectSql
    if self.collectSql:
      self.collectedSql = []

  # State-managing methods

  def __enter__(self):
    self.deferredSql = []
    if self.connection.features.canRollbackDdl:
      self.atomic = atomic(self.connection.alias)
      self.atomic.__enter__()
    return self

  def __exit__(self, excType, excValue, traceback):
    if excType is None:
      for sql in self.deferredSql:
        self.execute(sql)
    if self.connection.features.canRollbackDdl:
      self.atomic.__exit__(excType, excValue, traceback)

  # Core utility functions

  def execute(self, sql, params=[]):
    """
    Executes the given SQL statement, with optional parameters.
    """
    # Log the command we're running, then run it
    logger.debug("%s; (params %r)" % (sql, params))
    if self.collectSql:
      self.collectedSql.append((sql % tuple(map(self.quoteValue, params))) + ";")
    else:
      with self.connection.cursor() as cursor:
        cursor.execute(sql, params)

  def quoteName(self, name):
    return self.connection.ops.quoteName(name)

  # Field <-> database mapping functions

  def columnSql(self, modal, field, includeDefault=False):
    """
    Takes a field and returns its column definition.
    The field must already have had setAttributesFromName called.
    """
    # Get the column's type and use that as the basis of the SQL
    dbParams = field.dbParameters(connection=self.connection)
    sql = dbParams['type']
    params = []
    # Check for fields that aren't actually columns (e.g. M2M)
    if sql is None:
      return None, None
    # Work out nullability
    null = field.null
    # If we were told to include a default value, do so
    defaultValue = self.effectiveDefault(field)
    includeDefault = includeDefault and not self.skipDefault(field)
    if includeDefault and defaultValue is not None:
      if self.connection.features.requiresLiteralDefaults:
        # Some databases can't take defaults as a parameter (oracle)
        # If this is the case, the individual schema backend should
        # implement prepareDefault
        sql += " DEFAULT %s" % self.prepareDefault(defaultValue)
      else:
        sql += " DEFAULT %s"
        params += [defaultValue]
    # Oracle treats the empty string ('') as null, so coerce the null
    # option whenever '' is a possible value.
    if (field.emptyStringsAllowed and not field.primaryKey and
        self.connection.features.interpretsEmptyStringsAsNulls):
      null = True
    if null and not self.connection.features.impliedColumnNull:
      sql += " NULL"
    elif not null:
      sql += " NOT NULL"
    # Primary key/unique outputs
    if field.primaryKey:
      sql += " PRIMARY KEY"
    elif field.unique:
      sql += " UNIQUE"
    # Optionally add the tablespace if it's an implicitly indexed column
    tablespace = field.dbTablespace or modal._meta.dbTablespace
    if tablespace and self.connection.features.supportsTablespaces and field.unique:
      sql += " %s" % self.connection.ops.tablespaceSql(tablespace, inline=True)
    # Return the sql
    return sql, params

  def skipDefault(self, field):
    """
    Some backends don't accept default values for certain columns types
    (i.e. MySQL longtext and longblob).
    """
    return False

  def prepareDefault(self, value):
    """
    Only used for backends which have requiresLiteralDefaults feature
    """
    raise NotImplementedError('subclasses of BaseDatabaseSchemaEditor for backends which have requiresLiteralDefaults must provide a prepareDefault() method')

  def effectiveDefault(self, field):
    """
    Returns a field's effective database default value
    """
    if field.hasDefault():
      default = field.getDefault()
    elif not field.null and field.blank and field.emptyStringsAllowed:
      if field.getInternalType() == "BinaryField":
        default = six.binaryType()
      else:
        default = six.textType()
    else:
      default = None
    # If it's a callable, call it
    if six.callable(default):
      default = default()
    # Run it through the field's getDbPrepSave method so we can send it
    # to the database.
    default = field.getDbPrepSave(default, self.connection)
    return default

  def quoteValue(self, value):
    """
    Returns a quoted version of the value so it's safe to use in an SQL
    string. This is not safe against injection from user code; it is
    intended only for use in making SQL scripts or preparing default values
    for particularly tricky backends (defaults are not user-defined, though,
    so this is safe).
    """
    raise NotImplementedError()

  # Actions

  def createModel(self, modal):
    """
    Takes a modal and creates a table for it in the database.
    Will also create any accompanying indexes or unique constraints.
    """
    # Create column SQL, add FK deferreds if needed
    columnSqls = []
    params = []
    for field in modal._meta.localFields:
      # SQL
      definition, extraParams = self.columnSql(modal, field)
      if definition is None:
        continue
      # Check constraints can go on the column SQL here
      dbParams = field.dbParameters(connection=self.connection)
      if dbParams['check']:
        definition += " CHECK (%s)" % dbParams['check']
      # Autoincrement SQL (for backends with inline variant)
      colTypeSuffix = field.dbTypeSuffix(connection=self.connection)
      if colTypeSuffix:
        definition += " %s" % colTypeSuffix
      params.extend(extraParams)
      # Indexes
      if field.dbIndex and not field.unique:
        self.deferredSql.append(
          self.sqlCreateIndex % {
            "name": self._createIndexName(modal, [field.column], suffix=""),
            "table": self.quoteName(modal._meta.dbTable),
            "columns": self.quoteName(field.column),
            "extra": "",
          }
        )
      # FK
      if field.rel and field.dbConstraint:
        toTable = field.rel.to._meta.dbTable
        toColumn = field.rel.to._meta.getField(field.rel.fieldName).column
        if self.connection.features.supportsForeignKeys:
          self.deferredSql.append(
            self.sqlCreateFk % {
              "name": self._createIndexName(modal, [field.column], suffix="_fk_%s_%s" % (toTable, toColumn)),
              "table": self.quoteName(modal._meta.dbTable),
              "column": self.quoteName(field.column),
              "toTable": self.quoteName(toTable),
              "toColumn": self.quoteName(toColumn),
            }
          )
        elif self.sqlCreateInlineFk:
          definition += " " + self.sqlCreateInlineFk % {
            "toTable": self.quoteName(toTable),
            "toColumn": self.quoteName(toColumn),
          }
      # Add the SQL to our big list
      columnSqls.append("%s %s" % (
        self.quoteName(field.column),
        definition,
      ))
      # Autoincrement SQL (for backends with post table definition variant)
      if field.getInternalType() == "AutoField":
        autoincSql = self.connection.ops.autoincSql(modal._meta.dbTable, field.column)
        if autoincSql:
          self.deferredSql.extend(autoincSql)
    # Add any uniqueTogethers
    for fields in modal._meta.uniqueTogether:
      columns = [modal._meta.getFieldByName(field)[0].column for field in fields]
      columnSqls.append(self.sqlCreateTableUnique % {
        "columns": ", ".join(self.quoteName(column) for column in columns),
      })
    # Make the table
    sql = self.sqlCreateTable % {
      "table": self.quoteName(modal._meta.dbTable),
      "definition": ", ".join(columnSqls)
    }
    self.execute(sql, params)
    # Add any indexTogethers
    for fields in modal._meta.indexTogether:
      columns = [modal._meta.getFieldByName(field)[0].column for field in fields]
      self.execute(self.sqlCreateIndex % {
        "table": self.quoteName(modal._meta.dbTable),
        "name": self._createIndexName(modal, columns, suffix="_idx"),
        "columns": ", ".join(self.quoteName(column) for column in columns),
        "extra": "",
      })
    # Make M2M tables
    for field in modal._meta.localManyToMany:
      if field.rel.through._meta.autoCreated:
        self.createModel(field.rel.through)

  def deleteModel(self, modal):
    """
    Deletes a modal from the database.
    """
    # Handle auto-created intermediary model
    for field in modal._meta.localManyToMany:
      if field.rel.through._meta.autoCreated:
        self.deleteModel(field.rel.through)

    # Delete the table
    self.execute(self.sqlDeleteTable % {
      "table": self.quoteName(modal._meta.dbTable),
    })

  def alterUniqueTogether(self, modal, oldUniqueTogether, newUniqueTogether):
    """
    Deals with a modal changing its uniqueTogether.
    Note: The input uniqueTogethers must be doubly-nested, not the single-
    nested ["foo", "bar"] format.
    """
    olds = set(tuple(fields) for fields in oldUniqueTogether)
    news = set(tuple(fields) for fields in newUniqueTogether)
    # Deleted uniques
    for fields in olds.difference(news):
      columns = [modal._meta.getFieldByName(field)[0].column for field in fields]
      constraintNames = self._constraintNames(modal, columns, unique=True)
      if len(constraintNames) != 1:
        raise ValueError("Found wrong number (%s) of constraints for %s(%s)" % (
          len(constraintNames),
          modal._meta.dbTable,
          ", ".join(columns),
        ))
      self.execute(
        self.sqlDeleteUnique % {
          "table": self.quoteName(modal._meta.dbTable),
          "name": constraintNames[0],
        },
      )
    # Created uniques
    for fields in news.difference(olds):
      columns = [modal._meta.getFieldByName(field)[0].column for field in fields]
      self.execute(self.sqlCreateUnique % {
        "table": self.quoteName(modal._meta.dbTable),
        "name": self._createIndexName(modal, columns, suffix="_uniq"),
        "columns": ", ".join(self.quoteName(column) for column in columns),
      })

  def alterIndexTogether(self, modal, oldIndexTogether, newIndexTogether):
    """
    Deals with a modal changing its indexTogether.
    Note: The input indexTogethers must be doubly-nested, not the single-
    nested ["foo", "bar"] format.
    """
    olds = set(tuple(fields) for fields in oldIndexTogether)
    news = set(tuple(fields) for fields in newIndexTogether)
    # Deleted indexes
    for fields in olds.difference(news):
      columns = [modal._meta.getFieldByName(field)[0].column for field in fields]
      constraintNames = self._constraintNames(modal, list(columns), index=True)
      if len(constraintNames) != 1:
        raise ValueError("Found wrong number (%s) of constraints for %s(%s)" % (
          len(constraintNames),
          modal._meta.dbTable,
          ", ".join(columns),
        ))
      self.execute(
        self.sqlDeleteIndex % {
          "table": self.quoteName(modal._meta.dbTable),
          "name": constraintNames[0],
        },
      )
    # Created indexes
    for fields in news.difference(olds):
      columns = [modal._meta.getFieldByName(field)[0].column for field in fields]
      self.execute(self.sqlCreateIndex % {
        "table": self.quoteName(modal._meta.dbTable),
        "name": self._createIndexName(modal, columns, suffix="_idx"),
        "columns": ", ".join(self.quoteName(column) for column in columns),
        "extra": "",
      })

  def alterDbTable(self, modal, oldDbTable, newDbTable):
    """
    Renames the table a modal points to.
    """
    if oldDbTable == newDbTable:
      return
    self.execute(self.sqlRenameTable % {
      "oldTable": self.quoteName(oldDbTable),
      "newTable": self.quoteName(newDbTable),
    })

  def alterDbTablespace(self, modal, oldDbTablespace, newDbTablespace):
    """
    Moves a modal's table between tablespaces
    """
    self.execute(self.sqlRetablespaceTable % {
      "table": self.quoteName(modal._meta.dbTable),
      "oldTablespace": self.quoteName(oldDbTablespace),
      "newTablespace": self.quoteName(newDbTablespace),
    })

  def addField(self, modal, field):
    """
    Creates a field on a modal.
    Usually involves adding a column, but may involve adding a
    table instead (for M2M fields)
    """
    # Special-case implicit M2M tables
    if isinstance(field, ManyToManyField) and field.rel.through._meta.autoCreated:
      return self.createModel(field.rel.through)
    # Get the column's definition
    definition, params = self.columnSql(modal, field, includeDefault=True)
    # It might not actually have a column behind it
    if definition is None:
      return
    # Check constraints can go on the column SQL here
    dbParams = field.dbParameters(connection=self.connection)
    if dbParams['check']:
      definition += " CHECK (%s)" % dbParams['check']
    # Build the SQL and run it
    sql = self.sqlCreateColumn % {
      "table": self.quoteName(modal._meta.dbTable),
      "column": self.quoteName(field.column),
      "definition": definition,
    }
    self.execute(sql, params)
    # Drop the default if we need to
    # (Theory usually does not use in-database defaults)
    if not self.skipDefault(field) and field.default is not None:
      sql = self.sqlAlterColumn % {
        "table": self.quoteName(modal._meta.dbTable),
        "changes": self.sqlAlterColumnNoDefault % {
          "column": self.quoteName(field.column),
        }
      }
      self.execute(sql)
    # Add an index, if required
    if field.dbIndex and not field.unique:
      self.deferredSql.append(
        self.sqlCreateIndex % {
          "name": self._createIndexName(modal, [field.column], suffix=""),
          "table": self.quoteName(modal._meta.dbTable),
          "columns": self.quoteName(field.column),
          "extra": "",
        }
      )
    # Add any FK constraints later
    if field.rel and self.connection.features.supportsForeignKeys and field.dbConstraint:
      toTable = field.rel.to._meta.dbTable
      toColumn = field.rel.to._meta.getField(field.rel.fieldName).column
      self.deferredSql.append(
        self.sqlCreateFk % {
          "name": self._createIndexName(modal, [field.column], suffix="_fk_%s_%s" % (toTable, toColumn)),
          "table": self.quoteName(modal._meta.dbTable),
          "column": self.quoteName(field.column),
          "toTable": self.quoteName(toTable),
          "toColumn": self.quoteName(toColumn),
        }
      )
    # Reset connection if required
    if self.connection.features.connectionPersistsOldColumns:
      self.connection.close()

  def removeField(self, modal, field):
    """
    Removes a field from a modal. Usually involves deleting a column,
    but for M2Ms may involve deleting a table.
    """
    # Special-case implicit M2M tables
    if isinstance(field, ManyToManyField) and field.rel.through._meta.autoCreated:
      return self.deleteModel(field.rel.through)
    # It might not actually have a column behind it
    if field.dbParameters(connection=self.connection)['type'] is None:
      return
    # Drop any FK constraints, MySQL requires explicit deletion
    if field.rel:
      fkNames = self._constraintNames(modal, [field.column], foreignKey=True)
      for fkName in fkNames:
        self.execute(
          self.sqlDeleteFk % {
            "table": self.quoteName(modal._meta.dbTable),
            "name": fkName,
          }
        )
    # Delete the column
    sql = self.sqlDeleteColumn % {
      "table": self.quoteName(modal._meta.dbTable),
      "column": self.quoteName(field.column),
    }
    self.execute(sql)
    # Reset connection if required
    if self.connection.features.connectionPersistsOldColumns:
      self.connection.close()

  def alterField(self, modal, oldField, newField, strict=False):
    """
    Allows a field's type, uniqueness, nullability, default, column,
    constraints etc. to be modified.
    Requires a copy of the old field as well so we can only perform
    changes that are required.
    If strict is true, raises errors if the old column does not match oldField precisely.
    """
    # Ensure this field is even column-based
    oldDbParams = oldField.dbParameters(connection=self.connection)
    oldType = oldDbParams['type']
    newDbParams = newField.dbParameters(connection=self.connection)
    newType = newDbParams['type']
    if (oldType is None and oldField.rel is None) or (newType is None and newField.rel is None):
      raise ValueError("Cannot alter field %s into %s - they do not properly define dbType (are you using PostGIS 1.5 or badly-written custom fields?)" % (
        oldField,
        newField,
      ))
    elif oldType is None and newType is None and (oldField.rel.through and newField.rel.through and oldField.rel.through._meta.autoCreated and newField.rel.through._meta.autoCreated):
      return self._alterManyToMany(modal, oldField, newField, strict)
    elif oldType is None and newType is None and (oldField.rel.through and newField.rel.through and not oldField.rel.through._meta.autoCreated and not newField.rel.through._meta.autoCreated):
      # Both sides have through model; this is a no-op.
      return
    elif oldType is None or newType is None:
      raise ValueError("Cannot alter field %s into %s - they are not compatible types (you cannot alter to or from M2M fields, or add or remove through= on M2M fields)" % (
        oldField,
        newField,
      ))

    self._alterField(modal, oldField, newField, oldType, newType, oldDbParams, newDbParams, strict)

  def _alterField(self, modal, oldField, newField, oldType, newType, oldDbParams, newDbParams, strict=False):
    """Actually perform a "physical" (non-ManyToMany) field update."""

    # Has unique been removed?
    if oldField.unique and (not newField.unique or (not oldField.primaryKey and newField.primaryKey)):
      # Find the unique constraint for this field
      constraintNames = self._constraintNames(modal, [oldField.column], unique=True)
      if strict and len(constraintNames) != 1:
        raise ValueError("Found wrong number (%s) of unique constraints for %s.%s" % (
          len(constraintNames),
          modal._meta.dbTable,
          oldField.column,
        ))
      for constraintName in constraintNames:
        self.execute(
          self.sqlDeleteUnique % {
            "table": self.quoteName(modal._meta.dbTable),
            "name": constraintName,
          },
        )
    # Drop any FK constraints, we'll remake them later
    fksDropped = set()
    if oldField.rel and oldField.dbConstraint:
      fkNames = self._constraintNames(modal, [oldField.column], foreignKey=True)
      if strict and len(fkNames) != 1:
        raise ValueError("Found wrong number (%s) of foreign key constraints for %s.%s" % (
          len(fkNames),
          modal._meta.dbTable,
          oldField.column,
        ))
      for fkName in fkNames:
        fksDropped.add((oldField.column,))
        self.execute(
          self.sqlDeleteFk % {
            "table": self.quoteName(modal._meta.dbTable),
            "name": fkName,
          }
        )
    # Drop incoming FK constraints if we're a primary key and things are going
    # to change.
    if oldField.primaryKey and newField.primaryKey and oldType != newType:
      for rel in newField.modal._meta.getAllRelatedObjects():
        relFkNames = self._constraintNames(rel.modal, [rel.field.column], foreignKey=True)
        for fkName in relFkNames:
          self.execute(
            self.sqlDeleteFk % {
              "table": self.quoteName(rel.modal._meta.dbTable),
              "name": fkName,
            }
          )
    # Removed an index?
    if oldField.dbIndex and not newField.dbIndex and not oldField.unique and not (not newField.unique and oldField.unique):
      # Find the index for this field
      indexNames = self._constraintNames(modal, [oldField.column], index=True)
      if strict and len(indexNames) != 1:
        raise ValueError("Found wrong number (%s) of indexes for %s.%s" % (
          len(indexNames),
          modal._meta.dbTable,
          oldField.column,
        ))
      for indexName in indexNames:
        self.execute(
          self.sqlDeleteIndex % {
            "table": self.quoteName(modal._meta.dbTable),
            "name": indexName,
          }
        )
    # Change check constraints?
    if oldDbParams['check'] != newDbParams['check'] and oldDbParams['check']:
      constraintNames = self._constraintNames(modal, [oldField.column], check=True)
      if strict and len(constraintNames) != 1:
        raise ValueError("Found wrong number (%s) of check constraints for %s.%s" % (
          len(constraintNames),
          modal._meta.dbTable,
          oldField.column,
        ))
      for constraintName in constraintNames:
        self.execute(
          self.sqlDeleteCheck % {
            "table": self.quoteName(modal._meta.dbTable),
            "name": constraintName,
          }
        )
    # Have they renamed the column?
    if oldField.column != newField.column:
      self.execute(self.sqlRenameColumn % {
        "table": self.quoteName(modal._meta.dbTable),
        "oldColumn": self.quoteName(oldField.column),
        "newColumn": self.quoteName(newField.column),
        "type": newType,
      })
    # Next, start accumulating actions to do
    actions = []
    postActions = []
    # Type change?
    if oldType != newType:
      fragment, otherActions = self._alterColumnTypeSql(modal._meta.dbTable, newField.column, newType)
      actions.append(fragment)
      postActions.extend(otherActions)
    # Default change?
    oldDefault = self.effectiveDefault(oldField)
    newDefault = self.effectiveDefault(newField)
    if oldDefault != newDefault:
      if newDefault is None:
        actions.append((
          self.sqlAlterColumnNoDefault % {
            "column": self.quoteName(newField.column),
          },
          [],
        ))
      else:
        if self.connection.features.requiresLiteralDefaults:
          # Some databases can't take defaults as a parameter (oracle)
          # If this is the case, the individual schema backend should
          # implement prepareDefault
          actions.append((
            self.sqlAlterColumnDefault % {
              "column": self.quoteName(newField.column),
              "default": self.prepareDefault(newDefault),
            },
            [],
          ))
        else:
          actions.append((
            self.sqlAlterColumnDefault % {
              "column": self.quoteName(newField.column),
              "default": "%s",
            },
            [newDefault],
          ))
    # Nullability change?
    if oldField.null != newField.null:
      if newField.null:
        actions.append((
          self.sqlAlterColumnNull % {
            "column": self.quoteName(newField.column),
            "type": newType,
          },
          [],
        ))
      else:
        actions.append((
          self.sqlAlterColumnNotNull % {
            "column": self.quoteName(newField.column),
            "type": newType,
          },
          [],
        ))
    if actions:
      # Combine actions together if we can (e.g. postgres)
      if self.connection.features.supportsCombinedAlters:
        sql, params = tuple(zip(*actions))
        actions = [(", ".join(sql), reduce(operator.add, params))]
      # Apply those actions
      for sql, params in actions:
        self.execute(
          self.sqlAlterColumn % {
            "table": self.quoteName(modal._meta.dbTable),
            "changes": sql,
          },
          params,
        )
    if postActions:
      for sql, params in postActions:
        self.execute(sql, params)
    # Added a unique?
    if not oldField.unique and newField.unique:
      self.execute(
        self.sqlCreateUnique % {
          "table": self.quoteName(modal._meta.dbTable),
          "name": self._createIndexName(modal, [newField.column], suffix="_uniq"),
          "columns": self.quoteName(newField.column),
        }
      )
    # Added an index?
    if not oldField.dbIndex and newField.dbIndex and not newField.unique and not (not oldField.unique and newField.unique):
      self.execute(
        self.sqlCreateIndex % {
          "table": self.quoteName(modal._meta.dbTable),
          "name": self._createIndexName(modal, [newField.column], suffix="_uniq"),
          "columns": self.quoteName(newField.column),
          "extra": "",
        }
      )
    # Type alteration on primary key? Then we need to alter the column
    # referring to us.
    relsToUpdate = []
    if oldField.primaryKey and newField.primaryKey and oldType != newType:
      relsToUpdate.extend(newField.modal._meta.getAllRelatedObjects())
    # Changed to become primary key?
    # Note that we don't detect unsetting of a PK, as we assume another field
    # will always come along and replace it.
    if not oldField.primaryKey and newField.primaryKey:
      # First, drop the old PK
      constraintNames = self._constraintNames(modal, primaryKey=True)
      if strict and len(constraintNames) != 1:
        raise ValueError("Found wrong number (%s) of PK constraints for %s" % (
          len(constraintNames),
          modal._meta.dbTable,
        ))
      for constraintName in constraintNames:
        self.execute(
          self.sqlDeletePk % {
            "table": self.quoteName(modal._meta.dbTable),
            "name": constraintName,
          },
        )
      # Make the new one
      self.execute(
        self.sqlCreatePk % {
          "table": self.quoteName(modal._meta.dbTable),
          "name": self._createIndexName(modal, [newField.column], suffix="_pk"),
          "columns": self.quoteName(newField.column),
        }
      )
      # Update all referencing columns
      relsToUpdate.extend(newField.modal._meta.getAllRelatedObjects())
    # Handle our type alters on the other end of rels from the PK stuff above
    for rel in relsToUpdate:
      relDbParams = rel.field.dbParameters(connection=self.connection)
      relType = relDbParams['type']
      self.execute(
        self.sqlAlterColumn % {
          "table": self.quoteName(rel.modal._meta.dbTable),
          "changes": self.sqlAlterColumnType % {
            "column": self.quoteName(rel.field.column),
            "type": relType,
          }
        }
      )
    # Does it have a foreign key?
    if newField.rel and \
      (fksDropped or (oldField.rel and not oldField.dbConstraint)) and \
      newField.dbConstraint:
      toTable = newField.rel.to._meta.dbTable
      toColumn = newField.rel.getRelatedField().column
      self.execute(
        self.sqlCreateFk % {
          "table": self.quoteName(modal._meta.dbTable),
          "name": self._createIndexName(modal, [newField.column], suffix="_fk_%s_%s" % (toTable, toColumn)),
          "column": self.quoteName(newField.column),
          "toTable": self.quoteName(toTable),
          "toColumn": self.quoteName(toColumn),
        }
      )
    # Rebuild FKs that pointed to us if we previously had to drop them
    if oldField.primaryKey and newField.primaryKey and oldType != newType:
      for rel in newField.modal._meta.getAllRelatedObjects():
        self.execute(
          self.sqlCreateFk % {
            "table": self.quoteName(rel.modal._meta.dbTable),
            "name": self._createIndexName(rel.modal, [rel.field.column], suffix="_fk"),
            "column": self.quoteName(rel.field.column),
            "toTable": self.quoteName(modal._meta.dbTable),
            "toColumn": self.quoteName(newField.column),
          }
        )
    # Does it have check constraints we need to add?
    if oldDbParams['check'] != newDbParams['check'] and newDbParams['check']:
      self.execute(
        self.sqlCreateCheck % {
          "table": self.quoteName(modal._meta.dbTable),
          "name": self._createIndexName(modal, [newField.column], suffix="_check"),
          "column": self.quoteName(newField.column),
          "check": newDbParams['check'],
        }
      )
    # Drop the default if we need to
    # (Theory usually does not use in-database defaults)
    if not self.skipDefault(newField) and newField.default is not None:
      sql = self.sqlAlterColumn % {
        "table": self.quoteName(modal._meta.dbTable),
        "changes": self.sqlAlterColumnNoDefault % {
          "column": self.quoteName(newField.column),
        }
      }
      self.execute(sql)
    # Reset connection if required
    if self.connection.features.connectionPersistsOldColumns:
      self.connection.close()

  def _alterColumnTypeSql(self, table, column, type):
    """
    Hook to specialize column type alteration for different backends,
    for cases when a creation type is different to an alteration type
    (e.g. SERIAL in PostgreSQL, PostGIS fields).

    Should return two things; an SQL fragment of (sql, params) to insert
    into an ALTER TABLE statement, and a list of extra (sql, params) tuples
    to run once the field is altered.
    """
    return (
      (
        self.sqlAlterColumnType % {
          "column": self.quoteName(column),
          "type": type,
        },
        [],
      ),
      [],
    )

  def _alterManyToMany(self, modal, oldField, newField, strict):
    """
    Alters M2Ms to repoint their to= endpoints.
    """
    # Rename the through table
    if oldField.rel.through._meta.dbTable != newField.rel.through._meta.dbTable:
      self.alterDbTable(oldField.rel.through, oldField.rel.through._meta.dbTable, newField.rel.through._meta.dbTable)
    # Repoint the FK to the other side
    self.alterField(
      newField.rel.through,
      # We need the field that points to the target modal, so we can tell alterField to change it -
      # this is m2mReverseFieldName() (as opposed to m2mFieldName, which points to our modal)
      oldField.rel.through._meta.getFieldByName(oldField.m2mReverseFieldName())[0],
      newField.rel.through._meta.getFieldByName(newField.m2mReverseFieldName())[0],
    )

  def _createIndexName(self, modal, columnNames, suffix=""):
    """
    Generates a unique name for an index/unique constraint.
    """
    # If there is just one column in the index, use a default algorithm from Theory
    if len(columnNames) == 1 and not suffix:
      return truncateName(
        '%s_%s' % (modal._meta.dbTable, BaseDatabaseCreation._digest(columnNames[0])),
        self.connection.ops.maxNameLength()
      )
    # Else generate the name for the index using a different algorithm
    tableName = modal._meta.dbTable.replace('"', '').replace('.', '_')
    indexUniqueName = '_%x' % abs(hash((tableName, ','.join(columnNames))))
    maxLength = self.connection.ops.maxNameLength() or 200
    # If the index name is too long, truncate it
    indexName = ('%s_%s%s%s' % (tableName, columnNames[0], indexUniqueName, suffix)).replace('"', '').replace('.', '_')
    if len(indexName) > maxLength:
      part = ('_%s%s%s' % (columnNames[0], indexUniqueName, suffix))
      indexName = '%s%s' % (tableName[:(maxLength - len(part))], part)
    # It shouldn't start with an underscore (Oracle hates this)
    if indexName[0] == "_":
      indexName = indexName[1:]
    # If it's STILL too long, just hash it down
    if len(indexName) > maxLength:
      indexName = hashlib.md5(forceBytes(indexName)).hexdigest()[:maxLength]
    # It can't start with a number on Oracle, so prepend D if we need to
    if indexName[0].isdigit():
      indexName = "D%s" % indexName[:-1]
    return indexName

  def _constraintNames(self, modal, columnNames=None, unique=None, primaryKey=None, index=None, foreignKey=None, check=None):
    """
    Returns all constraint names matching the columns and conditions
    """
    columnNames = list(columnNames) if columnNames else None
    with self.connection.cursor() as cursor:
      constraints = self.connection.introspection.getConstraints(cursor, modal._meta.dbTable)
    result = []
    for name, infodict in constraints.items():
      if columnNames is None or columnNames == infodict['columns']:
        if unique is not None and infodict['unique'] != unique:
          continue
        if primaryKey is not None and infodict['primaryKey'] != primaryKey:
          continue
        if index is not None and infodict['index'] != index:
          continue
        if check is not None and infodict['check'] != check:
          continue
        if foreignKey is not None and not infodict['foreignKey']:
          continue
        result.append(name)
    return result
