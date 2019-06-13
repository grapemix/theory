# -*- coding: utf-8 -*-
#!/usr/bin/env python
##### System wide lib #####
import fileinput
import imp
import os
from subprocess import check_output
import sys

##### Theory lib #####
from theory.conf import settings
from theory.core.resourceScan import *
from theory.utils.importlib import importModule

##### Theory third-party lib #####

##### Local app #####

##### Theory app #####

##### Misc #####

FILE_MODULE = 1
DIR_MODULE = 2

__all__ = ('reprobeAllModule',)

def setupEnviron(settingsMod, originalSettingsPath=None):
  """
  Configures the runtime environment. This can also be used by external
  scripts wanting to set up a similar environment to manage.py.
  Returns the mood directory (assuming the passed settings module is
  directly in the mood directory).

  The "originalSettingsPath" parameter is optional, but recommended, since
  trying to work out the original path from the module can be problematic.
  """
  # Add this mood to sys.path so that it's importable in the conventional
  # way. For example, if this file (manage.py) lives in a directory
  # "mymood", this code would add "/path/to/mymood" to sys.path.
  if '__init__.py' in settingsMod.__file__:
    p = os.path.dirname(settingsMod.__file__)
  else:
    p = settingsMod.__file__
  moodDirectory, settings_filename = os.path.split(p)
  if moodDirectory == os.curdir or not moodDirectory:
    moodDirectory = os.getcwd()
  moodName = os.path.basename(moodDirectory)

  # Strip filename suffix to get the module name.
  settingsName = os.path.splitext(settings_filename)[0]

  # Strip $py for Jython compiled files (like settings$py.class)
  if settingsName.endswith("$py"):
    settingsName = settingsName[:-3]

  # Set THEORY_SETTINGS_MODULE appropriately.
  if originalSettingsPath:
    os.environ['THEORY_SETTINGS_MODULE'] = originalSettingsPath
  else:
    os.environ['THEORY_SETTINGS_MODULE'] = '%s.%s' % (moodName, settingsName)

  # Import the mood module. We add the parent directory to PYTHONPATH to
  # avoid some of the path errors new users can have.
  sys.path.append(os.path.join(moodDirectory, os.pardir))
  moodModule = importModule(moodName)
  sys.path.pop()

  return moodDirectory

def detectScreenResolution(configPath):
  resolution = []
  for i in check_output("xrandr").split("\n"):
    if "*" in i:
      width, height = i.split()[0].split("x")
      resolution.append(str((width, height)))

  for line in fileinput.input(configPath, inplace=True):
    if line == "RESOLUTION = ()":
      print("RESOLUTION = ({0},)".format(",".join(resolution)))
    elif line == "\n":
      continue
    else:
      print(line,)

def checkModuleType(path):
  if(os.path.isfile(path)):
    return FILE_MODULE
  elif(os.path.isdir(path)):
    return DIR_MODULE

def findFilesInAppDir(appName, dirName, isIncludeInit=False):
  """
  Determines the path to the management module for the given appName,
  without actually importing the application or the management module.

  Raises ImportError if the management module cannot be found for any reason.
  """
  parts = appName.split('.')
  parts.append(dirName)
  parts.reverse()
  part = parts.pop()
  path = None

  # When using manage.py, the project module is added to the path,
  # loaded, then removed from the path. This means that
  # testproject.testapp.models can be loaded in future, even if
  # testproject isn't in the path. When looking for the management
  # module, we need look for the case where the project name is part
  # of the appName but the project directory itself isn't on the path.
  try:
    f, path, descr = imp.find_module(part,path)
  except ImportError as e:
    if os.path.basename(os.getcwd()) != part:
      raise e

  while parts:
    part = parts.pop()
    f, path, descr = imp.find_module(part, path and [path] or None)

  if(isIncludeInit):
    filterFxn = lambda i: i.endswith(".py")
  else:
    filterFxn = lambda i: i.endswith(".py") and i!="__init__.py"
  try:
    r = (path, [i[:-3] for i in os.listdir(path) if(filterFxn(i))])
  except OSError as e:
    if(checkModuleType(path)==FILE_MODULE):
      return ("/".join(path.split("/")[:-1]), ["__init__"])
    else:
      raise e
  return r

class ModuleLoader(object):
  _lstPackFxn = lambda x, y, z: x

  @property
  def lstPackFxn(self):
    return self._lstPackFxn

  @lstPackFxn.setter
  def lstPackFxn(self, lstPackFxn):
    self._lstPackFxn = lstPackFxn

  def __init__(self, scanManager, dirName, apps):
    self.scanManager = scanManager
    self.dirName = dirName
    self.apps = apps

  def postPackFxn(self, o):
    return o

  # ok, that's ugly, should be rewrite it later
  def postPackFxnForTheory(self, lst):
    return lst

  def load(self, isDropAll):
    if isDropAll:
      (path, fileList) = findFilesInAppDir("theory.apps", self.dirName, True)
    else:
      path = "Dummy"

    if(path is not None):
      scanManager = self.scanManager()
      if isDropAll:
        scanManager.drop()
        scanManager.paramList = self.postPackFxnForTheory(
            self.lstPackFxn(fileList, "theory.apps", path)
            )

      for appName in self.apps:
        if not isDropAll:
          scanManager.drop(appName)
        try:
          (path, fileList) = findFilesInAppDir(appName, self.dirName, True)
          scanManager.paramList.extend(
              self.postPackFxn(self.lstPackFxn(fileList, appName, path))
              )
        except ImportError:
          pass # No module - ignore this app
      scanManager.scan()

class CommandModuleLoader(ModuleLoader):
  def postPackFxnForTheory(self, lst):
    # TODO: should move this config into somewhere
    moodCommandRel = {
      "tester": ["dev"],
      "loadDbData": ["norm"],
      "listCommand": ["norm"],
      "probeModule": ["norm"],
      "switchMood": ["norm"],
      "filenameScanner": ["norm"],
      "nextStep": ["norm"],
      "createApp": ["dev"],
      "createCmd": ["dev"],
      "modelQuery": ["norm"],
      "modelSelect": ["norm"],
      "modelTblEdit": ["norm"],
      "modelTblDel": ["norm"],
      "modelUpsert": ["norm"],
      "dumpdata": ["norm"],
      "loaddata": ["norm"],
      "flush": ["norm"],
      "makeMigration": ["norm"],
      "migrate": ["norm"],
      "infect": ["dev"],
      "manageAppDb": ["dev"],
      "updateUiApi": ["dev"],
    }
    for o in lst:
      if o[1] in moodCommandRel:
        o[-1] = moodCommandRel[o[1]]
    return lst

  def postPackFxn(self, lst):
    for o in lst:
     if o[0] in self.moodAppRel:
        o[-1] = self.moodAppRel[o[0]]
    return lst

def probeApps(apps, isDropAll=False):
  moodAppRel = {}
  for moodDirName in settings.INSTALLED_MOODS:
    config = importModule("%s.config" % (moodDirName))
    for appName in config.APPS:
      if appName in moodAppRel:
        moodAppRel[appName].append(moodDirName)
      else:
        moodAppRel[appName] = [moodDirName]


  moduleLoader = ModuleLoader(ModelScanManager, "model", apps)
  moduleLoader.lstPackFxn = \
      lambda lst, appName, path: [".".join([appName, i]) for i in lst]
  moduleLoader.load(isDropAll)

  moduleLoader = ModuleLoader(AdapterScanManager, "adapter", apps)
  moduleLoader.lstPackFxn = \
      lambda lst, appName, path: [".".join([appName, i]) for i in lst]
  moduleLoader.load(isDropAll)

  moduleLoader = CommandModuleLoader(CommandScanManager, "command", apps)
  moduleLoader.moodAppRel = moodAppRel
  moduleLoader.lstPackFxn = \
      lambda lst, appName, path:\
        [[appName, i, os.path.join(path, i + ".py"), ["lost"]] for i in lst]
  moduleLoader.load(isDropAll)

def reprobeAllModule(settingsMod, argv=None):
  """
  Returns a dictionary mapping command names to their callback applications.

  This works by looking for a management.commands package in theory.core, and
  in each installed application -- if a commands package exists, all commands
  in that package are registered.

  Core commands are always included. If a settings module has been
  specified, user-defined commands will also be included, the
  startmood command will be disabled, and the startapp command
  will be modified to use the directory in which the settings module appears.

  The dictionary is in the format {commandName: appName}. Key-value
  pairs from this dictionary can then be used in calls to
  loadCommandClass(appName, commandName)

  If a specific version of a command must be loaded (e.g., with the
  startapp command), the instantiated module can be placed in the
  dictionary in place of the application name.

  The dictionary is cached on the first call and reused on subsequent
  calls.
  """
  if settingsMod is not None:
    setupEnviron(settingsMod)

  # Find the installed apps
  try:
    apps = settings.INSTALLED_APPS
  except (AttributeError, EnvironmentError, ImportError):
    apps = []

  # Find all mood directory
  settings.INSTALLED_MOODS = list(settings.INSTALLED_MOODS)
  settings.INSTALLED_MOODS.append("norm")
  settings.INSTALLED_MOODS = tuple(settings.INSTALLED_MOODS)
  probeApps(apps, isDropAll=True)
