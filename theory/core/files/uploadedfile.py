"""
Classes representing uploaded files.
"""

import errno
import os
from io import BytesIO

from theory.conf import settings
from theory.core.files.base import File
from theory.core.files import temp as tempfile
from theory.utils.encoding import forceStr

__all__ = ('UploadedFile', 'TemporaryUploadedFile', 'InMemoryUploadedFile',
      'SimpleUploadedFile')


class UploadedFile(File):
  """
  A abstract uploaded file (``TemporaryUploadedFile`` and
  ``InMemoryUploadedFile`` are the built-in concrete subclasses).

  An ``UploadedFile`` object behaves somewhat like a file object and
  represents some file data that the user submitted with a form.
  """
  DEFAULT_CHUNK_SIZE = 64 * 2 ** 10

  def __init__(self, file=None, name=None, contentType=None, size=None, charset=None, contentTypeExtra=None):
    super(UploadedFile, self).__init__(file, name)
    self.size = size
    self.contentType = contentType
    self.charset = charset
    self.contentTypeExtra = contentTypeExtra

  def __repr__(self):
    return forceStr("<%s: %s (%s)>" % (
      self.__class__.__name__, self.name, self.contentType))

  def _getName(self):
    return self._name

  def _setName(self, name):
    # Sanitize the file name so that it can't be dangerous.
    if name is not None:
      # Just use the basename of the file -- anything else is dangerous.
      name = os.path.basename(name)

      # File names longer than 255 characters can cause problems on older OSes.
      if len(name) > 255:
        name, ext = os.path.splitext(name)
        ext = ext[:255]
        name = name[:255 - len(ext)] + ext

    self._name = name

  name = property(_getName, _setName)


class TemporaryUploadedFile(UploadedFile):
  """
  A file uploaded to a temporary location (i.e. stream-to-disk).
  """
  def __init__(self, name, contentType, size, charset, contentTypeExtra=None):
    if settings.FILE_UPLOAD_TEMP_DIR:
      file = tempfile.NamedTemporaryFile(suffix='.upload',
        dir=settings.FILE_UPLOAD_TEMP_DIR)
    else:
      file = tempfile.NamedTemporaryFile(suffix='.upload')
    super(TemporaryUploadedFile, self).__init__(file, name, contentType, size, charset, contentTypeExtra)

  def temporaryFilePath(self):
    """
    Returns the full path of this file.
    """
    return self.file.name

  def close(self):
    try:
      return self.file.close()
    except OSError as e:
      if e.errno != errno.ENOENT:
        # Means the file was moved or deleted before the tempfile
        # could unlink it.  Still sets self.file.closeCalled and
        # calls self.file.file.close() before the exception
        raise


class InMemoryUploadedFile(UploadedFile):
  """
  A file uploaded into memory (i.e. stream-to-memory).
  """
  def __init__(self, file, fieldName, name, contentType, size, charset, contentTypeExtra=None):
    super(InMemoryUploadedFile, self).__init__(file, name, contentType, size, charset, contentTypeExtra)
    self.fieldName = fieldName

  def open(self, mode=None):
    self.file.seek(0)

  def chunks(self, chunkSize=None):
    self.file.seek(0)
    yield self.read()

  def multipleChunks(self, chunkSize=None):
    # Since it's in memory, we'll never have multiple chunks.
    return False


class SimpleUploadedFile(InMemoryUploadedFile):
  """
  A simple representation of a file, which just has content, size, and a name.
  """
  def __init__(self, name, content, contentType='text/plain'):
    content = content or b''
    super(SimpleUploadedFile, self).__init__(BytesIO(content), None, name,
                         contentType, len(content), None, None)

  @classmethod
  def fromDict(cls, fileDict):
    """
    Creates a SimpleUploadedFile object from
    a dictionary object with the following keys:
      - filename
      - content-type
      - content
    """
    return cls(fileDict['filename'],
          fileDict['content'],
          fileDict.get('content-type', 'text/plain'))
