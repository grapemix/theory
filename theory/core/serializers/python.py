"""
A Python "serializer". Doesn't do much serializing per se -- just converts to
and from basic Python data types (lists, dicts, strings, etc.). Useful as a basis for
other serializers.
"""
from __future__ import unicode_literals

from theory.apps import apps
from theory.conf import settings
from theory.core.serializers import base
from theory.db import model, DEFAULT_DB_ALIAS
from theory.utils.encoding import smartText, isProtectedType
from theory.utils import six


class Serializer(base.Serializer):
  """
  Serializes a QuerySet to basic Python objects.
  """

  internalUseOnly = True

  def startSerialization(self):
    self._current = None
    self.objects = []

  def endSerialization(self):
    pass

  def startObject(self, obj):
    self._current = {}

  def endObject(self, obj):
    self.objects.append(self.getDumpObject(obj))
    self._current = None

  def getDumpObject(self, obj):
    data = {
      "model": smartText(obj._meta),
      "fields": self._current,
    }
    if not self.useNaturalPrimaryKeys or not hasattr(obj, 'naturalKey'):
      data["pk"] = smartText(obj._getPkVal(), stringsOnly=True)

    return data

  def handleField(self, obj, field):
    value = field._getValFromObj(obj)
    # Protected types (i.e., primitives like None, numbers, dates,
    # and Decimals) are passed through as is. All other values are
    # converted to string first.
    if isProtectedType(value):
      self._current[field.name] = value
    else:
      self._current[field.name] = field.valueToString(obj)

  def handleFkField(self, obj, field):
    if self.useNaturalForeignKeys and hasattr(field.rel.to, 'naturalKey'):
      related = getattr(obj, field.name)
      if related:
        value = related.naturalKey()
      else:
        value = None
    else:
      value = getattr(obj, field.getAttname())
    self._current[field.name] = value

  def handleM2mField(self, obj, field):
    if field.rel.through._meta.autoCreated:
      if self.useNaturalForeignKeys and hasattr(field.rel.to, 'naturalKey'):
        m2mValue = lambda value: value.naturalKey()
      else:
        m2mValue = lambda value: smartText(value._getPkVal(), stringsOnly=True)
      self._current[field.name] = [m2mValue(related)
                for related in getattr(obj, field.name).iterator()]

  def getvalue(self):
    return self.objects


def Deserializer(objectList, **options):
  """
  Deserialize simple Python objects back into Theory ORM instances.

  It's expected that you pass the Python objects themselves (instead of a
  stream or a string) to the constructor
  """
  db = options.pop('using', DEFAULT_DB_ALIAS)
  ignore = options.pop('ignorenonexistent', False)

  for d in objectList:
    # Look up the model and starting build a dict of data for it.
    try:
      Model = _getModel(d["model"])
    except base.DeserializationError:
      if ignore:
        continue
      else:
        raise
    data = {}
    if 'pk' in d:
      data[Model._meta.pk.attname] = Model._meta.pk.toPython(d.get("pk", None))
    m2mData = {}
    modelFields = Model._meta.getAllFieldNames()

    # Handle each field
    for (fieldName, fieldValue) in six.iteritems(d["fields"]):

      if ignore and fieldName not in modelFields:
        # skip fields no longer on model
        continue

      if isinstance(fieldValue, str):
        fieldValue = smartText(fieldValue, options.get("encoding", settings.DEFAULT_CHARSET), stringsOnly=True)

      field = Model._meta.getField(fieldName)

      # Handle M2M relations
      if field.rel and isinstance(field.rel, model.ManyToManyRel):
        if hasattr(field.rel.to._defaultManager, 'getByNaturalKey'):
          def m2mConvert(value):
            if hasattr(value, '__iter__') and not isinstance(value, six.textType):
              return field.rel.to._defaultManager.dbManager(db).getByNaturalKey(*value).pk
            else:
              return smartText(field.rel.to._meta.pk.toPython(value))
        else:
          m2mConvert = lambda v: smartText(field.rel.to._meta.pk.toPython(v))
        m2mData[field.name] = [m2mConvert(pk) for pk in fieldValue]

      # Handle FK fields
      elif field.rel and isinstance(field.rel, model.ManyToOneRel):
        if fieldValue is not None:
          if hasattr(field.rel.to._defaultManager, 'getByNaturalKey'):
            if hasattr(fieldValue, '__iter__') and not isinstance(fieldValue, six.textType):
              obj = field.rel.to._defaultManager.dbManager(db).getByNaturalKey(*fieldValue)
              value = getattr(obj, field.rel.fieldName)
              # If this is a natural foreign key to an object that
              # has a FK/O2O as the foreign key, use the FK value
              if field.rel.to._meta.pk.rel:
                value = value.pk
            else:
              value = field.rel.to._meta.getField(field.rel.fieldName).toPython(fieldValue)
            data[field.attname] = value
          else:
            data[field.attname] = field.rel.to._meta.getField(field.rel.fieldName).toPython(fieldValue)
        else:
          data[field.attname] = None

      # Handle all other fields
      else:
        data[field.name] = field.toPython(fieldValue)

    obj = base.buildInstance(Model, data, db)
    yield base.DeserializedObject(obj, m2mData)


def _getModel(modelIdentifier):
  """
  Helper to look up a model from an "appLabel.modelName" string.
  """
  try:
    return apps.getModel(modelIdentifier)
  except (LookupError, TypeError):
    raise base.DeserializationError("Invalid model identifier: '%s'" % modelIdentifier)
