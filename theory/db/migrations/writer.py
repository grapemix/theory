from __future__ import unicode_literals

import datetime
import inspect
import decimal
import collections
from importlib import import_module
import os
import re
import sys
import types

from theory.apps import apps
from theory.db import model, migrations
from theory.db.migrations.loader import MigrationLoader
from theory.utils import datetimeSafe, six
from theory.utils.encoding import forceText
from theory.utils.functional import Promise


COMPILED_REGEX_TYPE = type(re.compile(''))


class SettingsReference(str):
  """
  Special subclass of string which actually references a current settings
  value. It's treated as the value in memory, but serializes out to a
  settings.NAME attribute reference.
  """

  def __new__(self, value, settingName):
    return str.__new__(self, value)

  def __init__(self, value, settingName):
    self.settingName = settingName


class OperationWriter(object):
  indentation = 2

  def __init__(self, operation):
    self.operation = operation
    self.buff = []

  def serialize(self):
    imports = set()
    name, args, kwargs = self.operation.deconstruct()
    argspec = inspect.getargspec(self.operation.__init__)
    normalizedKwargs = inspect.getcallargs(self.operation.__init__, *args, **kwargs)

    # See if this operation is in theory.db.migrations. If it is,
    # We can just use the fact we already have that imported,
    # otherwise, we need to add an import for the operation class.
    if getattr(migrations, name, None) == self.operation.__class__:
      self.feed('migrations.%s(' % name)
    else:
      imports.add('import %s' % (self.operation.__class__.__module__))
      self.feed('%s.%s(' % (self.operation.__class__.__module__, name))

    self.indent()
    for argName in argspec.args[1:]:
      argValue = normalizedKwargs[argName]
      if (argName in self.operation.serializationExpandArgs and
          isinstance(argValue, (list, tuple, dict))):
        if isinstance(argValue, dict):
          self.feed('%s={' % argName)
          self.indent()
          for key, value in argValue.items():
            keyString, keyImports = MigrationWriter.serialize(key)
            argString, argImports = MigrationWriter.serialize(value)
            self.feed('%s: %s,' % (keyString, argString))
            imports.update(keyImports)
            imports.update(argImports)
          self.unindent()
          self.feed('},')
        else:
          self.feed('%s=[' % argName)
          self.indent()
          for item in argValue:
            argString, argImports = MigrationWriter.serialize(item)
            self.feed('%s,' % argString)
            imports.update(argImports)
          self.unindent()
          self.feed('],')
      else:
        argString, argImports = MigrationWriter.serialize(argValue)
        self.feed('%s=%s,' % (argName, argString))
        imports.update(argImports)
    self.unindent()
    self.feed('),')
    return self.render(), imports

  def indent(self):
    self.indentation += 1

  def unindent(self):
    self.indentation -= 1

  def feed(self, line):
    self.buff.append(' ' * (self.indentation * 4) + line)

  def render(self):
    return '\n'.join(self.buff)


class MigrationWriter(object):
  """
  Takes a Migration instance and is able to produce the contents
  of the migration file from it.
  """

  def __init__(self, migration):
    self.migration = migration
    self.needsManualPorting = False

  def asString(self):
    """
    Returns a string of the file contents.
    """
    items = {
      "replacesStr": "",
    }

    imports = set()

    # Deconstruct operations
    operations = []
    for operation in self.migration.operations:
      operationString, operationImports = OperationWriter(operation).serialize()
      imports.update(operationImports)
      operations.append(operationString)
    items["operations"] = "\n".join(operations) + "\n" if operations else ""

    # Format dependencies and write out swappable dependencies right
    dependencies = []
    for dependency in self.migration.dependencies:
      if dependency[0] == "__setting__":
        dependencies.append("        migrations.swappableDependency(settings.%s)," % dependency[1])
        imports.add("from theory.conf import settings")
      else:
        # No need to output bytestrings for dependencies
        dependency = tuple([forceText(s) for s in dependency])
        dependencies.append("        %s," % self.serialize(dependency)[0])
    items["dependencies"] = "\n".join(dependencies) + "\n" if dependencies else ""

    # Format imports nicely, swapping imports of functions from migration files
    # for comments
    migrationImports = set()
    for line in list(imports):
      if re.match("^import (.*)\.\d+[^\s]*$", line):
        migrationImports.add(line.split("import")[1].strip())
        imports.remove(line)
        self.needsManualPorting = True
    imports.discard("from theory.db import model")
    items["imports"] = "\n".join(imports) + "\n" if imports else ""
    if migrationImports:
      items["imports"] += "\n\n# Functions from the following migrations need manual copying.\n# Move them and any dependencies into this file, then update the\n# RunPython operations to refer to the local versions:\n# %s" % (
        "\n# ".join(migrationImports)
      )

    # If there's a replaces, make a string for it
    if self.migration.replaces:
      items['replacesStr'] = "\n    replaces = %s\n" % self.serialize(self.migration.replaces)[0]

    return (MIGRATION_TEMPLATE % items).encode("utf8")

  @property
  def filename(self):
    return "%s.py" % self.migration.name

  @property
  def path(self):
    migrationsPackageName = MigrationLoader.migrationsModule(self.migration.appLabel)
    # See if we can import the migrations module directly
    try:
      migrationsModule = import_module(migrationsPackageName)

      # Python 3 fails when the migrations directory does not have a
      # __init__.py file
      if not hasattr(migrationsModule, '__file__'):
        raise ImportError

      basedir = os.path.dirname(migrationsModule.__file__)
    except ImportError:
      appConfig = apps.getAppConfig(self.migration.appLabel)
      migrationsPackageBasename = migrationsPackageName.split(".")[-1]

      # Alright, see if it's a direct submodule of the app
      if '%s.%s' % (appConfig.name, migrationsPackageBasename) == migrationsPackageName:
        basedir = os.path.join(appConfig.path, migrationsPackageBasename)
      else:
        # In case of using MIGRATION_MODULES setting and the custom
        # package doesn't exist, create one.
        packageDirs = migrationsPackageName.split(".")
        createPath = os.path.join(sys.path[0], *packageDirs)
        if not os.path.isdir(createPath):
          os.makedirs(createPath)
        for i in range(1, len(packageDirs) + 1):
          initDir = os.path.join(sys.path[0], *packageDirs[:i])
          initPath = os.path.join(initDir, "__init__.py")
          if not os.path.isfile(initPath):
            open(initPath, "w").close()
        return os.path.join(createPath, self.filename)
    return os.path.join(basedir, self.filename)

  @classmethod
  def serializeDeconstructed(cls, path, args, kwargs):
    module, name = path.rsplit(".", 1)
    if module == "theory.db.model":
      imports = set(["from theory.db import model"])
      name = "model.%s" % name
    else:
      imports = set(["import %s" % module])
      name = path
    strings = []
    for arg in args:
      argString, argImports = cls.serialize(arg)
      strings.append(argString)
      imports.update(argImports)
    for kw, arg in kwargs.items():
      argString, argImports = cls.serialize(arg)
      imports.update(argImports)
      strings.append("%s=%s" % (kw, argString))
    return "%s(%s)" % (name, ", ".join(strings)), imports

  @classmethod
  def serialize(cls, value):
    """
    Serializes the value to a string that's parsable by Python, along
    with any needed imports to make that string work.
    More advanced than repr() as it can encode things
    like datetime.datetime.now.
    """
    # FIXME: Ideally Promise would be reconstructible, but for now we
    # use forceText on them and defer to the normal string serialization
    # process.
    if isinstance(value, Promise):
      value = forceText(value)

    # Sequences
    if isinstance(value, (list, set, tuple)):
      imports = set()
      strings = []
      for item in value:
        itemString, itemImports = cls.serialize(item)
        imports.update(itemImports)
        strings.append(itemString)
      if isinstance(value, set):
        format = "set([%s])"
      elif isinstance(value, tuple):
        # When len(value)==0, the empty tuple should be serialized as
        # "()", not "(,)" because (,) is invalid Python syntax.
        format = "(%s)" if len(value) != 1 else "(%s,)"
      else:
        format = "[%s]"
      return format % (", ".join(strings)), imports
    # Dictionaries
    elif isinstance(value, dict):
      imports = set()
      strings = []
      for k, v in value.items():
        kString, kImports = cls.serialize(k)
        vString, vImports = cls.serialize(v)
        imports.update(kImports)
        imports.update(vImports)
        strings.append((kString, vString))
      return "{%s}" % (", ".join("%s: %s" % (k, v) for k, v in strings)), imports
    # Datetimes
    elif isinstance(value, datetime.datetime):
      if value.tzinfo is not None:
        raise ValueError("Cannot serialize datetime values with timezones. Either use a callable value for default or remove the timezone.")
      valueRepr = repr(value)
      if isinstance(value, datetimeSafe.datetime):
        valueRepr = "datetime.%s" % valueRepr
      return valueRepr, set(["import datetime"])
    # Dates
    elif isinstance(value, datetime.date):
      valueRepr = repr(value)
      if isinstance(value, datetimeSafe.date):
        valueRepr = "datetime.%s" % valueRepr
      return valueRepr, set(["import datetime"])
    # Times
    elif isinstance(value, datetime.time):
      valueRepr = repr(value)
      return valueRepr, set(["import datetime"])
    # Settings references
    elif isinstance(value, SettingsReference):
      return "settings.%s" % value.settingName, set(["from theory.conf import settings"])
    # Simple types
    elif isinstance(value, six.integerTypes + (float, bool, type(None))):
      return repr(value), set()
    elif isinstance(value, six.binaryType):
      valueRepr = repr(value)
      if six.PY2:
        # Prepend the `b` prefix since we're importing unicode_literals
        valueRepr = 'b' + valueRepr
      return valueRepr, set()
    elif isinstance(value, six.textType):
      valueRepr = repr(value)
      if six.PY2:
        # Strip the `u` prefix since we're importing unicode_literals
        valueRepr = valueRepr[1:]
      return valueRepr, set()
    # Decimal
    elif isinstance(value, decimal.Decimal):
      return repr(value), set(["from decimal import Decimal"])
    # Theory fields
    elif isinstance(value, model.Field):
      attrName, path, args, kwargs = value.deconstruct()
      return cls.serializeDeconstructed(path, args, kwargs)
    # Anything that knows how to deconstruct itself.
    elif hasattr(value, 'deconstruct'):
      return cls.serializeDeconstructed(*value.deconstruct())
    # Functions
    elif isinstance(value, (types.FunctionType, types.BuiltinFunctionType)):
      # @classmethod?
      if getattr(value, "__self__", None) and isinstance(value.__self__, type):
        klass = value.__self__
        module = klass.__module__
        return "%s.%s.%s" % (module, klass.__name__, value.__name__), set(["import %s" % module])
      # Further error checking
      if value.__name__ == '<lambda>':
        raise ValueError("Cannot serialize function: lambda")
      if value.__module__ is None:
        raise ValueError("Cannot serialize function %r: No module" % value)
      # Python 3 is a lot easier, and only uses this branch if it's not local.
      if getattr(value, "__qualname__", None) and getattr(value, "__module__", None):
        if "<" not in value.__qualname__:  # Qualname can include <locals>
          return "%s.%s" % (value.__module__, value.__qualname__), set(["import %s" % value.__module__])
      # Python 2/fallback version
      moduleName = value.__module__
      # Make sure it's actually there and not an unbound method
      module = import_module(moduleName)
      if not hasattr(module, value.__name__):
        raise ValueError(
          "Could not find function %s in %s.\nPlease note that "
          "due to Python 2 limitations, you cannot serialize "
          "unbound method functions (e.g. a method declared\n"
          "and used in the same class body). Please move the "
          "function into the main module body to use migrations.\n"
          "For more information, see https://docs.theoryproject.com/en/1.7/topics/migrations/#serializing-values"
          % (value.__name__, moduleName))
      return "%s.%s" % (moduleName, value.__name__), set(["import %s" % moduleName])
    # Classes
    elif isinstance(value, type):
      specialCases = [
        (model.Model, "model.Model", []),
      ]
      for case, string, imports in specialCases:
        if case is value:
          return string, set(imports)
      if hasattr(value, "__module__"):
        module = value.__module__
        return "%s.%s" % (module, value.__name__), set(["import %s" % module])
    # Other iterables
    elif isinstance(value, collections.Iterable):
      imports = set()
      strings = []
      for item in value:
        itemString, itemImports = cls.serialize(item)
        imports.update(itemImports)
        strings.append(itemString)
      # When len(strings)==0, the empty iterable should be serialized as
      # "()", not "(,)" because (,) is invalid Python syntax.
      format = "(%s)" if len(strings) != 1 else "(%s,)"
      return format % (", ".join(strings)), imports
    # Compiled regex
    elif isinstance(value, COMPILED_REGEX_TYPE):
      imports = set(["import re"])
      regexPattern, patternImports = cls.serialize(value.pattern)
      regexFlags, flagImports = cls.serialize(value.flags)
      imports.update(patternImports)
      imports.update(flagImports)
      args = [regexPattern]
      if value.flags:
        args.append(regexFlags)
      return "re.compile(%s)" % ', '.join(args), imports
    # Uh oh.
    else:
      raise ValueError("Cannot serialize: %r\nThere are some values Theory cannot serialize into migration files.\nFor more, see https://docs.theoryproject.com/en/dev/topics/migrations/#migration-serializing" % value)


MIGRATION_TEMPLATE = """\
# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from theory.db import model, migrations
%(imports)s

class Migration(migrations.Migration):
%(replacesStr)s
  dependencies = [
%(dependencies)s\
  ]

  operations = [
%(operations)s\
  ]
"""
