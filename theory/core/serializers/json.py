"""
Serialize data to/from JSON
"""

# Avoid shadowing the standard library json module
from __future__ import absolute_import
from __future__ import unicode_literals

import datetime
import decimal
import json
import sys

from theory.core.serializers.base import DeserializationError
from theory.core.serializers.python import Serializer as PythonSerializer
from theory.core.serializers.python import Deserializer as PythonDeserializer
from theory.utils import six
from theory.utils.timezone import isAware


class Serializer(PythonSerializer):
  """
  Convert a queryset to JSON.
  """
  internalUseOnly = False

  def startSerialization(self):
    if json.__version__.split('.') >= ['2', '1', '3']:
      # Use JS strings to represent Python Decimal instances (ticket #16850)
      self.options.update({'useDecimal': False})
    self._current = None
    self.jsonKwargs = self.options.copy()
    self.jsonKwargs.pop('stream', None)
    self.jsonKwargs.pop('fields', None)
    if self.options.get('indent'):
      # Prevent trailing spaces
      self.jsonKwargs['separators'] = (',', ': ')
    self.stream.write("[")

  def endSerialization(self):
    if self.options.get("indent"):
      self.stream.write("\n")
    self.stream.write("]")
    if self.options.get("indent"):
      self.stream.write("\n")

  def endObject(self, obj):
    # self._current has the field data
    indent = self.options.get("indent")
    if not self.first:
      self.stream.write(",")
      if not indent:
        self.stream.write(" ")
    if indent:
      self.stream.write("\n")
    json.dump(self.getDumpObject(obj), self.stream,
         cls=TheoryJSONEncoder, **self.jsonKwargs)
    self._current = None

  def getvalue(self):
    # Grand-parent super
    return super(PythonSerializer, self).getvalue()


def Deserializer(streamOrString, **options):
  """
  Deserialize a stream or string of JSON data.
  """
  if not isinstance(streamOrString, (bytes, six.stringTypes)):
    streamOrString = streamOrString.read()
  if isinstance(streamOrString, bytes):
    streamOrString = streamOrString.decode('utf-8')
  try:
    objects = json.loads(streamOrString)
    for obj in PythonDeserializer(objects, **options):
      yield obj
  except GeneratorExit:
    raise
  except Exception as e:
    # Map to deserializer error
    six.reraise(DeserializationError, DeserializationError(e), sys.exc_info()[2])


class TheoryJSONEncoder(json.JSONEncoder):
  """
  JSONEncoder subclass that knows how to encode date/time and decimal types.
  """
  def default(self, o):
    # See "Date Time String Format" in the ECMA-262 specification.
    if isinstance(o, datetime.datetime):
      r = o.isoformat()
      if o.microsecond:
        r = r[:23] + r[26:]
      if r.endswith('+00:00'):
        r = r[:-6] + 'Z'
      return r
    elif isinstance(o, datetime.date):
      return o.isoformat()
    elif isinstance(o, datetime.time):
      if isAware(o):
        raise ValueError("JSON can't represent timezone-aware times.")
      r = o.isoformat()
      if o.microsecond:
        r = r[:12]
      return r
    elif isinstance(o, decimal.Decimal):
      return str(o)
    else:
      return super(TheoryJSONEncoder, self).default(o)

# Older, deprecated class name (for backwards compatibility purposes).
DateTimeAwareJSONEncoder = TheoryJSONEncoder
