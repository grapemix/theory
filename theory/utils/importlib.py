# Taken from Python 2.7 with permission from/by the original author.
import warnings
import sys

from theory.utils import six
from theory.utils.deprecation import RemovedInTheory19Warning


warnings.warn("theory.utils.importlib will be removed in Theory 1.9.",
  RemovedInTheory19Warning, stacklevel=2)


def _resolveName(name, package, level):
  """Return the absolute name of the module to be imported."""
  if not hasattr(package, 'rindex'):
    raise ValueError("'package' not set to a string")
  dot = len(package)
  for x in range(level, 1, -1):
    try:
      dot = package.rindex('.', 0, dot)
    except ValueError:
      raise ValueError("attempted relative import beyond top-level package")
  return "%s.%s" % (package[:dot], name)


if six.PY3:
  from importlib import import_module as importModule
else:
  def importModule(name, package=None):
    """Import a module.

    The 'package' argument is required when performing a relative import. It
    specifies the package to use as the anchor point from which to resolve the
    relative import to an absolute import.

    """
    if name.startswith('.'):
      if not package:
        raise TypeError("relative imports require the 'package' argument")
      level = 0
      for character in name:
        if character != '.':
          break
        level += 1
      name = _resolveName(name[level:], package, level)
    __import__(name)
    return sys.modules[name]

def importClass(name, package=None):
  """Import a class.

  To import Module.Class directly instead of from Module import Class in programatic

  The 'package' argument is required when performing a relative import. It
  specifies the package to use as the anchor point from which to resolve the
  relative import to an absolute import.

  """
  chunk = name.split(".")
  klassName = chunk[-1]
  moduleName = ".".join(chunk[:-1])
  if moduleName in sys.modules:
    return getattr(sys.modules[moduleName], klassName)

  module = importModule(moduleName, package)
  # Cause problem
  #del sys.modules[moduleName]

  return getattr(module, klassName)

