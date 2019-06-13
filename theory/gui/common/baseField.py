# -*- coding: utf-8 -*-
#!/usr/bin/env python
##### System wide lib #####
from __future__ import absolute_import
from __future__ import unicode_literals

from collections import OrderedDict
import copy
import datetime
from decimal import Decimal, DecimalException
from inspect import isclass
from json import loads as jsonLoads
import os
import re
import sys
import warnings
from io import BytesIO

##### Theory lib #####
from theory.conf import settings
from theory.core import validators
from theory.core.exceptions import ValidationError
from theory.gui.util import (
    ErrorList,
    fromCurrentTimezone,
    toCurrentTimezone,
    LocalFileObject
    )
from theory.gui.widget import *
from theory.utils import formats
from theory.utils.encoding import smartText, forceStr, forceText
from theory.utils.ipv6 import cleanIpv6Address
from theory.utils.deprecation import RemovedInTheory19Warning
from theory.utils import six
from theory.utils.importlib import importClass
from theory.utils.six.moves.urllib.parse import urlsplit, urlunsplit
from theory.utils.translation import ugettextLazy as _, ungettextLazy

# Provide this import for backwards compatibility.
from theory.core.validators import EMPTY_VALUES  # NOQA

##### Theory third-party lib #####

##### Local app #####

##### Theory app #####

##### Misc #####

"""
Field classes.
"""

__all__ = (
  'Field', 'TextField', 'IntegerField',
  'DateField', 'TimeField', 'DateTimeField', 'RegexField', 'EmailField',
  'URLField', 'BooleanField', 'NullBooleanField', 'ChoiceField',
  'MultipleChoiceField', 'ListField', 'DictField', 'AdapterField',
  'FileField', 'ImageField', 'FilePathField', 'ImagePathField', 'DirPathField',
  'ComboField', 'MultiValueField',
  #'SplitDateTimeField',
  'FloatField', 'DecimalField', 'IPAddressField', 'GenericIPAddressField',
  'SlugField', 'TypedChoiceField', 'TypedMultipleChoiceField',
  'StringGroupFilterField', 'ModelValidateGroupField', 'PythonModuleField',
  'PythonClassField', 'QuerysetField', 'BinaryField', 'GeoPointField',
)

FILE_INPUT_CONTRADICTION = object()

class Field(object):
  """The function being provided by this class should include data validation,
  valid/error message storage. The relationship between field and widget should
  be one to one."""
  widget = StringInput
  defaultValidators = [] # Default set of validators
  defaultErrorMessages = {
    'required': _(u'This field is required.'),
    'invalid': _(u'Enter a valid value.'),
  }
  emptyValues = list(validators.EMPTY_VALUES)

  # Tracks each time a Field instance is created. Used to retain order.
  creationCounter = 0

  def __init__(self, required=True, label=None, initData=None,
         helpText=None, errorMessages=None, showHiddenInitial=False,
         validators=[], localize=False, isSkipInHistory=False, widget=None,
         uiPropagate={},):
    # required -- Boolean that specifies whether the field is required.
    #             True by default.
    # widget -- A Widget class, or instance of a Widget class, that should
    #           be used for this Field when displaying it. Each Field has a
    #           default Widget that it'll use if you don't specify this. In
    #           most cases, the default widget is TextInput.
    # label -- A verbose name for this field, for use in displaying this
    #          field in a form. By default, Theory will use a "pretty"
    #          version of the form field name, if the Field is part of a
    #          Form.
    # initData -- A value to use in this Field's initial display. This value
    #            is *not* used as a fallback if data isn't given.
    # helpText -- An optional string to use as "help text" for this Field.
    # errorMessages -- An optional dictionary to override the default
    #                   messages that the field will raise.
    # showHiddenInitial -- Boolean that specifies if it is needed to render a
    #                        hidden widget with initial value after widget.
    # validators -- List of additional validators to use
    # localize -- Boolean that specifies if the field should be localized.
    # widget -- Default widget to use when rendering this type of Field.
    if label is not None:
      label = smartText(label)
    self.required, self.label, self.initData = required, label, initData
    #self.finalData = self.initData
    self._changedData = self._finalData = None

    self.showHiddenInitial = showHiddenInitial
    if helpText is None:
      self.helpText = u''
    else:
      self.helpText = smartText(helpText)
    # Trigger the localization machinery if needed.
    self.localize = localize

    # Increase the creation counter, and save our local copy.
    self.creationCounter = Field.creationCounter
    Field.creationCounter += 1

    messages = {}
    for c in reversed(self.__class__.__mro__):
      messages.update(getattr(c, 'defaultErrorMessages', {}))
    messages.update(errorMessages or {})
    self.errorMessages = messages

    self.validators = self.defaultValidators + validators

    # should we skip recording this field into history
    self.isSkipInHistory = isSkipInHistory

    self.uiPropagate = uiPropagate

    if widget is not None:
      self.widget = widget

  def renderWidget(self, *args, **kwargs):
    # widget -- A Widget class, or instance of a Widget class, that should
    #           be used for this Field when displaying it. Each Field has a
    #           default Widget that it'll use if you don't specify this. In
    #           most cases, the default widget is TextInput.
    #widget = widget or self.widget
    widget = self.widget
    if(isclass(widget)):
      widget = self.widget(self.widgetSetter, self.widgetGetter, *args, **kwargs)
      # In some case, ListInput for example, their children input only want the
      # core part instead of the whole part including the instruction
      if ("attrs" not in kwargs
          or "isSkipInHistory" not in kwargs["attrs"]
          or not kwargs["attrs"]["isSkipInstruction"]
          ):
        widget.setupInstructionComponent()

    # Trigger the localization machinery if needed.
    if(self.localize):
      widget.isLocalized = True

    widget.title = self.label
    widget.help = self.helpText

    # Let the widget know whether it should display as required.
    widget.isRequired = self.required

    # Hook into self.widgetAttrs() for any Field-specific HTML attributes.
    extraAttrs = self.widgetAttrs(widget)
    if extraAttrs:
      widget.attrs.update(extraAttrs)

    widget.attrs["initData"] = widget._prepareInitData(self.initData)
    if settings.UI_DEBUG and settings.DEBUG_LEVEL > 5 :
      if not hasattr(self, "logger"):
        import logging
        self.logger = logging.getLogger("theory.internal")
      self.logger.debug(f"baseField renderWidget: {widget.attrs}")
    self.widget = widget

  def getModelFieldNameSuffix(self):
    return ""

  def prepareValue(self, value):
    return value

  def toPython(self, value):
    return value

  def validate(self, value):
    if value in self.emptyValues and self.required:
      raise ValidationError(self.errorMessages['required'], code='required')

  def runValidators(self, value):
    if value in self.emptyValues:
      return
    errors = []
    for v in self.validators:
      try:
        v(value)
      except ValidationError as e:
        if hasattr(e, 'code') and e.code in self.errorMessages:
          e.message = self.errorMessages[e.code]
        errors.extend(e.errorList)
    if errors:
      raise ValidationError(errors)

  def clean(self, value, isEmptyForgiven=False):
    """
    Validates the given value and returns its "cleaned" value as an
    appropriate Python object.

    Raises ValidationError for any errors.
    """
    value = self.toPython(value)
    if isEmptyForgiven and self.required:
      self.required = False
    self.validate(value)
    self.runValidators(value)
    if isEmptyForgiven and self.required:
      self.required = True
    return value

  def boundData(self, data, initial):
    """
    Return the value that should be shown for this field on render of a
    bound form, given the submitted POST data for the field and the initial
    data, if any.

    For most fields, this will simply be data; FileFields need to handle it
    a bit differently.
    """
    return data

  def widgetAttrs(self, widget):
    """
    Given a Widget instance (*not* a Widget class), returns a dictionary of
    any HTML attributes that should be added to the Widget, based on this
    Field.
    """
    return {}

  def getLimitChoicesTo(self):
    """
    Returns ``limitChoicesTo`` for this form field.

    If it is a callable, it will be invoked and the result will be
    returned.
    """
    if callable(self.limitChoicesTo):
      return self.limitChoicesTo()
    return self.limitChoicesTo

  def _hasChanged(self, initial, data):
    """
    Return True if data differs from initial.
    """
    # For purposes of seeing whether something has changed, None is
    # the same as an empty string, if the data or initial value we get
    # is None, replace it w/ ''.
    initialValue = initial if initial is not None else ''
    try:
      data = self.toPython(data)
      if hasattr(self, '_coerce'):
        data = self._coerce(data)
    except ValidationError:
      return True
    dataValue = data if data is not None else ''
    return initialValue != dataValue

  def __deepcopy__(self, memo):
    result = copy.copy(self)
    memo[id(self)] = result
    result.widget = copy.deepcopy(self.widget, memo)
    result.validators = self.validators[:]
    return result

  @property
  def initData(self):
    return self._initData

  @initData.setter
  def initData(self, initData):
    self._initData = initData

  @property
  def changedData(self):
    return self._changedData

  @changedData.setter
  def changedData(self, changedData):
    self._changedData = changedData

  @property
  def finalData(self):
    """It is used to store data directly from widget before validation and
    cleaning."""
    # TODO: allow lazy update
    if(self._finalData in validators.EMPTY_VALUES):
      if(isclass(self.widget)):
        # return initial data if widget has not been rendered and finalData
        # is empty
        return self.initData
      else:
        # force update
        self.widget.updateField()
    return self._finalData

  @finalData.setter
  def finalData(self, finalData):
    self._finalData = finalData

  def forceUpdate(self):
    """
    To force the widget to update the finalData. It is usful when invalid
    data was stored into the field, failed, and new valid data is trying to
    be stored. If we called the updateField() in here, updateField() won't be
    called in the finalData.
    """
    if(not isclass(self.widget)):
      self.widget.updateField()

  def widgetSetter(self, data):
    try:
      self.changedData = data["changedData"]
    except KeyError:
      pass
    try:
      self.finalData = data["finalData"]
    except KeyError:
      pass

  def widgetGetter(self, name):
    if(not name.endswith("Data")):
      # Avoid accidently access other attribute
      raise
    return self.__getattribute__(name)

class TextField(Field):
  widget = StringInput
  lineBreak = "\n"

  def __init__(self, maxLen=None, minLen=None, *args, **kwargs):
    self.maxLen, self.minLen = maxLen, minLen
    super(TextField, self).__init__(*args, **kwargs)
    if minLen is not None:
      self.validators.append(validators.MinLengthValidator(int(minLen)))
    if maxLen is not None:
      self.validators.append(validators.MaxLengthValidator(int(maxLen)))
      if(maxLen>128):
        self.widget = TextInput

  def toPython(self, value):
    "Returns a Unicode object."
    if value in self.emptyValues:
      return ''
    return smartText(value)

  def widgetAttrs(self, widget):
    if(self.maxLen<64):
      return {"isSingleLine": True}

  @property
  def initData(self):
    return self._initData

  @initData.setter
  def initData(self, initData=""):
    if self.lineBreak!="\n" and isinstance(initData, str):
      self._initData = initData.replace("\n", self.lineBreak)
    elif isinstance(initData, (list, tuple)):
      self._initData = "\n".join(initData)
    else:
      self._initData = initData

class IntegerField(Field):
  widget = NumericInput
  defaultErrorMessages = {
    'invalid': _('Enter a whole number.'),
  }

  def __init__(self, maxValue=None, minValue=None, *args, **kwargs):
    self.maxValue, self.minValue = maxValue, minValue
    if kwargs.get('localize') and self.widget == NumericInput:
      # Localized number input is not well supported on most browsers
      kwargs.setdefault('widget', super(IntegerField, self).widget)
    super(IntegerField, self).__init__(*args, **kwargs)

    if maxValue is not None:
      self.validators.append(validators.MaxValueValidator(maxValue))
    if minValue is not None:
      self.validators.append(validators.MinValueValidator(minValue))

  def toPython(self, value):
    """
    Validates that int() can be called on the input. Returns the result
    of int(). Returns None for empty values.
    """
    value = super(IntegerField, self).toPython(value)
    if value in self.emptyValues:
      return None
    if self.localize:
      value = formats.sanitizeSeparators(value)
    try:
      value = int(str(value))
    except (ValueError, TypeError):
      raise ValidationError(self.errorMessages['invalid'], code='invalid')
    return value

  def widgetAttrs(self, widget):
    attrs = super(IntegerField, self).widgetAttrs(widget)
    if isinstance(widget, NumericInput):
      if self.minValue is not None:
        attrs['min'] = self.minValue
      if self.maxValue is not None:
        attrs['max'] = self.maxValue
    return attrs


class FloatField(IntegerField):
  defaultErrorMessages = {
    'invalid': _('Enter a number.'),
  }

  def toPython(self, value):
    """
    Validates that float() can be called on the input. Returns the result
    of float(). Returns None for empty values.
    """
    value = super(IntegerField, self).toPython(value)
    if value in self.emptyValues:
      return None
    if self.localize:
      value = formats.sanitizeSeparators(value)
    try:
      value = float(value)
    except (ValueError, TypeError):
      raise ValidationError(self.errorMessages['invalid'], code='invalid')
    return value

  def validate(self, value):
    super(FloatField, self).validate(value)

    # Check for NaN (which is the only thing not equal to itself) and +/- infinity
    if value != value or value in (Decimal('Inf'), Decimal('-Inf')):
      raise ValidationError(self.errorMessages['invalid'], code='invalid')

    return value

  def widgetAttrs(self, widget):
    attrs = super(FloatField, self).widgetAttrs(widget)
    if isinstance(widget, NumericInput) and 'step' not in widget.attrs:
      attrs.setdefault('step', 'any')
    return attrs


class DecimalField(IntegerField):
  defaultErrorMessages = {
    'invalid': _('Enter a number.'),
    'maxDigits': ungettextLazy(
      'Ensure that there are no more than %(max)s digit in total.',
      'Ensure that there are no more than %(max)s digits in total.',
      'max'),
    'maxDecimalPlaces': ungettextLazy(
      'Ensure that there are no more than %(max)s decimal place.',
      'Ensure that there are no more than %(max)s decimal places.',
      'max'),
    'maxWholeDigits': ungettextLazy(
      'Ensure that there are no more than %(max)s digit before the decimal point.',
      'Ensure that there are no more than %(max)s digits before the decimal point.',
      'max'),
  }

  def __init__(self, maxValue=None, minValue=None, maxDigits=None, decimalPlaces=None, *args, **kwargs):
    self.maxDigits, self.decimalPlaces = maxDigits, decimalPlaces
    super(DecimalField, self).__init__(maxValue, minValue, *args, **kwargs)

  def toPython(self, value):
    """
    Validates that the input is a decimal number. Returns a Decimal
    instance. Returns None for empty values. Ensures that there are no more
    than maxDigits in the number, and no more than decimalPlaces digits
    after the decimal point.
    """
    if value in self.emptyValues:
      return None
    if self.localize:
      value = formats.sanitizeSeparators(value)
    value = smartText(value).strip()
    try:
      value = Decimal(value)
    except DecimalException:
      raise ValidationError(self.errorMessages['invalid'], code='invalid')
    return value

  def validate(self, value):
    super(DecimalField, self).validate(value)
    if value in self.emptyValues:
      return
    # Check for NaN, Inf and -Inf values. We can't compare directly for NaN,
    # since it is never equal to itself. However, NaN is the only value that
    # isn't equal to itself, so we can use this to identify NaN
    if value != value or value == Decimal("Inf") or value == Decimal("-Inf"):
      raise ValidationError(self.errorMessages['invalid'], code='invalid')
    sign, digittuple, exponent = value.as_tuple()
    decimals = abs(exponent)
    # digittuple doesn't include any leading zeros.
    digits = len(digittuple)
    if decimals > digits:
      # We have leading zeros up to or past the decimal point.  Count
      # everything past the decimal point as a digit.  We do not count
      # 0 before the decimal point as a digit since that would mean
      # we would not allow maxDigits = decimalPlaces.
      digits = decimals
    wholeDigits = digits - decimals

    if self.maxDigits is not None and digits > self.maxDigits:
      raise ValidationError(
        self.errorMessages['maxDigits'],
        code='maxDigits',
        params={'max': self.maxDigits},
      )
    if self.decimalPlaces is not None and decimals > self.decimalPlaces:
      raise ValidationError(
        self.errorMessages['maxDecimalPlaces'],
        code='maxDecimalPlaces',
        params={'max': self.decimalPlaces},
      )
    if (self.maxDigits is not None and self.decimalPlaces is not None
        and wholeDigits > (self.maxDigits - self.decimalPlaces)):
      raise ValidationError(
        self.errorMessages['maxWholeDigits'],
        code='maxWholeDigits',
        params={'max': (self.maxDigits - self.decimalPlaces)},
      )
    return value

  def widgetAttrs(self, widget):
    attrs = super(DecimalField, self).widgetAttrs(widget)
    if isinstance(widget, NumericInput) and 'step' not in widget.attrs:
      if self.decimalPlaces is not None:
        # Use exponential notation for small values since they might
        # be parsed as 0 otherwise. ref #20765
        step = str(Decimal('1') / 10 ** self.decimalPlaces).lower()
      else:
        step = 'any'
      attrs.setdefault('step', step)
    return attrs


class BaseTemporalField(Field):

  def __init__(self, inputFormats=None, *args, **kwargs):
    super(BaseTemporalField, self).__init__(*args, **kwargs)
    if inputFormats is not None:
      self.inputFormats = inputFormats

  def toPython(self, value):
    # Try to coerce the value to unicode.
    unicodeValue = forceText(value, stringsOnly=True)
    if isinstance(unicodeValue, six.textType):
      value = unicodeValue.strip()
    # If unicode, try to strptime against each input format.
    if isinstance(value, six.textType):
      for format in self.inputFormats:
        try:
          return self.strptime(value, format)
        except (ValueError, TypeError):
          continue
    raise ValidationError(self.errorMessages['invalid'], code='invalid')

  def strptime(self, value, format):
    raise NotImplementedError('Subclasses must define this method.')


class DateField(BaseTemporalField):
  widget = DateInput
  inputFormats = formats.getFormatLazy('DATE_INPUT_FORMATS')
  defaultErrorMessages = {
    'invalid': _('Enter a valid date.'),
  }

  def toPython(self, value):
    """
    Validates that the input can be converted to a date. Returns a Python
    datetime.date object.
    """
    if value in self.emptyValues:
      return None
    if isinstance(value, datetime.datetime):
      return value.date()
    if isinstance(value, datetime.date):
      return value
    return super(DateField, self).toPython(value)

  def strptime(self, value, format):
    return datetime.datetime.strptime(forceStr(value), format).date()


class TimeField(BaseTemporalField):
  widget = TimeInput
  inputFormats = formats.getFormatLazy('TIME_INPUT_FORMATS')
  defaultErrorMessages = {
    'invalid': _('Enter a valid time.')
  }

  def toPython(self, value):
    """
    Validates that the input can be converted to a time. Returns a Python
    datetime.time object.
    """
    if value in self.emptyValues:
      return None
    if isinstance(value, datetime.time):
      return value
    return super(TimeField, self).toPython(value)

  def strptime(self, value, format):
    return datetime.datetime.strptime(forceStr(value), format).time()


class DateTimeField(BaseTemporalField):
  widget = DateTimeInput
  inputFormats = formats.getFormatLazy('DATETIME_INPUT_FORMATS')
  defaultErrorMessages = {
    'invalid': _('Enter a valid date/time.'),
  }

  def prepareValue(self, value):
    if isinstance(value, datetime.datetime):
      value = toCurrentTimezone(value)
    return value

  def toPython(self, value):
    """
    Validates that the input can be converted to a datetime. Returns a
    Python datetime.datetime object.
    """
    if value in self.emptyValues:
      return None
    if isinstance(value, datetime.datetime):
      return fromCurrentTimezone(value)
    if isinstance(value, datetime.date):
      result = datetime.datetime(value.year, value.month, value.day)
      return fromCurrentTimezone(result)
    if isinstance(value, six.textType):
      unicodeValue = forceText(value, stringsOnly=True)
      if isinstance(unicodeValue, six.textType):
        value = unicodeValue.strip()
      # If unicode, try to strptime against each input format.
      if isinstance(value, six.textType):
        for format in self.inputFormats:
          try:
            return self.strptime(value, format)
          except (ValueError, TypeError):
            continue

    result = super(DateTimeField, self).toPython(value)
    return fromCurrentTimezone(result)

  def strptime(self, value, format):
    return datetime.datetime.strptime(forceStr(value), format)


class RegexField(TextField):
  def __init__(self, regex, maxLen=None, minLen=None, errorMessage=None, *args, **kwargs):
    """
    regex can be either a string or a compiled regular expression object.
    errorMessage is an optional error message to use, if
    'Enter a valid value' is too generic for you.
    """
    # errorMessage is just kept for backwards compatibility:
    if errorMessage is not None:
      errorMessages = kwargs.get('errorMessages') or {}
      errorMessages['invalid'] = errorMessage
      kwargs['errorMessages'] = errorMessages
    super(RegexField, self).__init__(maxLen, minLen, *args, **kwargs)
    self._setRegex(regex)

  def _getRegex(self):
    return self._regex

  def _setRegex(self, regex):
    if isinstance(regex, six.stringTypes):
      regex = re.compile(regex, re.UNICODE)
    self._regex = regex
    if hasattr(self, '_regexValidator') and self._regexValidator in self.validators:
      self.validators.remove(self._regexValidator)
    self._regexValidator = validators.RegexValidator(regex=regex)
    self.validators.append(self._regexValidator)

  regex = property(_getRegex, _setRegex)


class EmailField(TextField):
  defaultValidators = [validators.validateEmail]

  def clean(self, value, isEmptyForgiven=False):
    value = self.toPython(value).strip()
    return super(EmailField, self).clean(value)


class FileField(Field):
  widget = FileselectInput
  defaultErrorMessages = {
    'invalid': _("No file was submitted. Check the encoding type on the form."),
    'missing': _("No file was submitted."),
    'empty': _("The submitted file is empty."),
    'maxLen': ungettextLazy(
      'Ensure this filename has at most %(max)d character (it has %(length)d).',
      'Ensure this filename has at most %(max)d characters (it has %(length)d).',
      'max'),
    'contradiction': _('Please either submit a file or check the clear checkbox, not both.')
  }

  def __init__(self, *args, **kwargs):
    self.maxLen = kwargs.pop('maxLen', None)
    self.allowEmptyFile = kwargs.pop('allowEmptyFile', False)
    self.initDir = kwargs.pop('initDir', None)
    super(FileField, self).__init__(*args, **kwargs)

  def renderWidget(self, *args, **kwargs):
    if(self.initData is not None and self.initDir is None):
      self.initDir = os.path.dirname(self.initData)
    super(FileField, self).renderWidget(*args, **kwargs)
    if(self.initDir is not None):
      self.widget.attrs["initDir"] = self.initDir

  def toPython(self, data):
    if data in self.emptyValues:
      return None

    # UploadedFile objects should have name and size attributes.
    try:
      fileName = data.name
      fileSize = data.size
    except AttributeError:
      raise ValidationError(self.errorMessages['invalid'], code='invalid')

    if self.maxLen is not None and len(fileName) > self.maxLen:
      params = {'max': self.maxLen, 'length': len(fileName)}
      raise ValidationError(self.errorMessages['maxLen'], code='maxLen', params=params)
    if not fileName:
      raise ValidationError(self.errorMessages['invalid'], code='invalid')
    if not self.allowEmptyFile and not fileSize:
      raise ValidationError(self.errorMessages['empty'], code='empty')

    return data

  def clean(self, data, initial=None, isEmptyForgiven=False):
    if(isinstance(data, basestring)):
      data = LocalFileObject(data)
    # If the widget got contradictory inputs, we raise a validation error
    if data is FILE_INPUT_CONTRADICTION:
      raise ValidationError(self.errorMessages['contradiction'], code='contradiction')
    # False means the field value should be cleared; further validation is
    # not needed.
    if data is False:
      if not self.required:
        return False
      # If the field is required, clearing is not possible (the widget
      # shouldn't return False data in that case anyway). False is not
      # in self.emptyValue; if a False value makes it this far
      # it should be validated from here on out as None (so it will be
      # caught by the required check).
      data = None
    if not data and initial:
      return initial
    return super(FileField, self).clean(data)

  def boundData(self, data, initial):
    if data in (None, FILE_INPUT_CONTRADICTION):
      return initial
    return data

  def _hasChanged(self, initial, data):
    if data is None:
      return False
    return True


class ImageField(FileField):
  defaultErrorMessages = {
    'invalidImage': _("Upload a valid image. The file you uploaded was either not an image or a corrupted image."),
  }

  def toPython(self, data):
    """
    Checks that the file-upload field data contains a valid image (GIF, JPG,
    PNG, possibly others -- whatever the Python Imaging Library supports).
    """
    f = super(ImageField, self).toPython(data)
    if f is None:
      return None

    from PIL import Image

    # We need to get a file object for Pillow. We might have a path or we might
    # have to read the data into memory.
    if hasattr(data, 'temporaryFilePath'):
      file = data.temporaryFilePath()
    else:
      if hasattr(data, 'read'):
        file = BytesIO(data.read())
      else:
        file = BytesIO(data['content'])

    try:
      # load() could spot a truncated JPEG, but it loads the entire
      # image in memory, which is a DoS vector. See #3848 and #18520.
      # verify() must be called immediately after the constructor.
      Image.open(file).verify()
    except Exception:
      # Pillow doesn't recognize it as an image.
      six.reraise(ValidationError, ValidationError(
        self.errorMessages['invalidImage'],
        code='invalidImage',
      ), sys.excInfo()[2])
    if hasattr(f, 'seek') and callable(f.seek):
      f.seek(0)
    return f

class FilePathField(FileField):
  """
  From the widget side, FilePathField and FileField would have no difference,
  but the FilePathField should save the path instead of actual file into DB.
  """
  pass

class ImagePathField(ImageField):
  pass

class DirPathField(Field):
  widget = FileselectInput
  defaultErrorMessages = {
    'missing': _(u"No directory was submitted."),
    'empty': _(u"The submitted directory is empty."),
    'notAccessable': _(u"The submitted directory is not accessable."),
    'notDir': _(u"The submitted directory is not a directory."),
  }

  def renderWidget(self, *args, **kwargs):
    super(DirPathField, self).renderWidget(*args, **kwargs)
    self.widget.attrs["isFolderOnly"] = True

  def validate(self, value):
    super(DirPathField, self).validate(value)
    if(not os.access(value, os.R_OK)):
      raise ValidationError(self.errorMessages['notAccessable'])
    if(not os.path.isdir(value)):
      raise ValidationError(self.errorMessages['notDir'])
    if(len(os.listdir(value)) == 0):
      raise ValidationError(self.errorMessages['empty'])

class URLField(TextField):
  defaultErrorMessages = {
    'invalid': _('Enter a valid URL.'),
  }
  defaultValidators = [validators.URLValidator()]

  def toPython(self, value):

    def splitUrl(url):
      """
      Returns a list of url parts via ``urlparse.urlsplit`` (or raises a
      ``ValidationError`` exception for certain).
      """
      try:
        return list(urlsplit(url))
      except ValueError:
        # urlparse.urlsplit can raise a ValueError with some
        # misformatted URLs.
        raise ValidationError(self.errorMessages['invalid'], code='invalid')

    value = super(URLField, self).toPython(value)
    if value:
      urlFields = splitUrl(value)
      if not urlFields[0]:
        # If no URL scheme given, assume http://
        urlFields[0] = 'http'
      if not urlFields[1]:
        # Assume that if no domain is provided, that the path segment
        # contains the domain.
        urlFields[1] = urlFields[2]
        urlFields[2] = ''
        # Rebuild the urlFields list, since the domain segment may now
        # contain the path too.
        urlFields = splitUrl(urlunsplit(urlFields))
      value = urlunsplit(urlFields)
    return value

  def clean(self, value, isEmptyForgiven=False):
    value = self.toPython(value).strip()
    return super(URLField, self).clean(value)


class BooleanField(Field):
  widget = SelectBoxInput

  def renderWidget(self, *args, **kwargs):
    super(BooleanField, self).renderWidget(*args, **kwargs)
    self.widget.attrs["choices"] = ((0, "False"), (1, "True"))

  def toPython(self, value):
    """Returns a Python boolean object."""
    # Explicitly check for the string 'False', which is what a hidden field
    # will submit for False. Also check for '0', since this is what
    # RadioSelect will provide. Because bool("True") == bool('1') == True,
    # we don't need to handle that explicitly.
    if isinstance(value, six.stringTypes) and value.lower() in ('false', '0'):
      value = False
    else:
      value = bool(value)
    return super(BooleanField, self).toPython(value)

  def validate(self, value):
    if value is not True and value is not False and self.required:
    #if not value and self.required:
      raise ValidationError(self.errorMessages['required'], code='required')

  def _hasChanged(self, initial, data):
    # Sometimes data or initial could be None or '' which should be the
    # same thing as False.
    if initial == 'False':
      # showHiddenInitial may have transformed False to 'False'
      initial = False
    return bool(initial) != bool(data)


class NullBooleanField(BooleanField):
  """
  A field whose valid values are None, True and False. Invalid values are
  cleaned to None.
  """
  widget = SelectBoxInput

  def toPython(self, value):
    """
    Explicitly checks for the string 'True' and 'False', which is what a
    hidden field will submit for True and False, and for '1' and '0', which
    is what a RadioField will submit. Unlike the Booleanfield we need to
    explicitly check for True, because we are not using the bool() function
    """
    if value in (True, 'True', '1'):
      return True
    elif value in (False, 'False', '0'):
      return False
    else:
      return None

  def validate(self, value):
    pass

  def _hasChanged(self, initial, data):
    # None (unknown) and False (No) are not the same
    if initial is not None:
      initial = bool(initial)
    if data is not None:
      data = bool(data)
    return initial != data


class ChoiceField(Field):
  """
  Choices will be (value, label). Value must be the key, as label may be
  crushed while value can never be crushed.
  """
  widget = SelectBoxInput
  defaultErrorMessages = {
    'invalidChoice': _('Select a valid choice. %(value)s is not one of the available choices.'),
  }

  def renderWidget(self, *args, **kwargs):
    super(ChoiceField, self).renderWidget(*args, **kwargs)
    self.widget.attrs["choices"] = self.choices

  def __init__(self, choices=(), dynamicChoiceLst=None, *args, **kwargs):
    # Choice field and its descendant will have dynamicChoiceLst and set
    # as None by default. We don't want to store it unless
    # dynamicChoiceLst has been actually in use because we will override
    # choices by dynamicChoiceLst
    super(ChoiceField, self).__init__(*args, **kwargs)
    self.choices = choices
    # Have to store it for CommandClassScanner to read and validation
    self.dynamicChoiceLst = dynamicChoiceLst

  def __deepcopy__(self, memo):
    result = super(ChoiceField, self).__deepcopy__(memo)
    result._choices = copy.deepcopy(self._choices, memo)
    return result

  def _getChoices(self):
    return self._choices

  def _setChoices(self, value):
    # Setting choices also sets the choices on the widget.
    # choices can be any iterable, but we call list() on it because
    # it will be consumed more than once.
    self._choices = list(value)
    if not isclass(self.widget):
      self.widget.choices = self._choices

  choices = property(_getChoices, _setChoices)

  def toPython(self, value):
    "Returns a Unicode object."
    if value in self.emptyValues:
      return ''
    return smartText(value)

  def validate(self, value):
    """
    Validates that the input is in self.choices.
    """
    if self.dynamicChoiceLst is not None:
      self.choices = self.dynamicChoiceLst
    super(ChoiceField, self).validate(value)
    if value and not self.validValue(value):
      raise ValidationError(
        self.errorMessages['invalidChoice'],
        code='invalidChoice',
        params={'value': value},
      )

  def validValue(self, value):
    "Check to see if the provided value is a valid choice"
    textValue = forceText(value)
    for k, v in self.choices:
      if isinstance(v, (list, tuple)):
        # This is an optgroup, so look inside the group for options
        for k2, v2 in v:
          if value == k2 or textValue == forceText(k2):
            return True
      else:
        if value == k or textValue == forceText(k):
          return True
    return False


class TypedChoiceField(ChoiceField):
  def __init__(self, *args, **kwargs):
    self.coerce = kwargs.pop('coerce', lambda val: val)
    self.emptyValue = kwargs.pop('emptyValue', '')
    super(TypedChoiceField, self).__init__(*args, **kwargs)

  def _coerce(self, value):
    """
    Validate that the value can be coerced to the right type (if not empty).
    """
    if value == self.emptyValue or value in self.emptyValues:
      return self.emptyValue
    try:
      value = self.coerce(value)
    except (ValueError, TypeError, ValidationError):
      raise ValidationError(
        self.errorMessages['invalidChoice'],
        code='invalidChoice',
        params={'value': value},
      )
    return value

  def clean(self, value, isEmptyForgiven=False):
    value = super(TypedChoiceField, self).clean(value)
    return self._coerce(value)


class MultipleChoiceField(ChoiceField):
  #hidden_widget = MultipleHiddenInput
  widget = CheckBoxInput
  defaultErrorMessages = {
    'invalidChoice': _('Select a valid choice. %(value)s is not one of the available choices.'),
    'invalidList': _('Enter a list of values.'),
  }

  def toPython(self, value):
    if not value:
      return []
    elif not isinstance(value, (list, tuple)):
      raise ValidationError(self.errorMessages['invalidList'], code='invalidList')
    return [smartText(val) for val in value]

  def validate(self, value):
    """
    Validates that the input is a list or tuple.
    """
    if self.required and not value:
      raise ValidationError(self.errorMessages['required'], code='required')
    if self.dynamicChoiceLst is not None:
      self.choices = self.dynamicChoiceLst
    # Validate that each value in the value list is in self.choices.
    for val in value:
      if not self.validValue(val):
        raise ValidationError(
          self.errorMessages['invalidChoice'],
          code='invalidChoice',
          params={'value': val},
        )

  def _hasChanged(self, initial, data):
    if initial is None:
      initial = []
    if data is None:
      data = []
    if len(initial) != len(data):
      return True
    initialSet = set(forceText(value) for value in initial)
    dataSet = set(forceText(value) for value in data)
    return dataSet != initialSet


class TypedMultipleChoiceField(MultipleChoiceField):
  def __init__(self, *args, **kwargs):
    self.coerce = kwargs.pop('coerce', lambda val: val)
    self.emptyValue = kwargs.pop('emptyValue', [])
    super(TypedMultipleChoiceField, self).__init__(*args, **kwargs)

  def _coerce(self, value):
    """
    Validates that the values are in self.choices and can be coerced to the
    right type.
    """
    if value == self.emptyValue or value in self.emptyValues:
      return self.emptyValue
    newValue = []
    for choice in value:
      try:
        newValue.append(self.coerce(choice))
      except (ValueError, TypeError, ValidationError):
        raise ValidationError(
          self.errorMessages['invalidChoice'],
          code='invalidChoice',
          params={'value': choice},
        )
    return newValue

  def clean(self, value, isEmptyForgiven=False):
    value = super(TypedMultipleChoiceField, self).clean(value)
    return self._coerce(value)

  def validate(self, value):
    if value != self.emptyValue:
      super(TypedMultipleChoiceField, self).validate(value)
    elif self.required:
      raise ValidationError(self.errorMessages['required'], code='required')


class ComboField(Field):
  """
  A Field whose clean() method calls multiple Field clean() methods.
  """
  def __init__(self, fields=(), *args, **kwargs):
    super(ComboField, self).__init__(*args, **kwargs)
    # Set 'required' to False on the individual fields, because the
    # required validation will be handled by ComboField, not by those
    # individual fields.
    for f in fields:
      f.required = False
    self.fields = fields

  def clean(self, value, isEmptyForgiven=False):
    """
    Validates the given value against all of self.fields, which is a
    list of Field instances.
    """
    super(ComboField, self).clean(value)
    for field in self.fields:
      value = field.clean(value)
    return value

class ListField(Field):
  """
  A Field that aggregates the logic of multiple Fields.
  You'll probably want to use this with MultiWidget.
  """
  widget = ListInput
  defaultErrorMessages = {
    'invalid': _(u'Enter a list of values.'),
  }

  def __init__(
      self,
      field,
      initData=[],
      minLen=0,
      maxLen=sys.maxsize,
      *args,
      **kwargs
      ):
    # Set 'required' to False on the individual fields, because the
    # required validation will be handled by ListField, not by those
    # individual fields.
    field.required = False
    self.fields = []
    self.childFieldTemplate = copy.deepcopy(field)
    # It stores the minium number of elements is required in this field
    self.minLen = minLen
    # It stores the maxium number of elements is required in this field
    self.maxLen = maxLen

    kwargs["initData"] = initData
    super(ListField, self).__init__(*args, **kwargs)

  def _setupChildrenData(self, data, fieldName):
    # ArrayField's default can be None. If the init data is None, ListField
    # does not gurantee return None if no modification is applied, ListField
    # will return [] instead.
    if data is not None:
      for i in data:
        self.addChildField(i, fieldName)
    #if(not isinstance(self.widget, type)):
    if(not isclass(self.widget)):
      self.widget.childFieldLst = self.fields

  def renderWidget(self, *args, **kwargs):
    # widget -- A Widget class, or instance of a Widget class, that should
    #           be used for this Field when displaying it. Each Field has a
    #           default Widget that it'll use if you don't specify this. In
    #           most cases, the default widget is TextInput.
    #widget = widget or self.widget
    widget = self.widget
    # For some widget which is unable to display e.x: binary data
    if(self.childFieldTemplate.widget is None):
      self.widget = None
    elif(isclass(widget)):
      # args[0] is always win, args[1] is always bx
      self.widget = widget(
          self.widgetSetter,
          self.widgetGetter,
          args[0],
          args[1],
          childFieldLst=self.fields,
          addChildFieldFxn=self.addChildField,
          removeChildFieldFxn=self.removeChildField,
          **kwargs)
      self.widget._probeChildWidget(self.childFieldTemplate)
      self.widget.setupInstructionComponent()
      super(ListField, self).renderWidget(*args, **kwargs)

  def addChildField(self, data, fieldName="initData"):
    field = copy.deepcopy(self.childFieldTemplate)
    if(hasattr(field, "embeddedFieldDict")):
      # The deepcopy is unable to do the copy the embeddedFieldDict, so we
      # have to make a special case for embeddedField
      field.embeddedFieldDict = copy.deepcopy(
          self.childFieldTemplate.embeddedFieldDict
          )
    if(data is not None):
      setattr(field, fieldName, data)
    self.fields.append(field)
    return field

  def removeChildField(self, idx):
    del self.fields[idx]

  def validate(self, valueList):
    if((self.required and len(valueList)<self.minLen) \
        or len(valueList)>self.maxLen):
      raise ValidationError(self.errorMessages['required'])

  def clean(self, valueList, isEmptyForgiven=False):
    """
    Validates every value in the given list. A value is validated against
    the corresponding Field in self.fields.
    """
    cleanData = []
    errors = ErrorList()
    if((self.required and len(valueList)<self.minLen) \
        or len(valueList)>self.maxLen):
      raise ValidationError(self.errorMessages['required'])

    for value in valueList:
      try:
        cleanData.append(self.childFieldTemplate.clean(value))
      except IndexError:
        pass
      except ValidationError as e:
        # Collect all validation errors in a single list, which we'll
        # raise at the end of clean(), rather than raising a single
        # exception for the first error we encounter.
        errors.extend(e.messages)
    if errors:
      raise ValidationError(errors)

    self.validate(cleanData)
    self.runValidators(cleanData)
    return cleanData

  @property
  def initData(self):
    return self._initData

  @initData.setter
  def initData(self, initData):
    self._initData = initData
    self.fields = []
    self._setupChildrenData(initData, "initData")
    self._changedData = self._finalData = []

  @property
  def changedData(self):
    return [i.changedData for i in self.fields]

  @changedData.setter
  def changedData(self, changedData):
    raise NotImplementedError

  @property
  def finalData(self):
    """It is used to store data directly from widget before validation and
    cleaning."""
    if(isclass(self.widget) or self.widget.isOverridedData):
      # some widget like Multibuttonentry from the e17 need special treatment
      # on retriving data
      data = super(ListField, self).finalData
      if (data==[u""] and
          self.initData==[] and
          issubclass(self.childFieldTemplate.widget, StringInput)
          ):
        return self.initData
      else:
        return data
    else:
      return [i.finalData for i in self.fields]

  @finalData.setter
  def finalData(self, finalData):
    if(isclass(self.widget) or self.widget.isOverridedData):
    #if(not isinstance(self.widget, type) and self.widget.isOverridedData):
      Field.finalData.fset(self, finalData)
    else:
      self._setupChildrenData(finalData, "finalData")

class DictField(Field):
  widget = DictInput
  defaultErrorMessages = {
    'lenUnmatch': _(u'The length of various fields unmatch.'),
  }

  def __init__(
      self,
      keyField,
      valueField,
      initData={},
      minLen=0,
      maxLen=sys.maxsize,
      *args,
      **kwargs
      ):

    # Set 'required' to False on the individual fields, because the
    # required validation will be handled by ListField, not by those
    # individual fields.
    keyField.required = False
    valueField.required = False
    self.keyFields = []
    self.valueFields = []
    self.childKeyFieldTemplate = copy.deepcopy(keyField)
    self.childValueFieldTemplate = copy.deepcopy(valueField)
    # It stores the minium number of elements is required in this field
    self.minLen = minLen
    # It stores the maxium number of elements is required in this field
    self.maxLen = maxLen

    kwargs["initData"] = initData
    super(DictField, self).__init__(*args, **kwargs)

  def _setupChildrenData(self, data, fieldName):
    keys = data.keys()
    for i in range(len(keys)):
      self.addChildField((keys[i], data[keys[i]]), fieldName)

    if(not isinstance(self.widget, type)):
      self.widget.childFieldPairLst = []
      for i in range(len(self.keyFields)):
        self.widget.childFieldPairLst.append(
            (self.keyFields[i], self.valueFields[i])
        )

  def addChildField(self, data, fieldName="initData"):
    keyField = copy.deepcopy(self.childKeyFieldTemplate)
    valueField = copy.deepcopy(self.childValueFieldTemplate)
    if(hasattr(valueField, "embeddedFieldDict")):
      # The deepcopy is unable to do the copy the embeddedFieldDict, so we
      # have to make a special case for embeddedField
      valueField.embeddedFieldDict = copy.deepcopy(
          self.childValueFieldTemplate.embeddedFieldDict
          )
    if(data is not None):
      (keyData, valueData) = data
      setattr(keyField, fieldName, keyData)
      setattr(valueField, fieldName, valueData)
    self.keyFields.append(keyField)
    self.valueFields.append(valueField)
    return (keyField, valueField)

  def removeChildField(self, idx):
    del self.keyFields[idx]
    del self.valueFields[idx]

  def validate(self, valueDict):
    if((self.required and len(valueDict)<self.minLen) \
        or len(valueDict)>self.maxLen):
      raise ValidationError(self.errorMessages['required'])

  def clean(self, valueOrderedDict, isEmptyForgiven=False):
    """
    Validates every value in the given list. A value is validated against
    the corresponding Field in self.fields.
    """
    cleanData = OrderedDict()
    errors = ErrorList()
    valueOrderedDictLen = len(valueOrderedDict)
    if((self.required and valueOrderedDictLen<self.minLen) \
        or valueOrderedDictLen>self.maxLen):
      raise ValidationError(self.errorMessages['required'])
    if(valueOrderedDictLen==0
        and len(self.keyFields)==1
        and self.keyFields[0].finalData==self.keyFields[0].initData
        and len(self.valueFields)==1
        and self.valueFields[0].finalData==self.valueFields[0].initData
        ):
      # User has not modified anything
      pass
    elif(valueOrderedDictLen!=len(self.keyFields)
        or valueOrderedDictLen!=len(self.valueFields)):
      raise ValidationError(self.errorMessages['lenUnmatch'])

    i = 0
    for k, v in valueOrderedDict.items():
      try:
        cleanData[self.keyFields[i].clean(k)] = \
            self.valueFields[i].clean(v)
      except IndexError:
        pass
      except ValidationError as e:
        # Collect all validation errors in a single list, which we'll
        # raise at the end of clean(), rather than raising a single
        # exception for the first error we encounter.
        errors.extend(e.messages)
      finally:
        i += 1
    if errors:
      raise ValidationError(errors)

    self.validate(cleanData)
    self.runValidators(cleanData)
    return cleanData

  @property
  def initData(self):
    return self._initData

  @initData.setter
  def initData(self, initData):
    self._initData = initData
    self.keyFields = []
    self.valueFields = []
    self._setupChildrenData(initData, "initData")
    self._changedData = self._finalData = {}

  # This is a special case of overriding multiple property methods
  # This class now has an this propertyField with a modified getter
  # so modify its setter rather than Parent.propertyField's setter.
  # This is an examaple: @Field.finalData.getter

  # OK, since we have setter, we can simply use @property instead
  @property
  def finalData(self):
    """It is used to store data directly from widget before validation and
    cleaning."""
    # TODO: allow lazy update
    if(isclass(self.widget) or self.widget.isOverridedData):
      # some widget like Multibuttonentry from the e17 need special treatment
      # on retriving data
      return super(DictField, self).finalData
    else:
      d = OrderedDict()
      for i in range(len(self.keyFields)):
        d[self.keyFields[i].finalData] = self.valueFields[i].finalData
      # fullClean() will clear the widget instance and hence finalData will be
      # equal to initData if we don't set the finalData in here
      self._finalData = d
      return d

  @finalData.setter
  def finalData(self, finalData):
    if(not isinstance(self.widget, type) and self.widget.isOverridedData):
      Field.finalData.fset(self, finalData)
    else:
      self._setupChildrenData(finalData, "finalData")

  def runValidators(self, valueDict):
    if valueDict in validators.EMPTY_VALUES:
      return
    errors = []
    for value in valueDict:
      for v in self.validators:
        try:
          v(value)
        except ValidationError as e:
          if hasattr(e, 'code') and e.code in self.errorMessages:
            message = self.errorMessages[e.code]
            if e.params:
              message = message % e.params
            errors.append(message)
          else:
            errors.extend(e.messages)
    if errors:
      raise ValidationError(errors)

  def renderWidget(self, *args, **kwargs):
    # widget -- A Widget class, or instance of a Widget class, that should
    #           be used for this Field when displaying it. Each Field has a
    #           default Widget that it'll use if you don't specify this. In
    #           most cases, the default widget is TextInput.
    widget = self.widget
    # For some widget which is unable to display e.x: binary data
    if(self.childValueFieldTemplate.widget is None):
      self.widget = None
    elif isinstance(widget, type):

      childFieldPairLst = []
      for i in range(len(self.keyFields)):
        childFieldPairLst.append(
            (self.keyFields[i], self.valueFields[i])
        )
      self.widget = widget(
          self.widgetSetter,
          self.widgetGetter,
          addChildFieldFxn=self.addChildField,
          removeChildFieldFxn=self.removeChildField,
          childFieldPairLst=childFieldPairLst,
          *args, **kwargs)
      self.widget.setupInstructionComponent()
      super(DictField, self).renderWidget(*args, **kwargs)

class AdapterField(Field):
  widget = CheckBoxInput

  def __init__(self, *args, **kwargs):
    super(AdapterField, self).__init__(*args, **kwargs)
    self.initData = [] if self.initData is None else self.initData

  def renderWidget(self, *args, **kwargs):
    # To avoid circular dependency
    from theory.apps.model import Adapter
    if("attrs" not in kwargs):
      kwargs["attrs"] = {}

    kwargs["attrs"]["choices"] = \
        [(i.name, i.name) for i in Adapter.objects.all()]
    super(AdapterField, self).renderWidget(*args, **kwargs)

  def widgetSetter(self, adapterDict):
    # To avoid circular dependency
    from theory.apps.model import Adapter
    nameLst = adapterDict["finalData"]
    data = Adapter.objects.filter(name__in=nameLst)
    super(AdapterField, self).widgetSetter({"finalData": data})

class MultiValueField(Field):
  """
  A Field that aggregates the logic of multiple Fields.

  Its clean() method takes a "decompressed" list of values, which are then
  cleaned into a single value according to self.fields. Each value in
  this list is cleaned by the corresponding field -- the first value is
  cleaned by the first field, the second value is cleaned by the second
  field, etc. Once all fields are cleaned, the list of clean values is
  "compressed" into a single value.

  Subclasses should not have to implement clean(). Instead, they must
  implement compress(), which takes a list of valid values and returns a
  "compressed" version of those values -- a single value.

  You'll probably want to use this with MultiWidget.
  """
  defaultErrorMessages = {
    'invalid': _('Enter a list of values.'),
    'incomplete': _('Enter a complete value.'),
  }

  def __init__(self, fields=(), *args, **kwargs):
    self.requireAllFields = kwargs.pop('requireAllFields', True)
    super(MultiValueField, self).__init__(*args, **kwargs)
    for f in fields:
      f.errorMessages.setdefault('incomplete',
                    self.errorMessages['incomplete'])
      if self.requireAllFields:
        # Set 'required' to False on the individual fields, because the
        # required validation will be handled by MultiValueField, not
        # by those individual fields.
        f.required = False
    self.fields = fields

  def __deepcopy__(self, memo):
    result = super(MultiValueField, self).__deepcopy__(memo)
    result.fields = tuple([x.__deepcopy__(memo) for x in self.fields])
    return result

  def validate(self, value):
    pass

  def clean(self, value, isEmptyForgiven=False):
    """
    Validates every value in the given list. A value is validated against
    the corresponding Field in self.fields.

    For example, if this MultiValueField was instantiated with
    fields=(DateField(), TimeField()), clean() would call
    DateField.clean(value[0]) and TimeField.clean(value[1]).
    """
    cleanData = []
    errors = []
    if not value or isinstance(value, (list, tuple)):
      if not value or not [v for v in value if v not in self.emptyValues]:
        if self.required:
          raise ValidationError(self.errorMessages['required'], code='required')
        else:
          return self.compress([])
    else:
      raise ValidationError(self.errorMessages['invalid'], code='invalid')
    for i, field in enumerate(self.fields):
      try:
        fieldValue = value[i]
      except IndexError:
        fieldValue = None
      if fieldValue in self.emptyValues:
        if self.requireAllFields:
          # Raise a 'required' error if the MultiValueField is
          # required and any field is empty.
          if self.required:
            raise ValidationError(self.errorMessages['required'], code='required')
        elif field.required:
          # Otherwise, add an 'incomplete' error to the list of
          # collected errors and skip field cleaning, if a required
          # field is empty.
          if field.errorMessages['incomplete'] not in errors:
            errors.append(field.errorMessages['incomplete'])
          continue
      try:
        cleanData.append(field.clean(fieldValue))
      except ValidationError as e:
        # Collect all validation errors in a single list, which we'll
        # raise at the end of clean(), rather than raising a single
        # exception for the first error we encounter. Skip duplicates.
        errors.extend(m for m in e.errorList if m not in errors)
    if errors:
      raise ValidationError(errors)

    out = self.compress(cleanData)
    self.validate(out)
    self.runValidators(out)
    return out

  def compress(self, dataList):
    """
    Returns a single value for the given list of values. The values can be
    assumed to be valid.

    For example, if this MultiValueField was instantiated with
    fields=(DateField(), TimeField()), this might return a datetime
    object created by combining the date and time in dataList.
    """
    raise NotImplementedError('Subclasses must implement this method.')

  def _hasChanged(self, initial, data):
    if initial is None:
      initial = ['' for x in range(0, len(data))]
    else:
      if not isinstance(initial, list):
        initial = self.widget.decompress(initial)
    for field, initial, data in zip(self.fields, initial, data):
      if field._hasChanged(field.toPython(initial), data):
        return True
    return False

'''
class SplitDateTimeField(MultiValueField):
  widget = SplitDateTimeWidget
  hiddenWidget = SplitHiddenDateTimeWidget
  defaultErrorMessages = {
    'invalidDate': _('Enter a valid date.'),
    'invalidTime': _('Enter a valid time.'),
  }

  def __init__(self, inputDateFormats=None, inputTimeFormats=None, *args, **kwargs):
    errors = self.defaultErrorMessages.copy()
    if 'errorMessages' in kwargs:
      errors.update(kwargs['errorMessages'])
    localize = kwargs.get('localize', False)
    fields = (
      DateField(inputFormats=inputDateFormats,
           errorMessages={'invalid': errors['invalidDate']},
           localize=localize),
      TimeField(inputFormats=inputTimeFormats,
           errorMessages={'invalid': errors['invalidTime']},
           localize=localize),
    )
    super(SplitDateTimeField, self).__init__(fields, *args, **kwargs)

  def compress(self, dataList):
    if dataList:
      # Raise a validation error if time or date is empty
      # (possible if SplitDateTimeField has required=False).
      if dataList[0] in self.emptyValues:
        raise ValidationError(self.errorMessages['invalidDate'], code='invalidDate')
      if dataList[1] in self.emptyValues:
        raise ValidationError(self.errorMessages['invalidTime'], code='invalidTime')
      result = datetime.datetime.combine(*dataList)
      return fromCurrentTimezone(result)
    return None
'''


class IPAddressField(TextField):
  defaultValidators = [validators.validateIpv4Address]

  def __init__(self, *args, **kwargs):
    warnings.warn("IPAddressField has been deprecated. Use GenericIPAddressField instead.",
           RemovedInTheory19Warning)
    super(IPAddressField, self).__init__(*args, **kwargs)

  def toPython(self, value):
    if value in self.emptyValues:
      return None
    return value.strip()


class GenericIPAddressField(TextField):
  def __init__(self, protocol='both', unpackIpv4=False, *args, **kwargs):
    self.unpackIpv4 = unpackIpv4
    self.defaultValidators = validators.ipAddressValidators(protocol, unpackIpv4)[0]
    super(GenericIPAddressField, self).__init__(*args, **kwargs)

  def toPython(self, value):
    if value in self.emptyValues:
      return ''
    value = value.strip()
    if value and ':' in value:
      return cleanIpv6Address(value, self.unpackIpv4)
    return value


class SlugField(TextField):
  defaultValidators = [validators.validateSlug]

  def clean(self, value, isEmptyForgiven=False):
    value = self.toPython(value).strip()
    return super(SlugField, self).clean(value)


class StringGroupFilterField(Field):
  widget = StringGroupFilterInput

class ModelValidateGroupField(Field):
  widget = ModelValidateGroupInput


class PythonModuleField(Field):
  defaultErrorMessages = {
    'invalid': _('Unable to import the given module'),
  }

  def __init__(self, maxLen=None, minLen=None, autoImport=False, *args, **kwargs):
    super(PythonModuleField, self).__init__(*args, **kwargs)
    self.widget = StringInput
    self.autoImport = autoImport

  def widgetAttrs(self, widget):
    return {"isSingleLine": True}

  def validate(self, value):
    """
    Validates if the input is able to import
    """
    super(PythonModuleField, self).validate(value)
    if(not self.autoImport):
      return value

    try:
      inspectModule = importClass(value)
      if(type(inspectModule).__name__!="module"):
        raise ValidationError(self.errorMessages['invalid'] % {'value': value})
    except (ImportError, AttributeError) as e:
      if(value=="" and not self.required):
        pass
      else:
        raise ValidationError(self.errorMessages['invalid'] % {'value': value})
    return inspectModule

class PythonClassField(Field):
  defaultErrorMessages = {
    'invalid': _('Unable to import the given class'),
    'wrong_classtype': _('The given class is not matched'),
  }

  def __init__(self, maxLen=None, minLen=None, autoImport=False, klassType=None, *args, **kwargs):
    super(PythonClassField, self).__init__(*args, **kwargs)
    self.widget = StringInput
    self.autoImport = autoImport
    self.klassType = klassType

  def widgetAttrs(self, widget):
    return {"isSingleLine": True}

  def validate(self, value):
    """
    Validates if the input is able to import
    """
    super(PythonClassField, self).validate(value)
    if(not self.autoImport):
      return value

    if(value!="" and value!=None):
      try:
        inspectKlass = importClass(value)
      except (ImportError, AttributeError) as e:
        inspectKlass = None
      if(inspectKlass==None):
          raise ValidationError(self.errorMessages['invalid'] % {'value': value})
      if(self.klassType !=None and not issubclass(inspectKlass, importClass(self.klassType))):
        raise ValidationError(self.errorMessages['wrong_classtype'] % {'value': value})
      return inspectKlass
    elif(self.required):
      raise ValidationError(self.errorMessages['invalid'] % {'value': value})
    # else (value is empty and it is not required, suppress error)

class QuerysetField(Field):
  widget = QueryIdInput
  defaultErrorMessages = {
    'invalid': _('Unable to import the given queryset'),
    'dbInvalid': _('Unable to find data({value}) in DB'),
    'appInvalid': _('No app has been set'),
    'mdlInvalid': _('No model has been set'),
    'configInvalid': _('Configuration has been invalid'),
  }

  def __init__(self, appName=None, mdlName=None, maxLen=-1, *args, **kwargs):
    super(QuerysetField, self).__init__(*args, **kwargs)
    self._appName = appName
    self._mdlName = mdlName
    self.maxLen = maxLen
    # values may be valid at the beginning, but may be invalid after db
    # operation, so we allow data to be checked at the beginning.
    # Use case: modelTblDel fills a valid id, then the cmd delete the object,
    # but the reactor try to export the form for history which called form's
    # toPython to clean the data again. The valid object is already checked
    # and deleted, but if we clean/check the object id again, it will become
    # invalid if we don't have dbCleanData
    self.dbCleanData = set()

  @property
  def appName(self):
    return self._appName

  @appName.setter
  def appName(self, appName):
    self._appName = appName
    if not isclass(self.widget):
      # When form level app change, widget's ref should also be changed
      self.widget.attrs["appName"] = appName
      # force reset
      self.widget.fieldSetter({"finalData": None})
      self.dbCleanData = set()

  @property
  def mdlName(self):
    return self._mdlName

  @mdlName.setter
  def mdlName(self, mdlName):
    self._mdlName = mdlName
    if not isclass(self.widget):
      # When form level app change, widget's ref should also be changed
      self.widget.attrs["mdlName"] = mdlName
      # force reset
      self.widget.fieldSetter({"finalData": None})
      self.dbCleanData = set()

  def clean(self, value, isEmptyForgiven=False):
    """
    Validates the given value and returns its "cleaned" value as an
    appropriate Python object.

    Raises ValidationError for any errors.
    """
    if not isclass(self.widget):
      # We don't clean anything in GUI. We trust data from server
      return value

    self.validate(value)
    self.runValidators(value)

    if not value:
      return []

    if self.maxLen == 1:
      if value is None or value == "None":
        return value
      elif type(value.__class__.__bases__[0]).__name__ == "ModelBase":
        return value.id

    try:
      dbClass = importClass('{0}.model.{1}'.format(
        self.appName,
        self.mdlName
        )
      )
      if self.maxLen == 1:
        if value in self.dbCleanData:
          return value
        else:
          # We are not actually return the new queryset, instead, we just check if
          # the id set is in the given queryset
          if dbClass.objects.filter(id=value).count() == 0:
            raise ValidationError(
                self.errorMessages['dbInvalid'].format(value=value)
            )
          self.dbCleanData.add(value)
      else:
        if self.dbCleanData >= set(value):
          # all values already checked before
          return value
        if len(value) != dbClass.objects.filter(id__in=value).count():
          raise ValidationError(
              self.errorMessages['dbInvalid'].format(value=value)
          )
        for i in value:
          self.dbCleanData.add(i)

    except Exception as e:
      import logging
      logger = logging.getLogger(__name__)
      logger.error(e, exc_info=True)
      raise ValidationError(
          self.errorMessages['dbInvalid'].format(value=value)
      )

    return value

  def validate(self, value):
    """
    Validates if the input exists in the db
    """
    if self.required and not value:
      raise ValidationError(self.errorMessages['invalid'])

    if isclass(self.widget):
      return True

    if self.required:
      if self.appName is None:
        raise ValidationError(
            self.errorMessages['appInvalid'] % {'value': value}
        )
      if self.mdlName is None:
        raise ValidationError(
            self.errorMessages['mdlInvalid'] % {'value': value}
        )

    return True

  def toPython(self, value):
    if value is None or value == []:
      return value
    elif self.maxLen == 1:
      return str(value)
    else:
      return [str(i) for i in value]

  def getModelFieldNameSuffix(self):
    if self.maxLen == 1:
      return "Id"
    else:
      return "__m2m"

  @property
  def finalData(self):
    """It is used to store data directly from widget before validation and
    cleaning."""
    # TODO: allow lazy update
    if self._finalData in validators.EMPTY_VALUES:
      if isclass(self.widget):
        # return initial data if widget has not been rendered and finalData
        # is empty
        return self.initData
      else:
        # force update
        self.widget.updateField()

    # That is when we want data as pk instead of queryset
    if self.maxLen == 1 \
        and self._finalData is not None \
        and isinstance(self._finalData, list):
      return self._finalData[0]
    else:
      return self._finalData

  @finalData.setter
  def finalData(self, finalData):
    if self.maxLen == 1 and not isinstance(finalData, list):
      # Since we use QueryIdInput, we have to store data and take input as qs.
      # Output will be int though
      finalData = [finalData,]
    self._finalData = finalData

  def renderWidget(self, *args, **kwargs):
    if("attrs" not in kwargs):
      kwargs["attrs"] = {}
    kwargs["attrs"].update({
      "appName": self.appName,
      "mdlName": self.mdlName
    })
    super(QuerysetField, self).renderWidget(*args, **kwargs)

class BinaryField(Field):
  widget = None

  def renderWidget(self, *args, **kwargs):
    pass

class GeoPointField(TextField):

  @property
  def initData(self):
    return self._initData

  @initData.setter
  def initData(self, initData):
    self._initData = str(initData)

  def toPython(self, value):
    if value in validators.EMPTY_VALUES:
      return None
    try:
      value = jsonLoads(value)
      if(len(value)!=2):
        raise
      for i in value:
        if(not isinstance(i, (int, float))):
          raise
    except:
      return None
    return value
