# -*- coding: utf-8 -*-
#!/usr/bin/env python
##### System wide lib #####
# Avoid shadowing the standard library json module
from __future__ import absolute_import

import datetime as dt
import decimal
import json

##### Theory lib #####
from theory.utils.serializer.base import DeserializationError
from theory.utils.serializer.base import Serializer as BaseSerializer
from theory.utils.serializer.base import Deserializer as BaseDeserializer
from theory.utils import six
from theory.utils.timezone import is_aware

##### Theory third-party lib #####

##### Local app #####

##### Theory app #####

##### Misc #####

"""
Serialize data to/from JSON
"""

class Serializer(BaseSerializer):
  """
  Convert a queryset to JSON.
  """

  def serialize(self, queryset, **options):
    return queryset.to_json()

def Deserializer(stream_or_string, **options):
  """
  Deserialize a stream or string of JSON data.
  """
  try:
    objects = json.loads(stream_or_string)
    # MyDoc.objects.from_json(string)
    for obj in BaseDeserializer(objects, **options):
      yield obj
  except GeneratorExit:
    raise
  except Exception as e:
    # Map to deserializer error
    raise DeserializationError(e)


class TheoryJSONEncoder(json.JSONEncoder):
  """
  JSONEncoder subclass that knows how to encode date/time and decimal types.
  """
  def default(self, o):
    # See "Date Time String Format" in the ECMA-262 specification.
    if isinstance(o, dt.datetime):
      r = o.isoformat()
      if o.microsecond:
        r = r[:23] + r[26:]
      if r.endswith('+00:00'):
        r = r[:-6] + 'Z'
      return r
    elif isinstance(o, dt.date):
      return o.isoformat()
    elif isinstance(o, dt.time):
      if is_aware(o):
        raise ValueError("JSON can't represent timezone-aware times.")
      r = o.isoformat()
      if o.microsecond:
        r = r[:12]
      return r
    elif isinstance(o, decimal.Decimal):
      return str(o)
    else:
      return super(TheoryJSONEncoder, self).default(o)
