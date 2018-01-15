# -*- coding: utf-8 -*-
#!/usr/bin/env python
##### System wide lib #####

##### Theory lib #####
from theory.utils import six

##### Theory third-party lib #####

##### Local app #####

##### Theory app #####

##### Misc #####


"""
Module for abstract serializer/unserializer base classes.
"""
class SerializerDoesNotExist(KeyError):
  """The requested serializer was not found."""
  pass

class SerializationError(Exception):
  """Something bad happened during serialization."""
  pass

class DeserializationError(Exception):
  """Something bad happened during deserialization."""
  pass

class Serializer(object):
  """
  Abstract serializer base class.
  """

  def serialize(self, queryset, **options):
    """
    Serialize a queryset.
    """
    raise NotImplementedError

  def startSerialization(self):
    """
    Called when serializing of the queryset starts.
    """
    raise NotImplementedError

  def endSerialization(self):
    """
    Called when serializing of the queryset ends.
    """
    pass

  def startObject(self, obj):
    """
    Called when serializing of an object starts.
    """
    raise NotImplementedError

  def endObject(self, obj):
    """
    Called when serializing of an object ends.
    """
    pass

  def handleField(self, obj, field):
    """
    Called to handle each individual (non-relational) field on an object.
    """
    raise NotImplementedError

  def handleFkField(self, obj, field):
    """
    Called to handle a ForeignKey field.
    """
    raise NotImplementedError

  def handleM2mField(self, obj, field):
    """
    Called to handle a ManyToManyField.
    """
    raise NotImplementedError

  def getvalue(self):
    """
    Return the fully serialized queryset (or None if the output stream is
    not seekable).
    """
    if callable(getattr(self.stream, 'getvalue', None)):
      return self.stream.getvalue()

class Deserializer(six.Iterator):
  """
  Abstract base deserializer class.
  """

  def __init__(self, streamOrString, **options):
    """
    Init this serializer given a stream or a string
    """
    self.options = options
    if isinstance(streamOrString, six.string_types):
      self.stream = six.StringIO(streamOrString)
    else:
      self.stream = stream_or_string

  def __iter__(self):
    return self

  def __next__(self):
    """Iteration iterface -- return the next item in the stream"""
    raise NotImplementedError

class DeserializedObject(object):
  """
  A deserialized model.

  Basically a container for holding the pre-saved deserialized data along
  with the reference data saved with the object.
  """

  def __init__(self, obj):
    self.object = obj

  def __repr__(self):
    return "<DeserializedObject: %s(pk=%s)>" % (
        self.object._meta.app_label,
        self.object._meta.__class__,
        self.object.id
        )

  def save(self):
    raise NotImplementedError
