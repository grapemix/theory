# -*- coding: utf-8 -*-
#!/usr/bin/env python
##### System wide lib #####
import os

##### Theory lib #####
from theory.conf import settings
from theory.utils.html import conditional_escape
from theory.utils.encoding import StrAndUnicode, forceUnicode
from theory.utils.safestring import markSafe
from theory.utils import timezone
from theory.utils.translation import ugettextLazy as _

# Import ValidationError so that it can be imported from this
# module to maintain backwards compatibility.
from theory.core.exceptions import ValidationError

##### Theory third-party lib #####

##### Local app #####

##### Theory app #####

##### Misc #####

def flatatt(attrs):
  """
  Convert a dictionary of attributes to a single string.
  The returned string will contain a leading space followed by key="value",
  XML-style pairs.  It is assumed that the keys do not need to be XML-escaped.
  If the passed dictionary is empty, then return an empty string.
  """
  return u''.join([u' %s="%s"' % (k, conditional_escape(v)) for k, v in attrs.items()])

class ErrorDict(dict, StrAndUnicode):
  """
  A collection of errors that knows how to display itself in various formats.

  The dictionary keys are the field names, and the values are the errors.
  """
  def __unicode__(self):
    return self.as_ul()

  def as_ul(self):
    if not self: return u''
    return mark_safe(u'<ul class="errorlist">%s</ul>'
        % ''.join([u'<li>%s%s</li>' % (k, conditional_escape(forceUnicode(v)))
          for k, v in self.items()]))

  def as_text(self):
    return u'\n'.join([u'* %s\n%s' % (k, u'\n'.join([u'  * %s' % forceUnicode(i) for i in v])) for k, v in self.items()])

class ErrorList(list, StrAndUnicode):
  """
  A collection of errors that knows how to display itself in various formats.
  """
  def __unicode__(self):
    return self.as_ul()

  def as_ul(self):
    if not self: return u''
    return mark_safe(u'<ul class="errorlist">%s</ul>'
        % ''.join([u'<li>%s</li>' % conditional_escape(forceUnicode(e)) for e in self]))

  def as_text(self):
    if not self: return u''
    return u'\n'.join([u'* %s' % forceUnicode(e) for e in self])

  def __repr__(self):
    return repr([forceUnicode(e) for e in self])

# Utilities for time zone support in DateTimeField et al.

def from_current_timezone(value):
  """
  When time zone support is enabled, convert naive datetimes
  entered in the current time zone to aware datetimes.
  """
  if settings.USE_TZ and value is not None and timezone.is_naive(value):
    current_timezone = timezone.get_current_timezone()
    try:
      return timezone.make_aware(value, current_timezone)
    except Exception, e:
      raise ValidationError(_('%(datetime)s couldn\'t be interpreted '
                  'in time zone %(current_timezone)s; it '
                  'may be ambiguous or it may not exist.')
                 % {'datetime': value,
                   'current_timezone': current_timezone})
  return value

def to_current_timezone(value):
  """
  When time zone support is enabled, convert aware datetimes
  to naive dateimes in the current time zone for display.
  """
  if settings.USE_TZ and value is not None and timezone.is_aware(value):
    current_timezone = timezone.get_current_timezone()
    return timezone.make_naive(value, current_timezone)
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
