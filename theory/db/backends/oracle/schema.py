import copy
import datetime
import binascii

from theory.utils import six
from theory.utils.text import forceText
from theory.db.backends.schema import BaseDatabaseSchemaEditor
from theory.db.utils import DatabaseError


class DatabaseSchemaEditor(BaseDatabaseSchemaEditor):

  sqlCreateColumn = "ALTER TABLE %(table)s ADD %(column)s %(definition)s"
  sqlAlterColumnType = "MODIFY %(column)s %(type)s"
  sqlAlterColumnNull = "MODIFY %(column)s NULL"
  sqlAlterColumnNotNull = "MODIFY %(column)s NOT NULL"
  sqlAlterColumnDefault = "MODIFY %(column)s DEFAULT %(default)s"
  sqlAlterColumnNoDefault = "MODIFY %(column)s DEFAULT NULL"
  sqlDeleteColumn = "ALTER TABLE %(table)s DROP COLUMN %(column)s"
  sqlDeleteTable = "DROP TABLE %(table)s CASCADE CONSTRAINTS"

  def quoteValue(self, value):
    if isinstance(value, (datetime.date, datetime.time, datetime.datetime)):
      return "'%s'" % value
    elif isinstance(value, six.stringTypes):
      return "'%s'" % six.textType(value).replace("\'", "\'\'")
    elif isinstance(value, six.bufferTypes):
      return "'%s'" % forceText(binascii.hexlify(value))
    elif isinstance(value, bool):
      return "1" if value else "0"
    else:
      return str(value)

  def deleteModel(self, modal):
    # Run superclass action
    super(DatabaseSchemaEditor, self).deleteModel(modal)
    # Clean up any autoincrement trigger
    self.execute("""
      DECLARE
        i INTEGER;
      BEGIN
        SELECT COUNT(*) INTO i FROM USER_CATALOG
          WHERE TABLE_NAME = '%(sqName)s' AND TABLE_TYPE = 'SEQUENCE';
        IF i = 1 THEN
          EXECUTE IMMEDIATE 'DROP SEQUENCE "%(sqName)s"';
        END IF;
      END;
    /""" % {'sqName': self.connection.ops._getSequenceName(modal._meta.dbTable)})

  def alterField(self, modal, oldField, newField, strict=False):
    try:
      # Run superclass action
      super(DatabaseSchemaEditor, self).alterField(modal, oldField, newField, strict)
    except DatabaseError as e:
      description = str(e)
      # If we're changing to/from LOB fields, we need to do a
      # SQLite-ish workaround
      if 'ORA-22858' in description or 'ORA-22859' in description:
        self._alterFieldLobWorkaround(modal, oldField, newField)
      else:
        raise

  def _alterFieldLobWorkaround(self, modal, oldField, newField):
    """
    Oracle refuses to change a column type from/to LOB to/from a regular
    column. In Theory, this shows up when the field is changed from/to
    a TextField.
    What we need to do instead is:
    - Add the desired field with a temporary name
    - Update the table to transfer values from old to new
    - Drop old column
    - Rename the new column
    """
    # Make a new field that's like the new one but with a temporary
    # column name.
    newTempField = copy.deepcopy(newField)
    newTempField.column = self._generateTempName(newField.column)
    # Add it
    self.addField(modal, newTempField)
    # Transfer values across
    self.execute("UPDATE %s set %s=%s" % (
      self.quoteName(modal._meta.dbTable),
      self.quoteName(newTempField.column),
      self.quoteName(oldField.column),
    ))
    # Drop the old field
    self.removeField(modal, oldField)
    # Rename the new field
    self.alterField(modal, newTempField, newField)
    # Close the connection to force cx_Oracle to get column types right
    # on a new cursor
    self.connection.close()

  def normalizeName(self, name):
    """
    Get the properly shortened and uppercased identifier as returned by quoteName(), but without the actual quotes.
    """
    nn = self.quoteName(name)
    if nn[0] == '"' and nn[-1] == '"':
      nn = nn[1:-1]
    return nn

  def _generateTempName(self, forName):
    """
    Generates temporary names for workarounds that need temp columns
    """
    suffix = hex(hash(forName)).upper()[1:]
    return self.normalizeName(forName + "_" + suffix)

  def prepareDefault(self, value):
    return self.quoteValue(value)
