from theory.core import checks
from theory.db.backends import BaseDatabaseValidation


class DatabaseValidation(BaseDatabaseValidation):
  def checkField(self, field, **kwargs):
    """
    MySQL has the following field length restriction:
    No character (varchar) fields can have a length exceeding 255
    characters if they have a unique index on them.
    """
    from theory.db import connection

    errors = super(DatabaseValidation, self).checkField(field, **kwargs)

    # Ignore any related fields.
    if getattr(field, 'rel', None) is None:
      fieldType = field.dbType(connection)

      if (fieldType.startswith('varchar')  # Look for CharFields...
          and field.unique  # ... that are unique
          and (field.maxLength is None or int(field.maxLength) > 255)):
        errors.append(
          checks.Error(
            ('MySQL does not allow unique CharFields to have a maxLength > 255.'),
            hint=None,
            obj=field,
            id='mysql.E001',
          )
        )
    return errors
