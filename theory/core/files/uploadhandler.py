"""
Base file upload handler classes, and the built-in concrete subclasses
"""

from __future__ import unicode_literals

from io import BytesIO

from theory.conf import settings
from theory.core.files.uploadedfile import TemporaryUploadedFile, InMemoryUploadedFile
from theory.utils.encoding import python2_unicodeCompatible
from theory.utils.moduleLoading import importString

__all__ = [
  'UploadFileException', 'StopUpload', 'SkipFile', 'FileUploadHandler',
  'TemporaryFileUploadHandler', 'MemoryFileUploadHandler', 'loadHandler',
  'StopFutureHandlers'
]


class UploadFileException(Exception):
  """
  Any error having to do with uploading files.
  """
  pass


@python2_unicodeCompatible
class StopUpload(UploadFileException):
  """
  This exception is raised when an upload must abort.
  """
  def __init__(self, connectionReset=False):
    """
    If ``connectionReset`` is ``True``, Theory knows will halt the upload
    without consuming the rest of the upload. This will cause the browser to
    show a "connection reset" error.
    """
    self.connectionReset = connectionReset

  def __str__(self):
    if self.connectionReset:
      return 'StopUpload: Halt current upload.'
    else:
      return 'StopUpload: Consume request data, then halt.'


class SkipFile(UploadFileException):
  """
  This exception is raised by an upload handler that wants to skip a given file.
  """
  pass


class StopFutureHandlers(UploadFileException):
  """
  Upload handers that have handled a file and do not want future handlers to
  run should raise this exception instead of returning None.
  """
  pass


class FileUploadHandler(object):
  """
  Base class for streaming upload handlers.
  """
  chunkSize = 64 * 2 ** 10  # : The default chunk size is 64 KB.

  def __init__(self, request=None):
    self.fileName = None
    self.contentType = None
    self.contentLength = None
    self.charset = None
    self.contentTypeExtra = None
    self.request = request

  def handleRawInput(self, inputData, META, contentLength, boundary, encoding=None):
    """
    Handle the raw input from the client.

    Parameters:

      :inputData:
        An object that supports reading via .read().
      :META:
        ``request.META``.
      :contentLength:
        The (integer) value of the Content-Length header from the
        client.
      :boundary: The boundary from the Content-Type header. Be sure to
        prepend two '--'.
    """
    pass

  def newFile(self, fieldName, fileName, contentType, contentLength, charset=None, contentTypeExtra=None):
    """
    Signal that a new file has been started.

    Warning: As with any data from the client, you should not trust
    contentLength (and sometimes won't even get it).
    """
    self.fieldName = fieldName
    self.fileName = fileName
    self.contentType = contentType
    self.contentLength = contentLength
    self.charset = charset
    self.contentTypeExtra = contentTypeExtra

  def receiveDataChunk(self, rawData, start):
    """
    Receive data from the streamed upload parser. ``start`` is the position
    in the file of the chunk.
    """
    raise NotImplementedError('subclasses of FileUploadHandler must provide a receiveDataChunk() method')

  def fileComplete(self, fileSize):
    """
    Signal that a file has completed. File size corresponds to the actual
    size accumulated by all the chunks.

    Subclasses should return a valid ``UploadedFile`` object.
    """
    raise NotImplementedError('subclasses of FileUploadHandler must provide a fileComplete() method')

  def uploadComplete(self):
    """
    Signal that the upload is complete. Subclasses should perform cleanup
    that is necessary for this handler.
    """
    pass


class TemporaryFileUploadHandler(FileUploadHandler):
  """
  Upload handler that streams data into a temporary file.
  """
  def __init__(self, *args, **kwargs):
    super(TemporaryFileUploadHandler, self).__init__(*args, **kwargs)

  def newFile(self, fileName, *args, **kwargs):
    """
    Create the file object to append to as data is coming in.
    """
    super(TemporaryFileUploadHandler, self).newFile(fileName, *args, **kwargs)
    self.file = TemporaryUploadedFile(self.fileName, self.contentType, 0, self.charset, self.contentTypeExtra)

  def receiveDataChunk(self, rawData, start):
    self.file.write(rawData)

  def fileComplete(self, fileSize):
    self.file.seek(0)
    self.file.size = fileSize
    return self.file


class MemoryFileUploadHandler(FileUploadHandler):
  """
  File upload handler to stream uploads into memory (used for small files).
  """

  def handleRawInput(self, inputData, META, contentLength, boundary, encoding=None):
    """
    Use the contentLength to signal whether or not this handler should be in use.
    """
    # Check the content-length header to see if we should
    # If the post is too large, we cannot use the Memory handler.
    if contentLength > settings.FILE_UPLOAD_MAX_MEMORY_SIZE:
      self.activated = False
    else:
      self.activated = True

  def newFile(self, *args, **kwargs):
    super(MemoryFileUploadHandler, self).newFile(*args, **kwargs)
    if self.activated:
      self.file = BytesIO()
      raise StopFutureHandlers()

  def receiveDataChunk(self, rawData, start):
    """
    Add the data to the BytesIO file.
    """
    if self.activated:
      self.file.write(rawData)
    else:
      return rawData

  def fileComplete(self, fileSize):
    """
    Return a file object if we're activated.
    """
    if not self.activated:
      return

    self.file.seek(0)
    return InMemoryUploadedFile(
      file=self.file,
      fieldName=self.fieldName,
      name=self.fileName,
      contentType=self.contentType,
      size=fileSize,
      charset=self.charset,
      contentTypeExtra=self.contentTypeExtra
    )


def loadHandler(path, *args, **kwargs):
  """
  Given a path to a handler, return an instance of that handler.

  E.g.::
    >>> from theory.http import HttpRequest
    >>> request = HttpRequest()
    >>> loadHandler('theory.core.files.uploadhandler.TemporaryFileUploadHandler', request)
    <TemporaryFileUploadHandler object at 0x...>

  """
  return importString(path)(*args, **kwargs)
