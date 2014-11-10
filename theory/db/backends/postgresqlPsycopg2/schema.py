from theory.db.backends.schema import BaseDatabaseSchemaEditor


class DatabaseSchemaEditor(BaseDatabaseSchemaEditor):

  sqlCreateSequence = "CREATE SEQUENCE %(sequence)s"
  sqlDeleteSequence = "DROP SEQUENCE IF EXISTS %(sequence)s CASCADE"
  sqlSetSequenceMax = "SELECT setval('%(sequence)s', MAX(%(column)s)) FROM %(table)s"

  def quoteValue(self, value):
    # Inner import so backend fails nicely if it's not present
    import psycopg2
    return psycopg2.extensions.adapt(value)

  def _alterColumnTypeSql(self, table, column, type):
    """
    Makes ALTER TYPE with SERIAL make sense.
    """
    if type.lower() == "serial":
      sequenceName = "%s_%sSeq" % (table, column)
      return (
        (
          self.sqlAlterColumnType % {
            "column": self.quoteName(column),
            "type": "integer",
          },
          [],
        ),
        [
          (
            self.sqlDeleteSequence % {
              "sequence": sequenceName,
            },
            [],
          ),
          (
            self.sqlCreateSequence % {
              "sequence": sequenceName,
            },
            [],
          ),
          (
            self.sqlAlterColumn % {
              "table": table,
              "changes": self.sqlAlterColumnDefault % {
                "column": column,
                "default": "nextval('%s')" % sequenceName,
              }
            },
            [],
          ),
          (
            self.sqlSetSequenceMax % {
              "table": table,
              "column": column,
              "sequence": sequenceName,
            },
            [],
          ),
        ],
      )
    else:
      return super(DatabaseSchemaEditor, self)._alterColumnTypeSql(table, column, type)
