from __future__ import unicode_literals

import json
import os
import sys

try:
  from collections import UserList
except ImportError:  # Python 2
  from UserList import UserList

from theory.conf import settings
from theory.utils.encoding import forceText, python2UnicodeCompatible
from theory.utils.html import formatHtml, formatHtmlJoin, escape
from theory.utils import timezone
from theory.utils.translation import ugettextLazy as _
from theory.utils import six

# Import ValidationError so that it can be imported from this
# module to maintain backwards compatibility.
from theory.core.exceptions import ValidationError


def flatatt(attrs):
  """
  Convert a dictionary of attributes to a single string.
  The returned string will contain a leading space followed by key="value",
  XML-style pairs.  It is assumed that the keys do not need to be XML-escaped.
  If the passed dictionary is empty, then return an empty string.

  The result is passed through 'markSafe'.
  """
  booleanAttrs = []
  for attr, value in list(attrs.items()):
    if value is True:
      booleanAttrs.append((attr,))
      del attrs[attr]
    elif value is False:
      del attrs[attr]

  return (
    formatHtmlJoin('', ' {0}="{1}"', sorted(attrs.items())) +
    formatHtmlJoin('', ' {0}', sorted(booleanAttrs))
  )


@python2UnicodeCompatible
class ErrorDict(dict):
  """
  A collection of errors that knows how to display itself in various formats.

  The dictionary keys are the field names, and the values are the errors.
  """
  def asData(self):
    return {f: e.asData() for f, e in self.items()}

  def asJson(self, escapeHtml=False):
    return json.dumps({f: e.getJsonData(escapeHtml) for f, e in self.items()})

  def asUl(self):
    if not self:
      return ''
    return formatHtml(
      '<ul class="errorlist">{0}</ul>',
      formatHtmlJoin('', '<li>{0}{1}</li>', ((k, forceText(v)) for k, v in self.items()))
    )

  def asText(self):
    output = []
    for field, errors in self.items():
      output.append('* %s' % field)
      output.append('\n'.join('  * %s' % e for e in errors))
    return '\n'.join(output)

  def __str__(self):
    return self.asUl()


@python2UnicodeCompatible
class ErrorList(UserList, list):
  """
  A collection of errors that knows how to display itself in various formats.
  """
  def __init__(self, initlist=None, errorClass=None):
    super(ErrorList, self).__init__(initlist)

    if errorClass is None:
      self.errorClass = 'errorlist'
    else:
      self.errorClass = 'errorlist {}'.format(errorClass)

  def asData(self):
    return ValidationError(self.data).errorList

  def getJsonData(self, escapeHtml=False):
    errors = []
    for error in self.asData():
      message = list(error)[0]
      errors.append({
        'message': escape(message) if escapeHtml else message,
        'code': error.code or '',
      })
    return errors

  def asJson(self, escapeHtml=False):
    return json.dumps(self.getJsonData(escapeHtml))

  def asUl(self):
    if not self.data:
      return ''

    return formatHtml(
      '<ul class="{0}">{1}</ul>',
      self.errorClass,
      formatHtmlJoin('', '<li>{0}</li>', ((forceText(e),) for e in self))
    )

  def asText(self):
    return '\n'.join('* %s' % e for e in self)

  def __str__(self):
    return self.asUl()

  def __repr__(self):
    return repr(list(self))

  def __contains__(self, item):
    return item in list(self)

  def __eq__(self, other):
    return list(self) == other

  def __ne__(self, other):
    return list(self) != other

  def __getitem__(self, i):
    error = self.data[i]
    if isinstance(error, ValidationError):
      return list(error)[0]
    return forceText(error)


# Utilities for time zone support in DateTimeField et al.

def fromCurrentTimezone(value):
  """
  When time zone support is enabled, convert naive datetimes
  entered in the current time zone to aware datetimes.
  """
  if settings.USE_TZ and value is not None and timezone.isNaive(value):
    currentTimezone = timezone.getCurrentTimezone()
    try:
      return timezone.makeAware(value, currentTimezone)
    except Exception:
      message = _(
        '%(datetime)s couldn\'t be interpreted '
        'in time zone %(currentTimezone)s; it '
        'may be ambiguous or it may not exist.'
      )
      params = {'datetime': value, 'currentTimezone': currentTimezone}
      six.reraise(ValidationError, ValidationError(
        message,
        code='ambiguousTimezone',
        params=params,
      ), sys.excInfo()[2])
  return value


def toCurrentTimezone(value):
  """
  When time zone support is enabled, convert aware datetimes
  to naive dateimes in the current time zone for display.
  """
  if settings.USE_TZ and value is not None and timezone.isAware(value):
    currentTimezone = timezone.getCurrentTimezone()
    return timezone.makeNaive(value, currentTimezone)
  return value

class LocalFileObject(object):
  def __init__(self, filepath):
    self.name = os.path.split(filepath)[-1]
    self.filepath = filepath
    self.storage = {}
    try:
      self.size = os.path.getsize(filepath)
      with open(filepath, 'rb') as f:
        self.storage["content"] = f.read()
    except:
      self.size = 0

  def __getitem__(self, key):
    return self.storage[key]

  def __unicode__(self):
    return unicode(self.filepath)
