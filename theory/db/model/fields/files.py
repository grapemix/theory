import datetime
import os

from theory.db.model.fields import Field
from theory.core import checks
from theory.core.exceptions import ImproperlyConfigured
from theory.core.files.base import File
from theory.core.files.storage import defaultStorage
from theory.core.files.images import ImageFile
from theory.db.model import signals
from theory.utils.encoding import forceStr, forceText
from theory.utils import six
from theory.utils.translation import ugettextLazy as _


class FieldFile(File):
  def __init__(self, instance, field, name):
    super(FieldFile, self).__init__(None, name)
    self.instance = instance
    self.field = field
    self.storage = field.storage
    self._committed = True

  def __eq__(self, other):
    # Older code may be expecting FileField values to be simple strings.
    # By overriding the == operator, it can remain backwards compatibility.
    if hasattr(other, 'name'):
      return self.name == other.name
    return self.name == other

  def __ne__(self, other):
    return not self.__eq__(other)

  def __hash__(self):
    return hash(self.name)

  # The standard File contains most of the necessary properties, but
  # FieldFiles can be instantiated without a name, so that needs to
  # be checked for here.

  def _requireFile(self):
    if not self:
      raise ValueError("The '%s' attribute has no file associated with it." % self.field.name)

  def _getFile(self):
    self._requireFile()
    if not hasattr(self, '_file') or self._file is None:
      self._file = self.storage.open(self.name, 'rb')
    return self._file

  def _setFile(self, file):
    self._file = file

  def _delFile(self):
    del self._file

  file = property(_getFile, _setFile, _delFile)

  def _getPath(self):
    self._requireFile()
    return self.storage.path(self.name)
  path = property(_getPath)

  def _getUrl(self):
    self._requireFile()
    return self.storage.url(self.name)
  url = property(_getUrl)

  def _getSize(self):
    self._requireFile()
    if not self._committed:
      return self.file.size
    return self.storage.size(self.name)
  size = property(_getSize)

  def open(self, mode='rb'):
    self._requireFile()
    self.file.open(mode)
  # open() doesn't alter the file's contents, but it does reset the pointer
  open.altersData = True

  # In addition to the standard File API, FieldFiles have extra methods
  # to further manipulate the underlying file, as well as update the
  # associated modal instance.

  def save(self, name, content, save=True):
    name = self.field.generateFilename(self.instance, name)
    self.name = self.storage.save(name, content)
    setattr(self.instance, self.field.name, self.name)

    # Update the filesize cache
    self._size = content.size
    self._committed = True

    # Save the object because it has changed, unless save is False
    if save:
      self.instance.save()
  save.altersData = True

  def delete(self, save=True):
    if not self:
      return
    # Only close the file if it's already open, which we know by the
    # presence of self._file
    if hasattr(self, '_file'):
      self.close()
      del self.file

    self.storage.delete(self.name)

    self.name = None
    setattr(self.instance, self.field.name, self.name)

    # Delete the filesize cache
    if hasattr(self, '_size'):
      del self._size
    self._committed = False

    if save:
      self.instance.save()
  delete.altersData = True

  def _getClosed(self):
    file = getattr(self, '_file', None)
    return file is None or file.closed
  closed = property(_getClosed)

  def close(self):
    file = getattr(self, '_file', None)
    if file is not None:
      file.close()

  def __getstate__(self):
    # FieldFile needs access to its associated modal field and an instance
    # it's attached to in order to work properly, but the only necessary
    # data to be pickled is the file's name itself. Everything else will
    # be restored later, by FileDescriptor below.
    return {'name': self.name, 'closed': False, '_committed': True, '_file': None}


class FileDescriptor(object):
  """
  The descriptor for the file attribute on the modal instance. Returns a
  FieldFile when accessed so you can do stuff like::

    >>> from myapp.model import MyModel
    >>> instance = MyModel.objects.get(pk=1)
    >>> instance.file.size

  Assigns a file object on assignment so you can do::

    >>> with open('/tmp/hello.world', 'r') as f:
    ...     instance.file = File(f)

  """
  def __init__(self, field):
    self.field = field

  def __get__(self, instance=None, owner=None):
    if instance is None:
      raise AttributeError(
        "The '%s' attribute can only be accessed from %s instances."
        % (self.field.name, owner.__name__))

    # This is slightly complicated, so worth an explanation.
    # instance.file`needs to ultimately return some instance of `File`,
    # probably a subclass. Additionally, this returned object needs to have
    # the FieldFile API so that users can easily do things like
    # instance.file.path and have that delegated to the file storage engine.
    # Easy enough if we're strict about assignment in __set__, but if you
    # peek below you can see that we're not. So depending on the current
    # value of the field we have to dynamically construct some sort of
    # "thing" to return.

    # The instance dict contains whatever was originally assigned
    # in __set__.
    file = instance.__dict__[self.field.name]

    # If this value is a string (instance.file = "path/to/file") or None
    # then we simply wrap it with the appropriate attribute class according
    # to the file field. [This is FieldFile for FileFields and
    # ImageFieldFile for ImageFields; it's also conceivable that user
    # subclasses might also want to subclass the attribute class]. This
    # object understands how to convert a path to a file, and also how to
    # handle None.
    if isinstance(file, six.stringTypes) or file is None:
      attr = self.field.attrClass(instance, self.field, file)
      instance.__dict__[self.field.name] = attr

    # Other types of files may be assigned as well, but they need to have
    # the FieldFile interface added to the. Thus, we wrap any other type of
    # File inside a FieldFile (well, the field's attrClass, which is
    # usually FieldFile).
    elif isinstance(file, File) and not isinstance(file, FieldFile):
      fileCopy = self.field.attrClass(instance, self.field, file.name)
      fileCopy.file = file
      fileCopy._committed = False
      instance.__dict__[self.field.name] = fileCopy

    # Finally, because of the (some would say boneheaded) way pickle works,
    # the underlying FieldFile might not actually itself have an associated
    # file. So we need to reset the details of the FieldFile in those cases.
    elif isinstance(file, FieldFile) and not hasattr(file, 'field'):
      file.instance = instance
      file.field = self.field
      file.storage = self.field.storage

    # That was fun, wasn't it?
    return instance.__dict__[self.field.name]

  def __set__(self, instance, value):
    instance.__dict__[self.field.name] = value


class FileField(Field):

  # The class to wrap instance attributes in. Accessing the file object off
  # the instance will always return an instance of attrClass.
  attrClass = FieldFile

  # The descriptor to use for accessing the attribute off of the class.
  descriptorClass = FileDescriptor

  description = _("File")

  def __init__(self, verboseName=None, name=None, uploadTo='', storage=None, **kwargs):
    self._primaryKeySetExplicitly = 'primaryKey' in kwargs
    self._uniqueSetExplicitly = 'unique' in kwargs

    self.storage = storage or defaultStorage
    self.uploadTo = uploadTo
    if callable(uploadTo):
      self.generateFilename = uploadTo

    kwargs['maxLength'] = kwargs.get('maxLength', 100)
    super(FileField, self).__init__(verboseName, name, **kwargs)

  def check(self, **kwargs):
    errors = super(FileField, self).check(**kwargs)
    errors.extend(self._checkUnique())
    errors.extend(self._checkPrimaryKey())
    return errors

  def _checkUnique(self):
    if self._uniqueSetExplicitly:
      return [
        checks.Error(
          "'unique' is not a valid argument for a %s." % self.__class__.__name__,
          hint=None,
          obj=self,
          id='fields.E200',
        )
      ]
    else:
      return []

  def _checkPrimaryKey(self):
    if self._primaryKeySetExplicitly:
      return [
        checks.Error(
          "'primaryKey' is not a valid argument for a %s." % self.__class__.__name__,
          hint=None,
          obj=self,
          id='fields.E201',
        )
      ]
    else:
      return []

  def deconstruct(self):
    name, path, args, kwargs = super(FileField, self).deconstruct()
    if kwargs.get("maxLength", None) == 100:
      del kwargs["maxLength"]
    kwargs['uploadTo'] = self.uploadTo
    if self.storage is not defaultStorage:
      kwargs['storage'] = self.storage
    return name, path, args, kwargs

  def getInternalType(self):
    return "FileField"

  def getPrepLookup(self, lookupType, value):
    if hasattr(value, 'name'):
      value = value.name
    return super(FileField, self).getPrepLookup(lookupType, value)

  def getPrepValue(self, value):
    "Returns field's value prepared for saving into a database."
    value = super(FileField, self).getPrepValue(value)
    # Need to convert File objects provided via a form to unicode for database insertion
    if value is None:
      return None
    return six.textType(value)

  def preSave(self, modalInstance, add):
    "Returns field's value just before saving."
    file = super(FileField, self).preSave(modalInstance, add)
    if file and not file._committed:
      # Commit the file to storage prior to saving the modal
      file.save(file.name, file, save=False)
    return file

  def contributeToClass(self, cls, name):
    super(FileField, self).contributeToClass(cls, name)
    setattr(cls, self.name, self.descriptorClass(self))

  def getDirectoryName(self):
    return os.path.normpath(forceText(datetime.datetime.now().strftime(forceStr(self.uploadTo))))

  def getFilename(self, filename):
    return os.path.normpath(self.storage.getValidName(os.path.basename(filename)))

  def generateFilename(self, instance, filename):
    return os.path.join(self.getDirectoryName(), self.getFilename(filename))

  def saveFormData(self, instance, data):
    # Important: None means "no change", other false value means "clear"
    # This subtle distinction (rather than a more explicit marker) is
    # needed because we need to consume values that are also sane for a
    # regular (non Model-) Form to find in its cleanedData dictionary.
    if data is not None:
      # This value will be converted to unicode and stored in the
      # database, so leaving False as-is is not acceptable.
      if not data:
        data = ''
      setattr(instance, self.name, data)

  def formfield(self, **kwargs):
    defaults = {'formClass': forms.FileField, 'maxLength': self.maxLength}
    # If a file has been provided previously, then the form doesn't require
    # that a new file is provided this time.
    # The code to mark the form field as not required is used by
    # formForInstance, but can probably be removed once formForInstance
    # is gone. ModelForm uses a different method to check for an existing file.
    if 'initial' in kwargs:
      defaults['required'] = False
    defaults.update(kwargs)
    return super(FileField, self).formfield(**defaults)


class ImageFileDescriptor(FileDescriptor):
  """
  Just like the FileDescriptor, but for ImageFields. The only difference is
  assigning the width/height to the widthField/heightField, if appropriate.
  """
  def __set__(self, instance, value):
    previousFile = instance.__dict__.get(self.field.name)
    super(ImageFileDescriptor, self).__set__(instance, value)

    # To prevent recalculating image dimensions when we are instantiating
    # an object from the database (bug #11084), only update dimensions if
    # the field had a value before this assignment.  Since the default
    # value for FileField subclasses is an instance of field.attrClass,
    # previousFile will only be None when we are called from
    # Model.__init__().  The ImageField.updateDimensionFields method
    # hooked up to the postInit signal handles the Model.__init__() cases.
    # Assignment happening outside of Model.__init__() will trigger the
    # update right here.
    if previousFile is not None:
      self.field.updateDimensionFields(instance, force=True)


class ImageFieldFile(ImageFile, FieldFile):
  def delete(self, save=True):
    # Clear the image dimensions cache
    if hasattr(self, '_dimensionsCache'):
      del self._dimensionsCache
    super(ImageFieldFile, self).delete(save)


class ImageField(FileField):
  attrClass = ImageFieldFile
  descriptorClass = ImageFileDescriptor
  description = _("Image")

  def __init__(self, verboseName=None, name=None, widthField=None,
      heightField=None, **kwargs):
    self.widthField, self.heightField = widthField, heightField
    super(ImageField, self).__init__(verboseName, name, **kwargs)

  def check(self, **kwargs):
    errors = super(ImageField, self).check(**kwargs)
    errors.extend(self._checkImageLibraryInstalled())
    return errors

  def _checkImageLibraryInstalled(self):
    try:
      from theory.utils.image import Image  # NOQA
    except ImproperlyConfigured:
      return [
        checks.Error(
          'Cannot use ImageField because Pillow is not installed.',
          hint=('Get Pillow at https://pypi.python.org/pypi/Pillow '
             'or run command "pip install pillow".'),
          obj=self,
          id='fields.E210',
        )
      ]
    else:
      return []

  def deconstruct(self):
    name, path, args, kwargs = super(ImageField, self).deconstruct()
    if self.widthField:
      kwargs['widthField'] = self.widthField
    if self.heightField:
      kwargs['heightField'] = self.heightField
    return name, path, args, kwargs

  def contributeToClass(self, cls, name):
    super(ImageField, self).contributeToClass(cls, name)
    # Attach updateDimensionFields so that dimension fields declared
    # after their corresponding image field don't stay cleared by
    # Model.__init__, see bug #11196.
    # Only run post-initialization dimension update on non-abstract model
    if not cls._meta.abstract:
      signals.postInit.connect(self.updateDimensionFields, sender=cls)

  def updateDimensionFields(self, instance, force=False, *args, **kwargs):
    """
    Updates field's width and height fields, if defined.

    This method is hooked up to modal's postInit signal to update
    dimensions after instantiating a modal instance.  However, dimensions
    won't be updated if the dimensions fields are already populated.  This
    avoids unnecessary recalculation when loading an object from the
    database.

    Dimensions can be forced to update with force=True, which is how
    ImageFileDescriptor.__set__ calls this method.
    """
    # Nothing to update if the field doesn't have dimension fields.
    hasDimensionFields = self.widthField or self.heightField
    if not hasDimensionFields:
      return

    # getattr will call the ImageFileDescriptor's __get__ method, which
    # coerces the assigned value into an instance of self.attrClass
    # (ImageFieldFile in this case).
    file = getattr(instance, self.attname)

    # Nothing to update if we have no file and not being forced to update.
    if not file and not force:
      return

    dimensionFieldsFilled = not(
      (self.widthField and not getattr(instance, self.widthField))
      or (self.heightField and not getattr(instance, self.heightField))
    )
    # When both dimension fields have values, we are most likely loading
    # data from the database or updating an image field that already had
    # an image stored.  In the first case, we don't want to update the
    # dimension fields because we are already getting their values from the
    # database.  In the second case, we do want to update the dimensions
    # fields and will skip this return because force will be True since we
    # were called from ImageFileDescriptor.__set__.
    if dimensionFieldsFilled and not force:
      return

    # file should be an instance of ImageFieldFile or should be None.
    if file:
      width = file.width
      height = file.height
    else:
      # No file, so clear dimensions fields.
      width = None
      height = None

    # Update the width and height fields.
    if self.widthField:
      setattr(instance, self.widthField, width)
    if self.heightField:
      setattr(instance, self.heightField, height)

  def formfield(self, **kwargs):
    defaults = {'formClass': forms.ImageField}
    defaults.update(kwargs)
    return super(ImageField, self).formfield(**defaults)
