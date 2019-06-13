# -*- coding: utf-8 -*-
#!/usr/bin/env python
##### System wide lib #####
# Avoid shadowing the standard library json module
from __future__ import absolute_import

import datetime as dt
import decimal
import json
from uuid import UUID

##### Theory lib #####
from theory.utils.timezone import isAware

##### Theory third-party lib #####

##### Local app #####

##### Theory app #####

##### Misc #####

class TheoryJSONEncoder(json.JSONEncoder):
  """
  JSONEncoder subclass that knows how to encode date/time and decimal types.
  """
  def default(self, o):
    from theory.db.model.query import QuerySet
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
      if isAware(o):
        raise ValueError("JSON can't represent timezone-aware times.")
      r = o.isoformat()
      if o.microsecond:
        r = r[:12]
      return r
    elif isinstance(o, decimal.Decimal) or isinstance(o, UUID):
      return str(o)
    elif type(o.__class__.__bases__[0]).__name__ == "ModelBase":
      module = o.__module__
      return {
          "appName": module[:module.find(".model")],
          "modelName": type(o).__name__,
          "id": str(o.id)
          }
    elif isinstance(o, QuerySet):
      module = o.modal.__module__
      return {
          "appName": module[:module.find(".model")],
          "modelName": o.modal.__name__,
          "idLst": [str(i.id) for i in o]
          }
    elif type(o).__name__ == "LocalFileObject":
      # We don't want to store the data because JSON cannot store binary
      # natively and no storing solution can provide human readibility
      return o.filepath
    elif (
      type(o).__name__ == "__proxy__"
      and str(type(o)) == (
        "<class 'theory.utils.functional.lazy.<locals>.__proxy__'>"
      )):
      return str(o)
    else:
      return super(TheoryJSONEncoder, self).default(o)
