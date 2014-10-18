"""
Module for abstract serializer/unserializer base classes.
"""
import warnings

from theory.db import model
from theory.utils import six
from theory.utils.deprecation import RemovedInTheory19Warning


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

  # Indicates if the implemented serializer is only available for
  # internal Theory use.
  internalUseOnly = False

  def serialize(self, queryset, **options):
    """
    Serialize a queryset.
    """
    self.options = options

    self.stream = options.pop("stream", six.StringIO())
    self.selectedFields = options.pop("fields", None)
    self.useNaturalKeys = options.pop("useNaturalKeys", False)
    if self.useNaturalKeys:
      warnings.warn("``useNaturalKeys`` is deprecated; use ``useNaturalForeignKeys`` instead.",
        RemovedInTheory19Warning)
    self.useNaturalForeignKeys = options.pop('useNaturalForeignKeys', False) or self.useNaturalKeys
    self.useNaturalPrimaryKeys = options.pop('useNaturalPrimaryKeys', False)

    self.startSerialization()
    self.first = True
    for obj in queryset:
      self.startObject(obj)
      # Use the concrete parent class' _meta instead of the object's _meta
      # This is to avoid localFields problems for proxy model. Refs #17717.
      concreteModel = obj._meta.concreteModel
      for field in concreteModel._meta.localFields:
        if field.serialize:
          if field.rel is None:
            if self.selectedFields is None or field.attname in self.selectedFields:
              self.handleField(obj, field)
          else:
            if self.selectedFields is None or field.attname[:-3] in self.selectedFields:
              self.handleFkField(obj, field)
      for field in concreteModel._meta.manyToMany:
        if field.serialize:
          if self.selectedFields is None or field.attname in self.selectedFields:
            self.handleM2mField(obj, field)
      self.endObject(obj)
      if self.first:
        self.first = False
    self.endSerialization()
    return self.getvalue()

  def startSerialization(self):
    """
    Called when serializing of the queryset starts.
    """
    raise NotImplementedError('subclasses of Serializer must provide a startSerialization() method')

  def endSerialization(self):
    """
    Called when serializing of the queryset ends.
    """
    pass

  def startObject(self, obj):
    """
    Called when serializing of an object starts.
    """
    raise NotImplementedError('subclasses of Serializer must provide a startObject() method')

  def endObject(self, obj):
    """
    Called when serializing of an object ends.
    """
    pass

  def handleField(self, obj, field):
    """
    Called to handle each individual (non-relational) field on an object.
    """
    raise NotImplementedError('subclasses of Serializer must provide an handleField() method')

  def handleFkField(self, obj, field):
    """
    Called to handle a ForeignKey field.
    """
    raise NotImplementedError('subclasses of Serializer must provide an handleFkField() method')

  def handleM2mField(self, obj, field):
    """
    Called to handle a ManyToManyField.
    """
    raise NotImplementedError('subclasses of Serializer must provide an handleM2mField() method')

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
    if isinstance(streamOrString, six.stringTypes):
      self.stream = six.StringIO(streamOrString)
    else:
      self.stream = streamOrString

  def __iter__(self):
    return self

  def __next__(self):
    """Iteration iterface -- return the next item in the stream"""
    raise NotImplementedError('subclasses of Deserializer must provide a __next__() method')


class DeserializedObject(object):
  """
  A deserialized model.

  Basically a container for holding the pre-saved deserialized data along
  with the many-to-many data saved with the object.

  Call ``save()`` to save the object (with the many-to-many data) to the
  database; call ``save(saveM2m=False)`` to save just the object fields
  (and not touch the many-to-many stuff.)
  """

  def __init__(self, obj, m2mData=None):
    self.object = obj
    self.m2mData = m2mData

  def __repr__(self):
    return "<DeserializedObject: %s.%s(pk=%s)>" % (
      self.object._meta.appLabel, self.object._meta.objectName, self.object.pk)

  def save(self, saveM2m=True, using=None):
    # Call save on the Model baseclass directly. This bypasses any
    # model-defined save. The save is also forced to be raw.
    # raw=True is passed to any pre/postSave signals.
    model.Model.saveBase(self.object, using=using, raw=True)
    if self.m2mData and saveM2m:
      for accessorName, objectList in self.m2mData.items():
        setattr(self.object, accessorName, objectList)

    # prevent a second (possibly accidental) call to save() from saving
    # the m2m data twice.
    self.m2mData = None


def buildInstance(Model, data, db):
  """
  Build a model instance.

  If the model instance doesn't have a primary key and the model supports
  natural keys, try to retrieve it from the database.
  """
  obj = Model(**data)
  if (obj.pk is None and hasattr(Model, 'naturalKey') and
      hasattr(Model._defaultManager, 'getByNaturalKey')):
    naturalKey = obj.naturalKey()
    try:
      obj.pk = Model._defaultManager.dbManager(db).getByNaturalKey(*naturalKey).pk
    except Model.DoesNotExist:
      pass
  return obj
