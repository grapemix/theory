"""
Utility functions for handling images.

Requires Pillow as you might imagine.
"""
import zlib

from theory.core.files import File


class ImageFile(File):
  """
  A mixin for use alongside theory.core.files.base.File, which provides
  additional features for dealing with images.
  """
  def _getWidth(self):
    return self._getImageDimensions()[0]
  width = property(_getWidth)

  def _getHeight(self):
    return self._getImageDimensions()[1]
  height = property(_getHeight)

  def _getImageDimensions(self):
    if not hasattr(self, '_dimensionsCache'):
      close = self.closed
      self.open()
      self._dimensionsCache = getImageDimensions(self, close=close)
    return self._dimensionsCache


def getImageDimensions(fileOrPath, close=False):
  """
  Returns the (width, height) of an image, given an open file or a path.  Set
  'close' to True to close the file at the end if it is initially in an open
  state.
  """
  from PIL import ImageFile as PillowImageFile

  p = PillowImageFile.Parser()
  if hasattr(fileOrPath, 'read'):
    file = fileOrPath
    filePos = file.tell()
    file.seek(0)
  else:
    file = open(fileOrPath, 'rb')
    close = True
  try:
    # Most of the time Pillow only needs a small chunk to parse the image
    # and get the dimensions, but with some TIFF files Pillow needs to
    # parse the whole file.
    chunkSize = 1024
    while 1:
      data = file.read(chunkSize)
      if not data:
        break
      try:
        p.feed(data)
      except zlib.error as e:
        # ignore zlib complaining on truncated stream, just feed more
        # data to parser (ticket #19457).
        if e.args[0].startswith("Error -5"):
          pass
        else:
          raise
      if p.image:
        return p.image.size
      chunkSize *= 2
    return None
  finally:
    if close:
      file.close()
    else:
      file.seek(filePos)
