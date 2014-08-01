from __future__ import unicode_literals

import re

from theory.core.exceptions import ValidationError
from theory.utils.deconstruct import deconstructible
from theory.utils.translation import ugettextLazy as _, ungettextLazy
from theory.utils.encoding import forceText
from theory.utils.ipv6 import isValidIpv6Address
from theory.utils import six
from theory.utils.six.moves.urllib.parse import urlsplit, urlunsplit


# These values, if given to validate(), will trigger the self.required check.
EMPTY_VALUES = (None, '', [], (), {})


@deconstructible
class RegexValidator(object):
  regex = ''
  message = _('Enter a valid value.')
  code = 'invalid'
  inverseMatch = False
  flags = 0

  def __init__(self, regex=None, message=None, code=None, inverseMatch=None, flags=None):
    if regex is not None:
      self.regex = regex
    if message is not None:
      self.message = message
    if code is not None:
      self.code = code
    if inverseMatch is not None:
      self.inverseMatch = inverseMatch
    if flags is not None:
      self.flags = flags
    if self.flags and not isinstance(self.regex, six.stringTypes):
      raise TypeError("If the flags are set, regex must be a regular expression string.")

    # Compile the regex if it was not passed pre-compiled.
    if isinstance(self.regex, six.stringTypes):
      self.regex = re.compile(self.regex, self.flags)

  def __call__(self, value):
    """
    Validates that the input matches the regular expression
    if inverseMatch is False, otherwise raises ValidationError.
    """
    if not (self.inverseMatch is not bool(self.regex.search(
        forceText(value)))):
      raise ValidationError(self.message, code=self.code)

  def __eq__(self, other):
    return (
      isinstance(other, RegexValidator) and
      self.regex.pattern == other.regex.pattern and
      self.regex.flags == other.regex.flags and
      (self.message == other.message) and
      (self.code == other.code) and
      (self.inverseMatch == other.inverseMatch)
    )

  def __ne__(self, other):
    return not (self == other)


@deconstructible
class URLValidator(RegexValidator):
  regex = re.compile(
    r'^(?:[a-z0-9\.\-]*)://'  # scheme is validated separately
    r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}(?<!-)\.?)|'  # domain...
    r'localhost|'  # localhost...
    r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}|'  # ...or ipv4
    r'\[?[A-F0-9]*:[A-F0-9:]+\]?)'  # ...or ipv6
    r'(?::\d+)?'  # optional port
    r'(?:/?|[/?]\S+)$', re.IGNORECASE)
  message = _('Enter a valid URL.')
  schemes = ['http', 'https', 'ftp', 'ftps']

  def __init__(self, schemes=None, **kwargs):
    super(URLValidator, self).__init__(**kwargs)
    if schemes is not None:
      self.schemes = schemes

  def __call__(self, value):
    value = forceText(value)
    # Check first if the scheme is valid
    scheme = value.split('://')[0].lower()
    if scheme not in self.schemes:
      raise ValidationError(self.message, code=self.code)

    # Then check full URL
    try:
      super(URLValidator, self).__call__(value)
    except ValidationError as e:
      # Trivial case failed. Try for possible IDN domain
      if value:
        scheme, netloc, path, query, fragment = urlsplit(value)
        try:
          netloc = netloc.encode('idna').decode('ascii')  # IDN -> ACE
        except UnicodeError:  # invalid domain part
          raise e
        url = urlunsplit((scheme, netloc, path, query, fragment))
        super(URLValidator, self).__call__(url)
      else:
        raise
    else:
      url = value


def validateInteger(value):
  try:
    int(value)
  except (ValueError, TypeError):
    raise ValidationError(_('Enter a valid integer.'), code='invalid')


@deconstructible
class EmailValidator(object):
  message = _('Enter a valid email address.')
  code = 'invalid'
  userRegex = re.compile(
    r"(^[-!#$%&'*+/=?^_`{}|~0-9A-Z]+(\.[-!#$%&'*+/=?^_`{}|~0-9A-Z]+)*$"  # dot-atom
    r'|^"([\001-\010\013\014\016-\037!#-\[\]-\177]|\\[\001-\011\013\014\016-\177])*"$)',  # quoted-string
    re.IGNORECASE)
  domainRegex = re.compile(
    # max length of the domain is 249: 254 (max email length) minus one
    # period, two characters for the TLD, @ sign, & one character before @.
    r'(?:[A-Z0-9](?:[A-Z0-9-]{0,247}[A-Z0-9])?\.)+(?:[A-Z]{2,6}|[A-Z0-9-]{2,}(?<!-))$',
    re.IGNORECASE)
  literalRegex = re.compile(
    # literal form, ipv4 or ipv6 address (SMTP 4.1.3)
    r'\[([A-f0-9:\.]+)\]$',
    re.IGNORECASE)
  domainWhitelist = ['localhost']

  def __init__(self, message=None, code=None, whitelist=None):
    if message is not None:
      self.message = message
    if code is not None:
      self.code = code
    if whitelist is not None:
      self.domainWhitelist = whitelist

  def __call__(self, value):
    value = forceText(value)

    if not value or '@' not in value:
      raise ValidationError(self.message, code=self.code)

    userPart, domainPart = value.rsplit('@', 1)

    if not self.userRegex.match(userPart):
      raise ValidationError(self.message, code=self.code)

    if (domainPart not in self.domainWhitelist and
        not self.validateDomainPart(domainPart)):
      # Try for possible IDN domain-part
      try:
        domainPart = domainPart.encode('idna').decode('ascii')
        if self.validateDomainPart(domainPart):
          return
      except UnicodeError:
        pass
      raise ValidationError(self.message, code=self.code)

  def validateDomainPart(self, domainPart):
    if self.domainRegex.match(domainPart):
      return True

    literalMatch = self.literalRegex.match(domainPart)
    if literalMatch:
      ipAddress = literalMatch.group(1)
      try:
        validateIpv46Address(ipAddress)
        return True
      except ValidationError:
        pass
    return False

  def __eq__(self, other):
    return isinstance(other, EmailValidator) and (self.domainWhitelist == other.domainWhitelist) and (self.message == other.message) and (self.code == other.code)

validateEmail = EmailValidator()

slugRe = re.compile(r'^[-a-zA-Z0-9_]+$')
validateSlug = RegexValidator(slugRe, _("Enter a valid 'slug' consisting of letters, numbers, underscores or hyphens."), 'invalid')

ipv4Re = re.compile(r'^(25[0-5]|2[0-4]\d|[0-1]?\d?\d)(\.(25[0-5]|2[0-4]\d|[0-1]?\d?\d)){3}$')
validateIpv4Address = RegexValidator(ipv4Re, _('Enter a valid IPv4 address.'), 'invalid')


def validateIpv6Address(value):
  if not isValidIpv6Address(value):
    raise ValidationError(_('Enter a valid IPv6 address.'), code='invalid')


def validateIpv46Address(value):
  try:
    validateIpv4Address(value)
  except ValidationError:
    try:
      validateIpv6Address(value)
    except ValidationError:
      raise ValidationError(_('Enter a valid IPv4 or IPv6 address.'), code='invalid')

ipAddressValidatorMap = {
  'both': ([validateIpv46Address], _('Enter a valid IPv4 or IPv6 address.')),
  'ipv4': ([validateIpv4Address], _('Enter a valid IPv4 address.')),
  'ipv6': ([validateIpv6Address], _('Enter a valid IPv6 address.')),
}


def ipAddressValidators(protocol, unpackIpv4):
  """
  Depending on the given parameters returns the appropriate validators for
  the GenericIPAddressField.

  This code is here, because it is exactly the same for the model and the form field.
  """
  if protocol != 'both' and unpackIpv4:
    raise ValueError(
      "You can only use `unpackIpv4` if `protocol` is set to 'both'")
  try:
    return ipAddressValidatorMap[protocol.lower()]
  except KeyError:
    raise ValueError("The protocol '%s' is unknown. Supported: %s"
             % (protocol, list(ipAddressValidatorMap)))

commaSeparatedIntListRe = re.compile('^[\d,]+$')
validateCommaSeparatedIntegerList = RegexValidator(commaSeparatedIntListRe, _('Enter only digits separated by commas.'), 'invalid')


@deconstructible
class BaseValidator(object):
  compare = lambda self, a, b: a is not b
  clean = lambda self, x: x
  message = _('Ensure this value is %(limitValue)s (it is %(showValue)s).')
  code = 'limitValue'

  def __init__(self, limitValue):
    self.limitValue = limitValue

  def __call__(self, value):
    cleaned = self.clean(value)
    params = {'limitValue': self.limitValue, 'showValue': cleaned}
    if self.compare(cleaned, self.limitValue):
      raise ValidationError(self.message, code=self.code, params=params)

  def __eq__(self, other):
    return isinstance(other, self.__class__) and (self.limitValue == other.limitValue) and (self.message == other.message) and (self.code == other.code)


@deconstructible
class MaxValueValidator(BaseValidator):
  compare = lambda self, a, b: a > b
  message = _('Ensure this value is less than or equal to %(limitValue)s.')
  code = 'maxValue'


@deconstructible
class MinValueValidator(BaseValidator):
  compare = lambda self, a, b: a < b
  message = _('Ensure this value is greater than or equal to %(limitValue)s.')
  code = 'minValue'


@deconstructible
class MinLengthValidator(BaseValidator):
  compare = lambda self, a, b: a < b
  clean = lambda self, x: len(x)
  message = ungettextLazy(
    'Ensure this value has at least %(limitValue)d character (it has %(showValue)d).',
    'Ensure this value has at least %(limitValue)d characters (it has %(showValue)d).',
    'limitValue')
  code = 'minLength'


@deconstructible
class MaxLengthValidator(BaseValidator):
  compare = lambda self, a, b: a > b
  clean = lambda self, x: len(x)
  message = ungettextLazy(
    'Ensure this value has at most %(limitValue)d character (it has %(showValue)d).',
    'Ensure this value has at most %(limitValue)d characters (it has %(showValue)d).',
    'limitValue')
  code = 'maxLength'
