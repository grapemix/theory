import json

#from theory.contrib.postgres.forms import SimpleArrayField
from theory.gui.common.baseField import ListField
from theory.contrib.postgres.validator import ArrayMaxLengthValidator
from theory.core import checks, exceptions
from theory.db.model import Field, Lookup, Transform, IntegerField
from theory.utils import six
from theory.utils.translation import stringConcat, ugettextLazy as _


__all__ = ['ArrayField']


class AttributeSetter(object):
  def __init__(self, name, value):
    setattr(self, name, value)


class ArrayField(Field):
  emptyStringsAllowed = False
  defaultErrorMessages = {
    'itemInvalid': _('Item %(nth)s in the array did not validate: '),
    'nestedArrayMismatch': _('Nested arrays must have the same length.'),
  }

  def __init__(self, baseField, size=None, **kwargs):
    self.baseField = baseField
    self.size = size
    if self.size:
      self.defaultValidators = self.defaultValidators[:]
      self.defaultValidators.append(ArrayMaxLengthValidator(self.size))
    super(ArrayField, self).__init__(**kwargs)

  def check(self, **kwargs):
    errors = super(ArrayField, self).check(**kwargs)
    if self.baseField.rel:
      errors.append(
        checks.Error(
          'Base field for array cannot be a related field.',
          hint=None,
          obj=self,
          id='postgres.E002'
        )
      )
    else:
      # Remove the field name checks as they are not needed here.
      baseErrors = self.baseField.check()
      if baseErrors:
        messages = '\n    '.join('%s (%s)' % (error.msg, error.id) for error in baseErrors)
        errors.append(
          checks.Error(
            'Base field for array has errors:\n    %s' % messages,
            hint=None,
            obj=self,
            id='postgres.E001'
          )
        )
    return errors

  def setAttributesFromName(self, name):
    super(ArrayField, self).setAttributesFromName(name)
    self.baseField.setAttributesFromName(name)

  @property
  def description(self):
    return 'Array of %s' % self.baseField.description

  def dbType(self, connection):
    size = self.size or ''
    return '%s[%s]' % (self.baseField.dbType(connection), size)

  def getPrepValue(self, value):
    if isinstance(value, list) or isinstance(value, tuple):
      return [self.baseField.getPrepValue(i) for i in value]
    return value

  def getDbPrepLookup(self, lookupType, value, connection, prepared=False):
    if lookupType == 'contains':
      return [self.getPrepValue(value)]
    return super(ArrayField, self).getDbPrepLookup(lookupType, value,
        connection, prepared=False)

  def deconstruct(self):
    name, path, args, kwargs = super(ArrayField, self).deconstruct()
    path = 'theory.contrib.postgres.fields.ArrayField'
    args.insert(0, self.baseField)
    kwargs['size'] = self.size
    return name, path, args, kwargs

  def toPython(self, value):
    if isinstance(value, six.stringTypes):
      # Assume we're deserializing
      vals = json.loads(value)
      value = [self.baseField.toPython(val) for val in vals]
    return value

  def getDefault(self):
    """Overridden from the default to prevent string-mangling."""
    if self.hasDefault():
      if callable(self.default):
        return self.default()
      return self.default
    return ''

  def valueToString(self, obj):
    values = []
    vals = self._getValFromObj(obj)
    baseField = self.baseField

    for val in vals:
      obj = AttributeSetter(baseField.attname, val)
      values.append(baseField.valueToString(obj))
    return json.dumps(values)

  def getTransform(self, name):
    transform = super(ArrayField, self).getTransform(name)
    if transform:
      return transform
    try:
      index = int(name)
    except ValueError:
      pass
    else:
      index += 1  # postgres uses 1-indexing
      return IndexTransformFactory(index, self.baseField)
    try:
      start, end = name.split('_')
      start = int(start) + 1
      end = int(end)  # don't add one here because postgres slices are weird
    except ValueError:
      pass
    else:
      return SliceTransformFactory(start, end)

  def validate(self, value, modalInstance):
    super(ArrayField, self).validate(value, modalInstance)
    for i, part in enumerate(value):
      try:
        self.baseField.validate(part, modalInstance)
      except exceptions.ValidationError as e:
        raise exceptions.ValidationError(
          stringConcat(self.errorMessages['itemInvalid'], e.message),
          code='itemInvalid',
          params={'nth': i},
        )
    if isinstance(self.baseField, ArrayField):
      if len({len(i) for i in value}) > 1:
        raise exceptions.ValidationError(
          self.errorMessages['nestedArrayMismatch'],
          code='nestedArrayMismatch',
        )

  def formfield(self, **kwargs):
    defaults = {
      'formClass': ListField,
      #'formClass': SimpleArrayField,
      #'baseField': self.baseField.formfield(),
      'field': self.baseField.formfield(),
      'maxLength': self.size,
    }
    defaults.update(kwargs)
    return super(ArrayField, self).formfield(**defaults)


class ArrayContainsLookup(Lookup):
  lookupName = 'contains'

  def asSql(self, qn, connection):
    lhs, lhsParams = self.processLhs(qn, connection)
    rhs, rhsParams = self.processRhs(qn, connection)
    params = lhsParams + rhsParams
    typeCast = self.lhs.source.dbType(connection)
    return '%s @> %s::%s' % (lhs, rhs, typeCast), params


ArrayField.registerLookup(ArrayContainsLookup)


class ArrayContainedByLookup(Lookup):
  lookupName = 'containedBy'

  def asSql(self, qn, connection):
    lhs, lhsParams = self.processLhs(qn, connection)
    rhs, rhsParams = self.processRhs(qn, connection)
    params = lhsParams + rhsParams
    return '%s <@ %s' % (lhs, rhs), params


ArrayField.registerLookup(ArrayContainedByLookup)


class ArrayOverlapLookup(Lookup):
  lookupName = 'overlap'

  def asSql(self, qn, connection):
    lhs, lhsParams = self.processLhs(qn, connection)
    rhs, rhsParams = self.processRhs(qn, connection)
    params = lhsParams + rhsParams
    return '%s && %s' % (lhs, rhs), params


ArrayField.registerLookup(ArrayOverlapLookup)


class ArrayLenTransform(Transform):
  lookupName = 'len'

  @property
  def outputField(self):
    return IntegerField()

  def asSql(self, qn, connection):
    lhs, params = qn.compile(self.lhs)
    return 'array_length(%s, 1)' % lhs, params


ArrayField.registerLookup(ArrayLenTransform)


class IndexTransform(Transform):

  def __init__(self, index, baseField, *args, **kwargs):
    super(IndexTransform, self).__init__(*args, **kwargs)
    self.index = index
    self.baseField = baseField

  def asSql(self, qn, connection):
    lhs, params = qn.compile(self.lhs)
    return '%s[%s]' % (lhs, self.index), params

  @property
  def outputField(self):
    return self.baseField


class IndexTransformFactory(object):

  def __init__(self, index, baseField):
    self.index = index
    self.baseField = baseField

  def __call__(self, *args, **kwargs):
    return IndexTransform(self.index, self.baseField, *args, **kwargs)


class SliceTransform(Transform):

  def __init__(self, start, end, *args, **kwargs):
    super(SliceTransform, self).__init__(*args, **kwargs)
    self.start = start
    self.end = end

  def asSql(self, qn, connection):
    lhs, params = qn.compile(self.lhs)
    return '%s[%s:%s]' % (lhs, self.start, self.end), params


class SliceTransformFactory(object):

  def __init__(self, start, end):
    self.start = start
    self.end = end

  def __call__(self, *args, **kwargs):
    return SliceTransform(self.start, self.end, *args, **kwargs)
