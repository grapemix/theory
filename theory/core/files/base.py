from __future__ import unicode_literals

import os
from io import BytesIO, StringIO, UnsupportedOperation

from theory.utils.encoding import smartText
from theory.core.files.utils import FileProxyMixin
from theory.utils import six
from theory.utils.encoding import forceBytes, python2UnicodeCompatible


@python2UnicodeCompatible
class File(FileProxyMixin):
  DEFAULT_CHUNK_SIZE = 64 * 2 ** 10

  def __init__(self, file, name=None):
    self.file = file
    if name is None:
      name = getattr(file, 'name', None)
    self.name = name
    if hasattr(file, 'mode'):
      self.mode = file.mode

  def __str__(self):
    return smartText(self.name or '')

  def __repr__(self):
    return "<%s: %s>" % (self.__class__.__name__, self or "None")

  def __bool__(self):
    return bool(self.name)

  def __nonzero__(self):      # Python 2 compatibility
    return type(self).__bool__(self)

  def __len__(self):
    return self.size

  def _getSizeFromUnderlyingFile(self):
    if hasattr(self.file, 'size'):
      return self.file.size
    if hasattr(self.file, 'name'):
      try:
        return os.path.getsize(self.file.name)
      except (OSError, TypeError):
        pass
    if hasattr(self.file, 'tell') and hasattr(self.file, 'seek'):
      pos = self.file.tell()
      self.file.seek(0, os.SEEK_END)
      size = self.file.tell()
      self.file.seek(pos)
      return size
    raise AttributeError("Unable to determine the file's size.")

  def _getSize(self):
    if hasattr(self, '_size'):
      return self._size
    self._size = self._getSizeFromUnderlyingFile()
    return self._size

  def _setSize(self, size):
    self._size = size

  size = property(_getSize, _setSize)

  def _getClosed(self):
    return not self.file or self.file.closed
  closed = property(_getClosed)

  def chunks(self, chunkSize=None):
    """
    Read the file and yield chucks of ``chunkSize`` bytes (defaults to
    ``UploadedFile.DEFAULT_CHUNK_SIZE``).
    """
    if not chunkSize:
      chunkSize = self.DEFAULT_CHUNK_SIZE

    try:
      self.seek(0)
    except (AttributeError, UnsupportedOperation):
      pass

    while True:
      data = self.read(chunkSize)
      if not data:
        break
      yield data

  def multipleChunks(self, chunkSize=None):
    """
    Returns ``True`` if you can expect multiple chunks.

    NB: If a particular file representation is in memory, subclasses should
    always return ``False`` -- there's no good reason to read from memory in
    chunks.
    """
    if not chunkSize:
      chunkSize = self.DEFAULT_CHUNK_SIZE
    return self.size > chunkSize

  def __iter__(self):
    # Iterate over this file-like object by newlines
    buffer_ = None
    for chunk in self.chunks():
      chunkBuffer = BytesIO(chunk)

      for line in chunkBuffer:
        if buffer_:
          line = buffer_ + line
          buffer_ = None

        # If this is the end of a line, yield
        # otherwise, wait for the next round
        if line[-1:] in (b'\n', b'\r'):
          yield line
        else:
          buffer_ = line

    if buffer_ is not None:
      yield buffer_

  def __enter__(self):
    return self

  def __exit__(self, excType, excValue, tb):
    self.close()

  def open(self, mode=None):
    if not self.closed:
      self.seek(0)
    elif self.name and os.path.exists(self.name):
      self.file = open(self.name, mode or self.mode)
    else:
      raise ValueError("The file cannot be reopened.")

  def close(self):
    self.file.close()


@python2UnicodeCompatible
class ContentFile(File):
  """
  A File-like object that takes just raw content, rather than an actual file.
  """
  def __init__(self, content, name=None):
    if six.PY3:
      streamClass = StringIO if isinstance(content, six.textType) else BytesIO
    else:
      streamClass = BytesIO
      content = forceBytes(content)
    super(ContentFile, self).__init__(streamClass(content), name=name)
    self.size = len(content)

  def __str__(self):
    return 'Raw content'

  def __bool__(self):
    return True

  def __nonzero__(self):      # Python 2 compatibility
    return type(self).__bool__(self)

  def open(self, mode=None):
    self.seek(0)

  def close(self):
    pass
