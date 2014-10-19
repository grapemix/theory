"""
YAML serializer.

Requires PyYaml (http://pyyaml.org/), but that's checked for in __init__.
"""

import decimal
import yaml
import sys
from io import StringIO

from theory.db import model
from theory.core.serializers.base import DeserializationError
from theory.core.serializers.python import Serializer as PythonSerializer
from theory.core.serializers.python import Deserializer as PythonDeserializer
from theory.utils import six

# Use the C (faster) implementation if possible
try:
  from yaml import CSafeLoader as SafeLoader
  from yaml import CSafeDumper as SafeDumper
except ImportError:
  from yaml import SafeLoader, SafeDumper


class TheorySafeDumper(SafeDumper):
  def represent_decimal(self, data):
    return self.representScalar('tag:yaml.org,2002:str', str(data))

TheorySafeDumper.add_representer(decimal.Decimal, TheorySafeDumper.represent_decimal)


class Serializer(PythonSerializer):
  """
  Convert a queryset to YAML.
  """

  internalUseOnly = False

  def handleField(self, obj, field):
    # A nasty special case: base YAML doesn't support serialization of time
    # types (as opposed to dates or datetimes, which it does support). Since
    # we want to use the "safe" serializer for better interoperability, we
    # need to do something with those pesky times. Converting 'em to strings
    # isn't perfect, but it's better than a "!!python/time" type which would
    # halt deserialization under any other language.
    if isinstance(field, model.TimeField) and getattr(obj, field.name) is not None:
      self._current[field.name] = str(getattr(obj, field.name))
    else:
      super(Serializer, self).handleField(obj, field)

  def endSerialization(self):
    yaml.dump(self.objects, self.stream, Dumper=TheorySafeDumper, **self.options)

  def getvalue(self):
    # Grand-parent super
    return super(PythonSerializer, self).getvalue()


def Deserializer(streamOrString, **options):
  """
  Deserialize a stream or string of YAML data.
  """
  if isinstance(streamOrString, bytes):
    streamOrString = streamOrString.decode('utf-8')
  if isinstance(streamOrString, six.stringTypes):
    stream = StringIO(streamOrString)
  else:
    stream = streamOrString
  try:
    for obj in PythonDeserializer(yaml.load(stream, Loader=SafeLoader), **options):
      yield obj
  except GeneratorExit:
    raise
  except Exception as e:
    # Map to deserializer error
    six.reraise(DeserializationError, DeserializationError(e), sys.excInfo()[2])
