import os
import sys

from . import six

buffering = int(six.PY3)        # No unbuffered text I/O on Python 3 (#20815).

if os.name == 'posix':
  def becomeDaemon(ourHomeDir='.', outLog='/dev/null',
           errLog='/dev/null', umask=0o022):
    "Robustly turn into a UNIX daemon, running in ourHomeDir."
    # First fork
    try:
      if os.fork() > 0:
        sys.exit(0)     # kill off parent
    except OSError as e:
      sys.stderr.write("fork #1 failed: (%d) %s\n" % (e.errno, e.strerror))
      sys.exit(1)
    os.setsid()
    os.chdir(ourHomeDir)
    os.umask(umask)

    # Second fork
    try:
      if os.fork() > 0:
        os._exit(0)
    except OSError as e:
      sys.stderr.write("fork #2 failed: (%d) %s\n" % (e.errno, e.strerror))
      os._exit(1)

    si = open('/dev/null', 'r')
    so = open(outLog, 'a+', buffering)
    se = open(errLog, 'a+', buffering)
    os.dup2(si.fileno(), sys.stdin.fileno())
    os.dup2(so.fileno(), sys.stdout.fileno())
    os.dup2(se.fileno(), sys.stderr.fileno())
    # Set custom file descriptors so that they get proper buffering.
    sys.stdout, sys.stderr = so, se
else:
  def becomeDaemon(ourHomeDir='.', outLog=None, errLog=None, umask=0o022):
    """
    If we're not running under a POSIX system, just simulate the daemon
    mode by doing redirections and directory changing.
    """
    os.chdir(ourHomeDir)
    os.umask(umask)
    sys.stdin.close()
    sys.stdout.close()
    sys.stderr.close()
    if errLog:
      sys.stderr = open(errLog, 'a', buffering)
    else:
      sys.stderr = NullDevice()
    if outLog:
      sys.stdout = open(outLog, 'a', buffering)
    else:
      sys.stdout = NullDevice()

  class NullDevice:
    "A writeable object that writes to nowhere -- like /dev/null."
    def write(self, s):
      pass
