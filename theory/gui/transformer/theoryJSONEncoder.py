# -*- coding: utf-8 -*-
#!/usr/bin/env python
##### System wide lib #####
# Avoid shadowing the standard library json module
from __future__ import absolute_import

import datetime as dt
import decimal
import json

##### Theory lib #####
from theory.db.models import QuerySet
from theory.utils.timezone import is_aware

##### Theory third-party lib #####

##### Local app #####

##### Theory app #####

##### Misc #####

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
    elif isinstance(o, QuerySet):
      return [str(i.id) for i in o]
    else:
      return super(TheoryJSONEncoder, self).default(o)