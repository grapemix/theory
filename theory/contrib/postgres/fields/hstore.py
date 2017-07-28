import json
import sys

from theory.contrib.postgres import form, lookup
from theory.contrib.postgres.fields.array import ArrayField
from theory.core import exceptions
from theory.db.model import Field, TextField, Transform
from theory.gui.common.baseField import TextField
from theory.utils import six
from theory.utils.translation import ugettextLazy as _

__all__ = ['HStoreField']


class HStoreField(Field):
  emptyStringsAllowed = False
  description = _('Map of strings to strings')
  defaultErrorMessages = {
      'not_a_string': _('The value of "%(key)s" is not a string.'),
  }

  def __init__(self, size=None, **kwargs):
    self.size = size
    if self.size:
      self.defaultValidators = self.defaultValidators[:]
      self.defaultValidators.append(ArrayMaxLengthValidator(self.size))
    super(HStoreField, self).__init__(**kwargs)

  def dbType(self, connection):
    return 'hstore'

  def getTransform(self, name):
    transform = super(HStoreField, self).getTransform(name)
    if transform:
      return transform
    return KeyTransformFactory(name)

  def validate(self, value, modelInstance):
    super(HStoreField, self).validate(value, modelInstance)
    for key, val in value.items():
      if not isinstance(val, six.stringTypes):
        raise exceptions.ValidationError(
            self.error_messages['not_a_string'],
            code='not_a_string',
            params={'key': key},
        )

  def toPython(self, value):
    if isinstance(value, six.stringTypes):
      if value == "":
        #return {}
        return None
      value = json.loads(value)
    return value

  def valueToString(self, obj):
    value = self._getValFromObj(obj)
    return json.dumps(value)

  #def formfield(self, **kwargs):
  #  defaults = {
  #      'form_class': forms.HStoreField,
  #  }
  #  defaults.update(kwargs)
  #  return super(HStoreField, self).formfield(**defaults)
  def formfield(self, **kwargs):
    if self.size is None:
      # maxLength has be an int according to field. However, postgres will
      # complain during table creation if maxint is used.
      maxLength = sys.maxint
    else:
      maxLength = self.size
    defaults = {
        'keyField': TextField(),
        'valueField': TextField(),
        'formClass': form.HStoreField,
        'maxLength': maxLength,
    }
    defaults.update(kwargs)
    return super(HStoreField, self).formfield(**defaults)

  def clean(self, value, isEmptyForgiven=False):
    super(HStoreField, self).clean(self.toPython(value), isEmptyForgiven)
    return self.toPython(value)

HStoreField.registerLookup(lookup.DataContains)
HStoreField.registerLookup(lookup.ContainedBy)


@HStoreField.registerLookup
class HasKeyLookup(lookup.PostgresSimpleLookup):
  lookupName = 'has_key'
  operator = '?'


@HStoreField.registerLookup
class HasKeysLookup(lookup.PostgresSimpleLookup):
  lookupName = 'has_keys'
  operator = '?&'


class KeyTransform(Transform):
  output_field = TextField()

  def __init__(self, keyName, *args, **kwargs):
    super(KeyTransform, self).__init__(*args, **kwargs)
    self.keyName = keyName

  def asSql(self, compiler, connection):
    lhs, params = compiler.compile(self.lhs)
    return "%s -> '%s'" % (lhs, self.keyName), params


class KeyTransformFactory(object):

  def __init__(self, keyName):
    self.keyName = keyName

  def __call__(self, *args, **kwargs):
    return KeyTransform(self.keyName, *args, **kwargs)


@HStoreField.registerLookup
class KeysTransform(lookup.FunctionTransform):
  lookupName = 'keys'
  function = 'akeys'
  outputField = ArrayField(TextField())


@HStoreField.registerLookup
class ValuesTransform(lookup.FunctionTransform):
  lookupName = 'values'
  function = 'avals'
  outputField = ArrayField(TextField())
