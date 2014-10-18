from theory.core.validators import MaxLengthValidator, MinLengthValidator
from theory.utils.translation import ungettextLazy


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
