import codecs
import copy
from decimal import Decimal
from theory.utils import six
from theory.apps.registry import Apps
from theory.db.backends.schema import BaseDatabaseSchemaEditor
from theory.db.model.fields.related import ManyToManyField


class DatabaseSchemaEditor(BaseDatabaseSchemaEditor):

  sqlDeleteTable = "DROP TABLE %(table)s"
  sqlCreateInlineFk = "REFERENCES %(toTable)s (%(toColumn)s)"

  def quoteValue(self, value):
    # Inner import to allow nice failure for backend if not present
    import _sqlite3
    try:
      value = _sqlite3.adapt(value)
    except _sqlite3.ProgrammingError:
      pass
    # Manual emulation of SQLite parameter quoting
    if isinstance(value, type(True)):
      return str(int(value))
    elif isinstance(value, (Decimal, float)):
      return str(value)
    elif isinstance(value, six.integerTypes):
      return str(value)
    elif isinstance(value, six.stringTypes):
      return "'%s'" % six.textType(value).replace("\'", "\'\'")
    elif value is None:
      return "NULL"
    elif isinstance(value, (bytes, bytearray, six.memoryview)):
      # Bytes are only allowed for BLOB fields, encoded as string
      # literals containing hexadecimal data and preceded by a single "X"
      # character:
      # value = b'\x01\x02' => valueHex = b'0102' => return X'0102'
      value = bytes(value)
      hexEncoder = codecs.getencoder('hexCodec')
      valueHex, _length = hexEncoder(value)
      # Use 'ascii' encoding for b'01' => '01', no need to use forceText here.
      return "X'%s'" % valueHex.decode('ascii')
    else:
      raise ValueError("Cannot quote parameter value %r of type %s" % (value, type(value)))

  def _remakeTable(self, modal, createFields=[], deleteFields=[], alterFields=[], overrideUniques=None):
    """
    Shortcut to transform a modal from oldModel into newModel
    """
    # Work out the new fields dict / mapping
    body = dict((f.name, f) for f in modal._meta.localFields)
    # Since mapping might mix column names and default values,
    # its values must be already quoted.
    mapping = dict((f.column, self.quoteName(f.column)) for f in modal._meta.localFields)
    # This maps field names (not columns) for things like uniqueTogether
    renameMapping = {}
    # If any of the new or altered fields is introducing a new PK,
    # remove the old one
    restorePkField = None
    if any(f.primaryKey for f in createFields) or any(n.primaryKey for o, n in alterFields):
      for name, field in list(body.items()):
        if field.primaryKey:
          field.primaryKey = False
          restorePkField = field
          if field.autoCreated:
            del body[name]
            del mapping[field.column]
    # Add in any created fields
    for field in createFields:
      body[field.name] = field
      # If there's a default, insert it into the copy map
      if field.hasDefault():
        mapping[field.column] = self.quoteValue(
          self.effectiveDefault(field)
        )
    # Add in any altered fields
    for (oldField, newField) in alterFields:
      del body[oldField.name]
      del mapping[oldField.column]
      body[newField.name] = newField
      mapping[newField.column] = self.quoteName(oldField.column)
      renameMapping[oldField.name] = newField.name
    # Remove any deleted fields
    for field in deleteFields:
      del body[field.name]
      del mapping[field.column]
      # Remove any implicit M2M tables
      if isinstance(field, ManyToManyField) and field.rel.through._meta.autoCreated:
        return self.deleteModel(field.rel.through)
    # Work inside a new app registry
    apps = Apps()

    # Provide isolated instances of the fields to the new modal body
    # Instantiating the new modal with an alternate dbTable will alter
    # the internal references of some of the provided fields.
    body = copy.deepcopy(body)

    # Work out the new value of uniqueTogether, taking renames into
    # account
    if overrideUniques is None:
      overrideUniques = [
        [renameMapping.get(n, n) for n in unique]
        for unique in modal._meta.uniqueTogether
      ]

    # Construct a new modal for the new state
    metaContents = {
      'appLabel': modal._meta.appLabel,
      'dbTable': modal._meta.dbTable + "__new",
      'uniqueTogether': overrideUniques,
      'apps': apps,
    }
    meta = type("Meta", tuple(), metaContents)
    body['Meta'] = meta
    body['__module__'] = modal.__module__

    tempModel = type(modal._meta.objectName, modal.__bases__, body)
    # Create a new table with that format. We remove things from the
    # deferred SQL that match our table name, too
    self.deferredSql = [x for x in self.deferredSql if modal._meta.dbTable not in x]
    self.createModel(tempModel)
    # Copy data from the old table
    fieldMaps = list(mapping.items())
    self.execute("INSERT INTO %s (%s) SELECT %s FROM %s" % (
      self.quoteName(tempModel._meta.dbTable),
      ', '.join(self.quoteName(x) for x, y in fieldMaps),
      ', '.join(y for x, y in fieldMaps),
      self.quoteName(modal._meta.dbTable),
    ))
    # Delete the old table
    self.deleteModel(modal, handleAutom2m=False)
    # Rename the new to the old
    self.alterDbTable(tempModel, tempModel._meta.dbTable, modal._meta.dbTable)
    # Run deferred SQL on correct table
    for sql in self.deferredSql:
      self.execute(sql.replace(tempModel._meta.dbTable, modal._meta.dbTable))
    self.deferredSql = []
    # Fix any PK-removed field
    if restorePkField:
      restorePkField.primaryKey = True

  def deleteModel(self, modal, handleAutom2m=True):
    if handleAutom2m:
      super(DatabaseSchemaEditor, self).deleteModel(modal)
    else:
      # Delete the table (and only that)
      self.execute(self.sqlDeleteTable % {
        "table": self.quoteName(modal._meta.dbTable),
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
    self._remakeTable(modal, createFields=[field])

  def removeField(self, modal, field):
    """
    Removes a field from a modal. Usually involves deleting a column,
    but for M2Ms may involve deleting a table.
    """
    # M2M fields are a special case
    if isinstance(field, ManyToManyField):
      # For implicit M2M tables, delete the auto-created table
      if field.rel.through._meta.autoCreated:
        self.deleteModel(field.rel.through)
      # For explicit "through" M2M fields, do nothing
    # For everything else, remake.
    else:
      # It might not actually have a column behind it
      if field.dbParameters(connection=self.connection)['type'] is None:
        return
      self._remakeTable(modal, deleteFields=[field])

  def _alterField(self, modal, oldField, newField, oldType, newType, oldDbParams, newDbParams, strict=False):
    """Actually perform a "physical" (non-ManyToMany) field update."""
    # Alter by remaking table
    self._remakeTable(modal, alterFields=[(oldField, newField)])

  def alterUniqueTogether(self, modal, oldUniqueTogether, newUniqueTogether):
    """
    Deals with a modal changing its uniqueTogether.
    Note: The input uniqueTogethers must be doubly-nested, not the single-
    nested ["foo", "bar"] format.
    """
    self._remakeTable(modal, overrideUniques=newUniqueTogether)

  def _alterManyToMany(self, modal, oldField, newField, strict):
    """
    Alters M2Ms to repoint their to= endpoints.
    """
    if oldField.rel.through._meta.dbTable == newField.rel.through._meta.dbTable:
      # The field name didn't change, but some options did; we have to propagate this altering.
      self._remakeTable(
        oldField.rel.through,
        alterFields=[(
          # We need the field that points to the target modal, so we can tell alterField to change it -
          # this is m2mReverseFieldName() (as opposed to m2mFieldName, which points to our modal)
          oldField.rel.through._meta.getFieldByName(oldField.m2mReverseFieldName())[0],
          newField.rel.through._meta.getFieldByName(newField.m2mReverseFieldName())[0],
        )],
        overrideUniques=(newField.m2mFieldName(), newField.m2mReverseFieldName()),
      )
      return

    # Make a new through table
    self.createModel(newField.rel.through)
    # Copy the data across
    self.execute("INSERT INTO %s (%s) SELECT %s FROM %s" % (
      self.quoteName(newField.rel.through._meta.dbTable),
      ', '.join([
        "id",
        newField.m2mColumnName(),
        newField.m2mReverseName(),
      ]),
      ', '.join([
        "id",
        oldField.m2mColumnName(),
        oldField.m2mReverseName(),
      ]),
      self.quoteName(oldField.rel.through._meta.dbTable),
    ))
    # Delete the old through table
    self.deleteModel(oldField.rel.through)
