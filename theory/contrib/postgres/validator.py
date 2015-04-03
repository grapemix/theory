from theory.core.exceptions import ValidationError
from theory.core.validators import (
    MaxLengthValidator,
    MinLengthValidator,
    MaxValueValidator,
    MinValueValidator,
    )
from theory.utils.deconstruct import deconstructible
from theory.utils.translation import ungettextLazy
from theory.utils.translation import ugettextLazy as _


class ArrayMaxLengthValidator(MaxLengthValidator):
  message = ungettextLazy(
    'List contains %(showValue)d item, it should contain no more than %(limitValue)d.',
    'List contains %(showValue)d items, it should contain no more than %(limitValue)d.',
    'limitValue')


class ArrayMinLengthValidator(MinLengthValidator):
  message = ungettextLazy(
    'List contains %(showValue)d item, it should contain no fewer than %(limitValue)d.',
    'List contains %(showValue)d items, it should contain no fewer than %(limitValue)d.',
    'limitValue')

@deconstructible
class KeysValidator(object):
  """A validator designed for HStore to require/restrict keys."""

  messages = {
      'missingKeys': _('Some keys were missing: %(keys)s'),
      'extraKeys': _('Some unknown keys were provided: %(keys)s'),
  }
  strict = False

  def __init__(self, keys, strict=False, messages=None):
    self.keys = set(keys)
    self.strict = strict
    if messages is not None:
      self.messages = copy.copy(self.messages)
      self.messages.update(messages)

  def __call__(self, value):
    keys = set(value.keys())
    missingKeys = self.keys - keys
    if missingKeys:
      raise ValidationError(self.messages['missingKeys'],
          code='missingKeys',
          params={'keys': ', '.join(missingKeys)},
      )
    if self.strict:
      extraKeys = keys - self.keys
      if extraKeys:
        raise ValidationError(self.messages['extraKeys'],
            code='extraKeys',
            params={'keys': ', '.join(extraKeys)},
        )

  def __eq__(self, other):
    return (
        isinstance(other, self.__class__)
        and (self.keys == other.keys)
        and (self.messages == other.messages)
        and (self.strict == other.strict)
    )

  def __ne__(self, other):
    return not (self == other)

