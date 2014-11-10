# Autoreloading launcher.
# Borrowed from Peter Hunt and the CherryPy project (http://www.cherrypy.org).
# Some taken from Ian Bicking's Paste (http://pythonpaste.org/).
#
# Portions copyright (c) 2004, CherryPy Team (team@cherrypy.org)
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without modification,
# are permitted provided that the following conditions are met:
#
#     * Redistributions of source code must retain the above copyright notice,
#       this list of conditions and the following disclaimer.
#     * Redistributions in binary form must reproduce the above copyright notice,
#       this list of conditions and the following disclaimer in the documentation
#       and/or other materials provided with the distribution.
#     * Neither the name of the CherryPy Team nor the names of its contributors
#       may be used to endorse or promote products derived from this software
#       without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

from __future__ import absoluteImport  # Avoid importing `importlib` from this package.

import os
import signal
import sys
import time
import traceback

from theory.apps import apps
from theory.conf import settings
from theory.core.signals import requestFinished
try:
  from theory.utils.six.moves import _thread as thread
except ImportError:
  from theory.utils.six.moves import _dummyThread as thread

# This import does nothing, but it's necessary to avoid some race conditions
# in the threading module. See http://code.theoryproject.com/ticket/2330 .
try:
  import threading  # NOQA
except ImportError:
  pass

try:
  import termios
except ImportError:
  termios = None

USE_INOTIFY = False
try:
  # Test whether inotify is enabled and likely to work
  import pyinotify

  fd = pyinotify.INotifyWrapper.create().inotifyInit()
  if fd >= 0:
    USE_INOTIFY = True
    os.close(fd)
except ImportError:
  pass

RUN_RELOADER = True

FILE_MODIFIED = 1
I18N_MODIFIED = 2

_mtimes = {}
_win = (sys.platform == "win32")

_errorFiles = []
_cachedModules = set()
_cachedFilenames = []


def genFilenames(onlyNew=False):
  """
  Returns a list of filenames referenced in sys.modules and translation
  files.
  """
  # N.B. ``list(...)`` is needed, because this runs in parallel with
  # application code which might be mutating ``sys.modules``, and this will
  # fail with RuntimeError: cannot mutate dictionary while iterating
  global _cachedModules, _cachedFilenames
  moduleValues = set(sys.modules.values())
  if _cachedModules == moduleValues:
    # No changes in module list, short-circuit the function
    if onlyNew:
      return []
    else:
      return _cachedFilenames

  newModules = moduleValues - _cachedModules
  newFilenames = cleanFiles(
    [filename.__file__ for filename in newModules
     if hasattr(filename, '__file__')])

  if not _cachedFilenames and settings.USE_I18N:
    # Add the names of the .mo files that can be generated
    # by compilemessages management command to the list of files watched.
    basedirs = [os.path.join(os.path.dirname(os.path.dirname(__file__)),
                 'conf', 'locale'),
          'locale']
    for appConfig in reversed(list(apps.getAppConfigs())):
      basedirs.append(os.path.join(appConfig.path, 'locale'))
    basedirs.extend(settings.LOCALE_PATHS)
    basedirs = [os.path.abspath(basedir) for basedir in basedirs
          if os.path.isdir(basedir)]
    for basedir in basedirs:
      for dirpath, dirnames, localeFilenames in os.walk(basedir):
        for filename in localeFilenames:
          if filename.endswith('.mo'):
            newFilenames.append(os.path.join(dirpath, filename))

  _cachedModules = _cachedModules.union(newModules)
  _cachedFilenames += newFilenames
  if onlyNew:
    return newFilenames
  else:
    return _cachedFilenames + cleanFiles(_errorFiles)


def cleanFiles(filelist):
  filenames = []
  for filename in filelist:
    if not filename:
      continue
    if filename.endswith(".pyc") or filename.endswith(".pyo"):
      filename = filename[:-1]
    if filename.endswith("$py.class"):
      filename = filename[:-9] + ".py"
    if os.path.exists(filename):
      filenames.append(filename)
  return filenames


def resetTranslations():
  import gettext
  from theory.utils.translation import transReal
  gettext._translations = {}
  transReal._translations = {}
  transReal._default = None
  transReal._active = threading.local()


def inotifyCodeChanged():
  """
  Checks for changed code using inotify. After being called
  it blocks until a change event has been fired.
  """
  class EventHandler(pyinotify.ProcessEvent):
    modifiedCode = None

    def processDefault(self, event):
      if event.path.endswith('.mo'):
        EventHandler.modifiedCode = I18N_MODIFIED
      else:
        EventHandler.modifiedCode = FILE_MODIFIED

  wm = pyinotify.WatchManager()
  notifier = pyinotify.Notifier(wm, EventHandler())

  def updateWatch(sender=None, **kwargs):
    if sender and getattr(sender, 'handlesFiles', False):
      # No need to update watches when request serves files.
      # (sender is supposed to be a theory.core.handlers.BaseHandler subclass)
      return
    mask = (
      pyinotify.IN_MODIFY |
      pyinotify.IN_DELETE |
      pyinotify.IN_ATTRIB |
      pyinotify.IN_MOVED_FROM |
      pyinotify.IN_MOVED_TO |
      pyinotify.IN_CREATE
    )
    for path in genFilenames(onlyNew=True):
      wm.addWatch(path, mask)

  # New modules may get imported when a request is processed.
  requestFinished.connect(updateWatch)

  # Block until an event happens.
  updateWatch()
  notifier.checkEvents(timeout=None)
  notifier.readEvents()
  notifier.processEvents()
  notifier.stop()

  # If we are here the code must have changed.
  return EventHandler.modifiedCode


def codeChanged():
  global _mtimes, _win
  for filename in genFilenames():
    stat = os.stat(filename)
    mtime = stat.stMtime
    if _win:
      mtime -= stat.stCtime
    if filename not in _mtimes:
      _mtimes[filename] = mtime
      continue
    if mtime != _mtimes[filename]:
      _mtimes = {}
      try:
        del _errorFiles[_errorFiles.index(filename)]
      except ValueError:
        pass
      return I18N_MODIFIED if filename.endswith('.mo') else FILE_MODIFIED
  return False


def checkErrors(fn):
  def wrapper(*args, **kwargs):
    try:
      fn(*args, **kwargs)
    except (ImportError, IndentationError, NameError, SyntaxError,
        TypeError, AttributeError):
      et, ev, tb = sys.excInfo()

      if getattr(ev, 'filename', None) is None:
        # get the filename from the last item in the stack
        filename = traceback.extractTb(tb)[-1][0]
      else:
        filename = ev.filename

      if filename not in _errorFiles:
        _errorFiles.append(filename)

      raise

  return wrapper


def ensureEchoOn():
  if termios:
    fd = sys.stdin
    if fd.isatty():
      attrList = termios.tcgetattr(fd)
      if not attrList[3] & termios.ECHO:
        attrList[3] |= termios.ECHO
        if hasattr(signal, 'SIGTTOU'):
          oldHandler = signal.signal(signal.SIGTTOU, signal.SIG_IGN)
        else:
          oldHandler = None
        termios.tcsetattr(fd, termios.TCSANOW, attrList)
        if oldHandler is not None:
          signal.signal(signal.SIGTTOU, oldHandler)


def reloaderThread():
  ensureEchoOn()
  if USE_INOTIFY:
    fn = inotifyCodeChanged
  else:
    fn = codeChanged
  while RUN_RELOADER:
    change = fn()
    if change == FILE_MODIFIED:
      sys.exit(3)  # force reload
    elif change == I18N_MODIFIED:
      resetTranslations()
    time.sleep(1)


def restartWithReloader():
  while True:
    args = [sys.executable] + ['-W%s' % o for o in sys.warnoptions] + sys.argv
    if sys.platform == "win32":
      args = ['"%s"' % arg for arg in args]
    newEnviron = os.environ.copy()
    newEnviron["RUN_MAIN"] = 'true'
    exitCode = os.spawnve(os.P_WAIT, sys.executable, args, newEnviron)
    if exitCode != 3:
      return exitCode


def pythonReloader(mainFunc, args, kwargs):
  if os.environ.get("RUN_MAIN") == "true":
    thread.startNewThread(mainFunc, args, kwargs)
    try:
      reloaderThread()
    except KeyboardInterrupt:
      pass
  else:
    try:
      exitCode = restartWithReloader()
      if exitCode < 0:
        os.kill(os.getpid(), -exitCode)
      else:
        sys.exit(exitCode)
    except KeyboardInterrupt:
      pass


def jythonReloader(mainFunc, args, kwargs):
  from _systemrestart import SystemRestart
  thread.startNewThread(mainFunc, args)
  while True:
    if codeChanged():
      raise SystemRestart
    time.sleep(1)


def main(mainFunc, args=None, kwargs=None):
  if args is None:
    args = ()
  if kwargs is None:
    kwargs = {}
  if sys.platform.startswith('java'):
    reloader = jythonReloader
  else:
    reloader = pythonReloader

  wrappedMainFunc = checkErrors(mainFunc)
  reloader(wrappedMainFunc, args, kwargs)
