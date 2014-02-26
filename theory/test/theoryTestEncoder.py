# -*- coding: utf-8 -*-
#!/usr/bin/env python
##### System wide lib #####
# Avoid shadowing the standard library json module
from __future__ import absolute_import

from bson import ObjectId
import datetime as dt
import decimal
import json
from uuid import UUID

##### Theory lib #####
from theory.db.models import QuerySet
from theory.utils.timezone import is_aware

##### Theory third-party lib #####

##### Local app #####

##### Theory app #####

##### Misc #####

class TheoryTestEncoder(json.JSONEncoder):
  """
  JSONEncoder subclass that for testing
  """
  def __init__(self, *args, **kwargs):
    super(TheoryTestEncoder, self).__init__(*args, **kwargs)
    if(not hasattr(self, "excludeTermLst")):
      self.excludeTermLst = []

    if(not hasattr(self, "includeTermLst")):
      self.includeTermLst = []

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
    elif(isinstance(o, decimal.Decimal) or isinstance(o, UUID)):
      return str(o)
    elif isinstance(o, QuerySet):
      return len(o)
    elif isinstance(o, ObjectId):
      return ""
    elif type(o).__name__=="LocalFileObject":
      # We don't want to store the data because JSON cannot store binary
      # natively and no storing solution can provide human readibility
      return o.filepath
    elif(len(self.includeTermLst)>0):
      return dict(
        (k, v) for k, v in o.__dict__.iteritems() \
            if k in self.includeTermLst
            )
    elif(len(self.excludeTermLst)>0):
      return dict(
        (k, v) for k, v in o.__dict__.iteritems() \
            if k not in self.excludeTermLst
            )
    else:
      return o.__dict__
