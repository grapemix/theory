"""
Move a file in the safest way possible::

  >>> from theory.core.files.move import fileMoveSafe
  >>> fileMoveSafe("/tmp/oldFile", "/tmp/newFile")
"""

import os
from theory.core.files import locks

try:
  from shutil import copystat
except ImportError:
  import stat

  def copystat(src, dst):
    """Copy all stat info (mode bits, atime and mtime) from src to dst"""
    st = os.stat(src)
    mode = stat.S_IMODE(st.stMode)
    if hasattr(os, 'utime'):
      os.utime(dst, (st.stAtime, st.stMtime))
    if hasattr(os, 'chmod'):
      os.chmod(dst, mode)

__all__ = ['fileMoveSafe']


def _samefile(src, dst):
  # Macintosh, Unix.
  if hasattr(os.path, 'samefile'):
    try:
      return os.path.samefile(src, dst)
    except OSError:
      return False

  # All other platforms: check for same pathname.
  return (os.path.normcase(os.path.abspath(src)) ==
      os.path.normcase(os.path.abspath(dst)))


def fileMoveSafe(oldFileName, newFileName, chunkSize=1024 * 64, allowOverwrite=False):
  """
  Moves a file from one location to another in the safest way possible.

  First, tries ``os.rename``, which is simple but will break across filesystems.
  If that fails, streams manually from one file to another in pure Python.

  If the destination file exists and ``allowOverwrite`` is ``False``, this
  function will throw an ``IOError``.
  """

  # There's no reason to move if we don't have to.
  if _samefile(oldFileName, newFileName):
    return

  try:
    # If the destination file exists and allowOverwrite is False then raise an IOError
    if not allowOverwrite and os.access(newFileName, os.F_OK):
      raise IOError("Destination file %s exists and allowOverwrite is False" % newFileName)

    os.rename(oldFileName, newFileName)
    return
  except OSError:
    # This will happen with os.rename if moving to another filesystem
    # or when moving opened files on certain operating systems
    pass

  # first open the old file, so that it won't go away
  with open(oldFileName, 'rb') as oldFile:
    # now open the new file, not forgetting allowOverwrite
    fd = os.open(newFileName, (os.O_WRONLY | os.O_CREAT | getattr(os, 'O_BINARY', 0) |
                   (os.O_EXCL if not allowOverwrite else 0)))
    try:
      locks.lock(fd, locks.LOCK_EX)
      currentChunk = None
      while currentChunk != b'':
        currentChunk = oldFile.read(chunkSize)
        os.write(fd, currentChunk)
    finally:
      locks.unlock(fd)
      os.close(fd)
  copystat(oldFileName, newFileName)

  try:
    os.remove(oldFileName)
  except OSError as e:
    # Certain operating systems (Cygwin and Windows)
    # fail when deleting opened files, ignore it.  (For the
    # systems where this happens, temporary files will be auto-deleted
    # on close anyway.)
    if getattr(e, 'winerror', 0) != 32 and getattr(e, 'errno', 0) != 13:
      raise
