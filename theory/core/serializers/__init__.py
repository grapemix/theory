"""
Interfaces for serializing Theory objects.

Usage::

  from theory.core import serializers
  json = serializers.serialize("json", someQueryset)
  objects = list(serializers.deserialize("json", json))

To add your own serializers, use the SERIALIZATION_MODULES setting::

  SERIALIZATION_MODULES = {
    "csv": "path.to.csv.serializer",
    "txt": "path.to.txt.serializer",
  }

"""

import importlib

from theory.conf import settings
from theory.utils import six
from theory.core.serializers.base import SerializerDoesNotExist

# Built-in serializers
BUILTIN_SERIALIZERS = {
  "xml": "theory.core.serializers.xmlSerializer",
  "python": "theory.core.serializers.python",
  "json": "theory.core.serializers.json",
  "yaml": "theory.core.serializers.pyyaml",
}

_serializers = {}


class BadSerializer(object):
  """
  Stub serializer to hold exception raised during registration

  This allows the serializer registration to cache serializers and if there
  is an error raised in the process of creating a serializer it will be
  raised and passed along to the caller when the serializer is used.
  """
  internalUseOnly = False

  def __init__(self, exception):
    self.exception = exception

  def __call__(self, *args, **kwargs):
    raise self.exception


def registerSerializer(format, serializerModule, serializers=None):
  """Register a new serializer.

  ``serializerModule`` should be the fully qualified module name
  for the serializer.

  If ``serializers`` is provided, the registration will be added
  to the provided dictionary.

  If ``serializers`` is not provided, the registration will be made
  directly into the global register of serializers. Adding serializers
  directly is not a thread-safe operation.
  """
  if serializers is None and not _serializers:
    _loadSerializers()

  try:
    module = importlib.import_module(serializerModule)
  except ImportError as exc:
    badSerializer = BadSerializer(exc)

    module = type('BadSerializerModule', (object,), {
      'Deserializer': badSerializer,
      'Serializer': badSerializer,
    })

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
  return [k for k, v in six.iteritems(_serializers) if not v.Serializer.internalUseOnly]


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


def deserialize(format, streamOrString, **options):
  """
  Deserialize a stream or a string. Returns an iterator that yields ``(obj,
  m2mRelationDict)``, where ``obj`` is an instantiated -- but *unsaved* --
  object, and ``m2mRelationDict`` is a dictionary of ``{m2mFieldName :
  listOfRelatedObjects}``.
  """
  d = getDeserializer(format)
  return d(streamOrString, **options)


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
