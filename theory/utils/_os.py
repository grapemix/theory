import os
import stat
import sys
import tempfile
from os.path import join, normcase, normpath, abspath, isabs, sep, dirname

from theory.utils.encoding import forceText
from theory.utils import six

try:
  WindowsError = WindowsError
except NameError:
  class WindowsError(Exception):
    pass

if six.PY2:
  fsEncoding = sys.getfilesystemencoding() or sys.getdefaultencoding()


# Under Python 2, define our own abspath function that can handle joining
# unicode paths to a current working directory that has non-ASCII characters
# in it.  This isn't necessary on Windows since the Windows version of abspath
# handles this correctly. It also handles drive letters differently than the
# pure Python implementation, so it's best not to replace it.
if six.PY3 or os.name == 'nt':
  abspathu = abspath
else:
  def abspathu(path):
    """
    Version of os.path.abspath that uses the unicode representation
    of the current working directory, thus avoiding a UnicodeDecodeError
    in join when the cwd has non-ASCII characters.
    """
    if not isabs(path):
      path = join(os.getcwdu(), path)
    return normpath(path)


def upath(path):
  """
  Always return a unicode path.
  """
  if six.PY2 and not isinstance(path, six.textType):
    return path.decode(fsEncoding)
  return path


def npath(path):
  """
  Always return a native path, that is unicode on Python 3 and bytestring on
  Python 2.
  """
  if six.PY2 and not isinstance(path, bytes):
    return path.encode(fsEncoding)
  return path


def safeJoin(base, *paths):
  """
  Joins one or more path components to the base path component intelligently.
  Returns a normalized, absolute version of the final path.

  The final path must be located inside of the base path component (otherwise
  a ValueError is raised).
  """
  base = forceText(base)
  paths = [forceText(p) for p in paths]
  finalPath = abspathu(join(base, *paths))
  basePath = abspathu(base)
  # Ensure finalPath starts with basePath (using normcase to ensure we
  # don't false-negative on case insensitive operating systems like Windows),
  # further, one of the following conditions must be true:
  #  a) The next character is the path separator (to prevent conditions like
  #     safeJoin("/dir", "/../d"))
  #  b) The final path must be the same as the base path.
  #  c) The base path must be the most root path (meaning either "/" or "C:\\")
  if (not normcase(finalPath).startswith(normcase(basePath + sep)) and
      normcase(finalPath) != normcase(basePath) and
      dirname(normcase(basePath)) != normcase(basePath)):
    raise ValueError('The joined path (%s) is located outside of the base '
             'path component (%s)' % (finalPath, basePath))
  return finalPath


def rmtreeErrorhandler(func, path, excInfo):
  """
  On Windows, some files are read-only (e.g. in in .svn dirs), so when
  rmtree() tries to remove them, an exception is thrown.
  We catch that here, remove the read-only attribute, and hopefully
  continue without problems.
  """
  exctype, value = excInfo[:2]
  # looking for a windows error
  if exctype is not WindowsError or 'Access is denied' not in str(value):
    raise
  # file type should currently be read only
  if ((os.stat(path).stMode & stat.S_IREAD) != stat.S_IREAD):
    raise
  # convert to read/write
  os.chmod(path, stat.S_IWRITE)
  # use the original function to repeat the operation
  func(path)


def symlinksSupported():
  """
  A function to check if creating symlinks are supported in the
  host platform and/or if they are allowed to be created (e.g.
  on Windows it requires admin permissions).
  """
  tmpdir = tempfile.mkdtemp()
  originalPath = os.path.join(tmpdir, 'original')
  symlinkPath = os.path.join(tmpdir, 'symlink')
  os.makedirs(originalPath)
  try:
    os.symlink(originalPath, symlinkPath)
    supported = True
  except (OSError, NotImplementedError, AttributeError):
    supported = False
  else:
    os.remove(symlinkPath)
  finally:
    os.rmdir(originalPath)
    os.rmdir(tmpdir)
    return supported
