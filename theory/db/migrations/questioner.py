from __future__ import unicode_literals

import importlib
import os
import sys

from theory.apps import apps
from theory.utils import datetimeSafe, six
from theory.utils.six.moves import input

from .loader import MIGRATIONS_MODULE_NAME


class MigrationQuestioner(object):
  """
  Gives the autodetector responses to questions it might have.
  This base class has a built-in noninteractive mode, but the
  interactive subclass is what the command-line arguments will use.
  """

  def __init__(self, defaults=None, specifiedApps=None, dryRun=None):
    self.defaults = defaults or {}
    self.specifiedApps = specifiedApps or set()
    self.dryRun = dryRun

  def askInitial(self, appLabel):
    "Should we create an initial migration for the app?"
    # If it was specified on the command line, definitely true
    if appLabel in self.specifiedApps:
      return True
    # Otherwise, we look to see if it has a migrations module
    # without any Python files in it, apart from __init__.py.
    # Apps from the new app template will have these; the python
    # file check will ensure we skip South ones.
    try:
      appConfig = apps.getAppConfig(appLabel)
    except LookupError:         # It's a fake app.
      return self.defaults.get("askInitial", False)
    migrationsImportPath = "%s.%s" % (appConfig.name, MIGRATIONS_MODULE_NAME)
    try:
      migrationsModule = importlib.import_module(migrationsImportPath)
    except ImportError:
      return self.defaults.get("askInitial", False)
    else:
      if hasattr(migrationsModule, "__file__"):
        filenames = os.listdir(os.path.dirname(migrationsModule.__file__))
      elif hasattr(migrationsModule, "__path__"):
        if len(migrationsModule.__path__) > 1:
          return False
        filenames = os.listdir(list(migrationsModule.__path__)[0])
      return not any(x.endswith(".py") for x in filenames if x != "__init__.py")

  def askNotNullAddition(self, fieldName, modelName):
    "Adding a NOT NULL field to a modal"
    # None means quit
    return None

  def askRename(self, modelName, oldName, newName, fieldInstance):
    "Was this field really renamed?"
    return self.defaults.get("askRename", False)

  def askRenameModel(self, oldModelState, newModelState):
    "Was this modal really renamed?"
    return self.defaults.get("askRenameModel", False)

  def askMerge(self, appLabel):
    "Do you really want to merge these migrations?"
    return self.defaults.get("askMerge", False)


class InteractiveMigrationQuestioner(MigrationQuestioner):

  def _booleanInput(self, question, default=None):
    result = input("%s " % question)
    if not result and default is not None:
      return default
    while len(result) < 1 or result[0].lower() not in "yn":
      result = input("Please answer yes or no: ")
    return result[0].lower() == "y"

  def _choiceInput(self, question, choices):
    print(question)
    for i, choice in enumerate(choices):
      print(" %s) %s" % (i + 1, choice))
    result = input("Select an option: ")
    while True:
      try:
        value = int(result)
        if 0 < value <= len(choices):
          return value
      except ValueError:
        pass
      result = input("Please select a valid option: ")

  def askNotNullAddition(self, fieldName, modelName):
    "Adding a NOT NULL field to a modal"
    if not self.dryRun:
      choice = self._choiceInput(
        "You are trying to add a non-nullable field '%s' to %s without a default;\n" % (fieldName, modelName) +
        "we can't do that (the database needs something to populate existing rows).\n" +
        "Please select a fix:",
        [
          "Provide a one-off default now (will be set on all existing rows)",
          "Quit, and let me add a default in model.py",
        ]
      )
      if choice == 2:
        sys.exit(3)
      else:
        print("Please enter the default value now, as valid Python")
        print("The datetime module is available, so you can do e.g. datetime.date.today()")
        while True:
          if six.PY3:
            # Six does not correctly abstract over the fact that
            # py3 input returns a unicode string, while py2 rawInput
            # returns a bytestring.
            code = input(">>> ")
          else:
            code = input(">>> ").decode(sys.stdin.encoding)
          if not code:
            print("Please enter some code, or 'exit' (with no quotes) to exit.")
          elif code == "exit":
            sys.exit(1)
          else:
            try:
              return eval(code, {}, {"datetime": datetimeSafe})
            except (SyntaxError, NameError) as e:
              print("Invalid input: %s" % e)
    return None

  def askRename(self, modelName, oldName, newName, fieldInstance):
    "Was this field really renamed?"
    return self._booleanInput("Did you rename %s.%s to %s.%s (a %s)? [y/N]" % (modelName, oldName, modelName, newName, fieldInstance.__class__.__name__), False)

  def askRenameModel(self, oldModelState, newModelState):
    "Was this modal really renamed?"
    return self._booleanInput("Did you rename the %s.%s modal to %s? [y/N]" % (oldModelState.appLabel, oldModelState.name, newModelState.name), False)

  def askMerge(self, appLabel):
    return self._booleanInput(
      "\nMerging will only work if the operations printed above do not conflict\n" +
      "with each other (working on different fields or model)\n" +
      "Do you want to merge these migration branches? [y/N]",
      False,
    )
