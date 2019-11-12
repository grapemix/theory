import copy

from theory.contrib.postgres.validator import ArrayMinLengthValidator, ArrayMaxLengthValidator
from theory.core.exceptions import ValidationError
from theory.gui.field import Field, TextField
from theory.utils.safestring import markSafe
from theory.utils import six
from theory.utils.translation import stringConcat, ugettextLazy as _


class SimpleArrayField(TextField):
  defaultErrorMessages = {
    'itemInvalid': _('Item %(nth)s in the array did not validate: '),
  }

  def __init__(self, baseField, delimiter=',', maxLength=None, minLength=None, *args, **kwargs):
    self.baseField = baseField
    self.delimiter = delimiter
    super(SimpleArrayField, self).__init__(*args, **kwargs)
    if minLength is not None:
      self.minLength = minLength
      self.validators.append(ArrayMinLengthValidator(int(minLength)))
    if maxLength is not None:
      self.maxLength = maxLength
      self.validators.append(ArrayMaxLengthValidator(int(maxLength)))

  def prepareValue(self, value):
    if isinstance(value, list):
      return self.delimiter.join([six.textType(self.baseField.prepareValue(v)) for v in value])
    return value

  def toPython(self, value):
    if value:
      items = value.split(self.delimiter)
    else:
      items = []
    errors = []
    values = []
    for i, item in enumerate(items):
      try:
        values.append(self.baseField.toPython(item))
      except ValidationError as e:
        for error in e.errorList:
          errors.append(ValidationError(
            stringConcat(self.errorMessages['itemInvalid'], error.message),
            code='itemInvalid',
            params={'nth': i},
          ))
    if errors:
      raise ValidationError(errors)
    return values

  def validate(self, value):
    super(SimpleArrayField, self).validate(value)
    errors = []
    for i, item in enumerate(value):
      try:
        self.baseField.validate(item)
      except ValidationError as e:
        for error in e.errorList:
          errors.append(ValidationError(
            stringConcat(self.errorMessages['itemInvalid'], error.message),
            code='itemInvalid',
            params={'nth': i},
          ))
    if errors:
      raise ValidationError(errors)

  def runValidators(self, value):
    super(SimpleArrayField, self).runValidators(value)
    errors = []
    for i, item in enumerate(value):
      try:
        self.baseField.runValidators(item)
      except ValidationError as e:
        for error in e.errorList:
          errors.append(ValidationError(
            stringConcat(self.errorMessages['itemInvalid'], error.message),
            code='itemInvalid',
            params={'nth': i},
          ))
    if errors:
      raise ValidationError(errors)


class SplitArrayField(Field):
  defaultErrorMessages = {
    'itemInvalid': _('Item %(nth)s in the array did not validate: '),
  }
  widget = "theory.contrib.postgres.widget.SplitArrayWidget"

  def __init__(self, baseField, size, removeTrailingNulls=False, **kwargs):
    self.baseField = baseField
    self.size = size
    self.removeTrailingNulls = removeTrailingNulls

    super(SplitArrayField, self).__init__(**kwargs)

  def widget_attrs(self, widget):
    attrs = super().widget_attrs(widget)
    attrs.update({"size": self.size})

    return attrs
  def clean(self, value):
    cleanedData = []
    errors = []
    if not any(value) and self.required:
      raise ValidationError(self.errorMessages['required'])
    maxSize = max(self.size, len(value))
    for i in range(maxSize):
      item = value[i]
      try:
        cleanedData.append(self.baseField.clean(item))
        errors.append(None)
      except ValidationError as error:
        errors.append(ValidationError(
          stringConcat(self.errorMessages['itemInvalid'], error.message),
          code='itemInvalid',
          params={'nth': i},
        ))
        cleanedData.append(None)
    if self.removeTrailingNulls:
      nullIndex = None
      for i, value in reversed(list(enumerate(cleanedData))):
        if value in self.baseField.emptyValues:
          nullIndex = i
        else:
          break
      if nullIndex:
        cleanedData = cleanedData[:nullIndex]
        errors = errors[:nullIndex]
    errors = list(filter(None, errors))
    if errors:
      raise ValidationError(errors)
    return cleanedData
