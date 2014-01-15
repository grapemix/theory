# -*- coding: utf-8 -*-
##### System wide lib #####

##### Theory lib #####
from theory.conf import settings
from theory.utils import importlib
from theory.utils import six
from theory.utils.serializer.base import SerializerDoesNotExist

##### Theory third-party lib #####

##### Local app #####

##### Theory app #####

##### Misc #####

"""
Interfaces for serializing Theory objects.

Usage::

  from theory.utils import serializer
  json = serializer.serialize("json", some_query_set)
  objects = list(serializer.deserialize("json", json))

To add your own serializers, use the SERIALIZATION_MODULES setting::

  SERIALIZATION_MODULES = {
    "csv" : "path.to.csv.serializer",
    "txt" : "path.to.txt.serializer",
  }

"""

# Built-in serializers
BUILTIN_SERIALIZERS = {
  "json"   : "theory.utils.serializer.json",
}

_serializers = {}

def registerSerializer(format, serializer_module, serializers=None):
  """Register a new serializer.

  ``serializer_module`` should be the fully qualified module name
  for the serializer.

  If ``serializers`` is provided, the registration will be added
  to the provided dictionary.

  If ``serializers`` is not provided, the registration will be made
  directly into the global register of serializers. Adding serializers
  directly is not a thread-safe operation.
  """
  if serializers is None and not _serializers:
    _loadSerializers()
  module = importlib.import_module(serializer_module)
  if serializers is None:
    _serializers[format] = module
  else:
    serializers[format] = module

def unregisterSerializer(format):
  "Unregister a given serializer. This is not a thread-safe operation."
  if not _serializers:
    _loadSerializers()
  if format not in _serializers:
    raise SerializerDoesNotExist(format)
  del _serializers[format]

def getSerializer(format):
  if not _serializers:
    _loadSerializers()
  if format not in _serializers:
    raise SerializerDoesNotExist(format)
  return _serializers[format].Serializer

def getSerializerFormats():
  if not _serializers:
    _loadSerializers()
  return list(_serializers)

def getPublicSerializerFormats():
  if not _serializers:
    _loadSerializers()
  return [k for k, v in six.iteritems(_serializers) if not v.Serializer.internal_use_only]

def getDeserializer(format):
  if not _serializers:
    _loadSerializers()
  if format not in _serializers:
    raise SerializerDoesNotExist(format)
  return _serializers[format].Deserializer

def serialize(format, queryset, **options):
  """
  Serialize a queryset (or any iterator that returns database objects) using
  a certain serializer.
  """
  s = getSerializer(format)()
  s.serialize(queryset, **options)
  return s.getvalue()

def deserialize(format, stream_or_string, **options):
  """
  Deserialize a stream or a string. Returns an iterator that yields ``(obj
  )``, where ``obj`` is a instantiated -- but *unsaved* --
  object.
  """
  d = getDeserializer(format)
  return d(stream_or_string, **options)

def _loadSerializers():
  """
  Register built-in and settings-defined serializers. This is done lazily so
  that user code has a chance to (e.g.) set up custom settings without
  needing to be careful of import order.
  """
  global _serializers
  serializers = {}
  for format in BUILTIN_SERIALIZERS:
    registerSerializer(format, BUILTIN_SERIALIZERS[format], serializers)
  if hasattr(settings, "SERIALIZATION_MODULES"):
    for format in settings.SERIALIZATION_MODULES:
      registerSerializer(format, settings.SERIALIZATION_MODULES[format], serializers)
  _serializers = serializers
