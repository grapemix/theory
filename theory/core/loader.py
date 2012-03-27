# -*- coding: utf-8 -*-
##### System wide lib #####
import imp
import os
import sys

##### Theory lib #####
from theory.command import fileSelector
from theory.core.commandScan.commandScanManager import CommandScanManager
import theory.db
from theory.model import Command
from theory.utils.importlib import import_module

##### Theory third-party lib #####

##### Local app #####

##### Theory app #####

##### Misc #####

def setup_environ(settings_mod, original_settings_path=None):
  """
  Configures the runtime environment. This can also be used by external
  scripts wanting to set up a similar environment to manage.py.
  Returns the mood directory (assuming the passed settings module is
  directly in the mood directory).

  The "original_settings_path" parameter is optional, but recommended, since
  trying to work out the original path from the module can be problematic.
  """
  # Add this mood to sys.path so that it's importable in the conventional
  # way. For example, if this file (manage.py) lives in a directory
  # "mymood", this code would add "/path/to/mymood" to sys.path.
  if '__init__.py' in settings_mod.__file__:
    p = os.path.dirname(settings_mod.__file__)
  else:
    p = settings_mod.__file__
  mood_directory, settings_filename = os.path.split(p)
  if mood_directory == os.curdir or not mood_directory:
    mood_directory = os.getcwd()
  mood_name = os.path.basename(mood_directory)

  # Strip filename suffix to get the module name.
  settings_name = os.path.splitext(settings_filename)[0]

  # Strip $py for Jython compiled files (like settings$py.class)
  if settings_name.endswith("$py"):
    settings_name = settings_name[:-3]

  # Set THEORY_SETTINGS_MODULE appropriately.
  if original_settings_path:
    os.environ['THEORY_SETTINGS_MODULE'] = original_settings_path
  else:
    os.environ['THEORY_SETTINGS_MODULE'] = '%s.%s' % (mood_name, settings_name)

  # Import the mood module. We add the parent directory to PYTHONPATH to
  # avoid some of the path errors new users can have.
  sys.path.append(os.path.join(mood_directory, os.pardir))
  mood_module = import_module(mood_name)
  sys.path.pop()

  return mood_directory

def find_commands(app_name):
  """
  Determines the path to the management module for the given app_name,
  without actually importing the application or the management module.

  Raises ImportError if the management module cannot be found for any reason.
  """
  parts = app_name.split('.')
  parts.append('command')
  parts.reverse()
  part = parts.pop()
  path = None

  # When using manage.py, the project module is added to the path,
  # loaded, then removed from the path. This means that
  # testproject.testapp.models can be loaded in future, even if
  # testproject isn't in the path. When looking for the management
  # module, we need look for the case where the project name is part
  # of the app_name but the project directory itself isn't on the path.
  try:
    f, path, descr = imp.find_module(part,path)
  except ImportError,e:
    if os.path.basename(os.getcwd()) != part:
      raise e

  while parts:
    part = parts.pop()
    f, path, descr = imp.find_module(part, path and [path] or None)

  return (path, [i[:-3] for i in os.listdir(path) if(i.endswith(".py") and i!="__init__.py")])

def wakeup(settings_mod, argv=None):
  if(Command.objects.all().count()==0):
    reprobeAllModule(settings_mod, argv)

def reprobeAllModule(settings_mod, argv=None):
  """
  Returns a dictionary mapping command names to their callback applications.

  This works by looking for a management.commands package in theory.core, and
  in each installed application -- if a commands package exists, all commands
  in that package are registered.

  Core commands are always included. If a settings module has been
  specified, user-defined commands will also be included, the
  startmood command will be disabled, and the startapp command
  will be modified to use the directory in which the settings module appears.

  The dictionary is in the format {command_name: app_name}. Key-value
  pairs from this dictionary can then be used in calls to
  load_command_class(app_name, command_name)

  If a specific version of a command must be loaded (e.g., with the
  startapp command), the instantiated module can be placed in the
  dictionary in place of the application name.

  The dictionary is cached on the first call and reused on subsequent
  calls.
  """
  print "Reprobing all modules"
  if(settings_mod!=None):
    setup_environ(settings_mod)

  # Find the installed apps
  try:
    from theory.conf import settings
    apps = settings.INSTALLED_APPS
  except (AttributeError, EnvironmentError, ImportError):
    apps = []

  # Find the project directory
  try:
    from theory.conf import settings
    module = import_module(settings.SETTINGS_MODULE)
    project_directory = setup_environ(module, settings.SETTINGS_MODULE)
  except (AttributeError, EnvironmentError, ImportError, KeyError):
    project_directory = None

  # TODO: Find the mood directory

  (path, cmdLst) = find_commands("theory")
  cmdManager = CommandScanManager()
  cmdManager.cmdList = [("theory", i, os.path.join(path, i + ".py"), "dev") for i in cmdLst]
  #probeModule("theory", cmdLst)

  # Find and load the command module for each installed app.
  for app_name in apps:
    try:
      (path, cmdLst) = find_commands(app_name)
      cmdManager.cmdList.extend([(app_name, i, os.path.join(path, i + ".py"), app_name) for i in cmdLst])
      #probeModule(app_name, cmdLst)
      #_commands.update(dict([(name, app_name)
      #                       for name in find_commands(path)]))
    except ImportError:
      pass # No management module - ignore this app
  cmdManager.scan()

  return
