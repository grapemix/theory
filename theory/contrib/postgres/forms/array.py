import copy

from theory.contrib.postgres.validators import ArrayMinLengthValidator, ArrayMaxLengthValidator
from theory.core.exceptions import ValidationError
from theory.gui import field
from theory.gui import widget
from theory.utils.safestring import markSafe
from theory.utils import six
from theory.utils.translation import stringConcat, ugettextLazy as _


class SimpleArrayField(field.TextField):
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


class SplitArrayWidget(widget.BaseFieldInput):

  def __init__(self, widget, size, **kwargs):
    self.widget = widget() if isinstance(widget, type) else widget
    self.size = size
    super(SplitArrayWidget, self).__init__(**kwargs)

  @property
  def isHidden(self):
    return self.widget.isHidden

  def valueFromDatadict(self, data, files, name):
    return [self.widget.valueFromDatadict(data, files, '%s_%s' % (name, index))
        for index in range(self.size)]

  def idForLabel(self, id_):
    # See the comment for RadioSelect.idForLabel()
    if id_:
      id_ += '_0'
    return id_

  def render(self, name, value, attrs=None):
    if self.isLocalized:
      self.widget.isLocalized = self.isLocalized
    value = value or []
    output = []
    finalAttrs = self.buildAttrs(attrs)
    id_ = finalAttrs.get('id', None)
    for i in range(max(len(value), self.size)):
      try:
        widgetValue = value[i]
      except IndexError:
        widgetValue = None
      if id_:
        finalAttrs = dict(finalAttrs, id='%s_%s' % (id_, i))
      output.append(self.widget.render(name + '_%s' % i, widgetValue, finalAttrs))
    return markSafe(self.formatOutput(output))

  def formatOutput(self, renderedWidgets):
    return ''.join(renderedWidgets)

  @property
  def media(self):
    return self.widget.media

  def __deepcopy__(self, memo):
    obj = super(SplitArrayWidget, self).__deepcopy__(memo)
    obj.widget = copy.deepcopy(self.widget)
    return obj

  @property
  def needsMultipartForm(self):
    return self.widget.needsMultipartForm


class SplitArrayField(field.Field):
  defaultErrorMessages = {
    'itemInvalid': _('Item %(nth)s in the array did not validate: '),
  }

  def __init__(self, baseField, size, removeTrailingNulls=False, **kwargs):
    self.baseField = baseField
    self.size = size
    self.removeTrailingNulls = removeTrailingNulls
    widget = SplitArrayWidget(widget=baseField.widget, size=size)
    kwargs.setdefault('widget', widget)
    super(SplitArrayField, self).__init__(**kwargs)

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
