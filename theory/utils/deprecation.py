import inspect
import warnings


class RemovedInTheory20Warning(PendingDeprecationWarning):
  pass


class RemovedInTheory19Warning(DeprecationWarning):
  pass


RemovedInNextVersionWarning = RemovedInTheory19Warning


class warnAboutRenamedMethod(object):
  def __init__(self, className, oldMethodName, newMethodName, deprecationWarning):
    self.className = className
    self.oldMethodName = oldMethodName
    self.newMethodName = newMethodName
    self.deprecationWarning = deprecationWarning

  def __call__(self, f):
    def wrapped(*args, **kwargs):
      warnings.warn(
        "`%s.%s` is deprecated, use `%s` instead." %
        (self.className, self.oldMethodName, self.newMethodName),
        self.deprecationWarning, 2)
      return f(*args, **kwargs)
    return wrapped


class RenameMethodsBase(type):
  """
  Handles the deprecation paths when renaming a method.

  It does the following:
      1) Define the new method if missing and complain about it.
      2) Define the old method if missing.
      3) Complain whenever an old method is called.

  See #15363 for more details.
  """

  renamedMethods = ()

  def __new__(cls, name, bases, attrs):
    newClass = super(RenameMethodsBase, cls).__new__(cls, name, bases, attrs)

    for base in inspect.getmro(newClass):
      className = base.__name__
      for renamedMethod in cls.renamedMethods:
        oldMethodName = renamedMethod[0]
        oldMethod = base.__dict__.get(oldMethodName)
        newMethodName = renamedMethod[1]
        newMethod = base.__dict__.get(newMethodName)
        deprecationWarning = renamedMethod[2]
        wrapper = warnAboutRenamedMethod(className, *renamedMethod)

        # Define the new method if missing and complain about it
        if not newMethod and oldMethod:
          warnings.warn(
            "`%s.%s` method should be renamed `%s`." %
            (className, oldMethodName, newMethodName),
            deprecationWarning, 2)
          setattr(base, newMethodName, oldMethod)
          setattr(base, oldMethodName, wrapper(oldMethod))

        # Define the old method as a wrapped call to the new method.
        if not oldMethod and newMethod:
          setattr(base, oldMethodName, wrapper(newMethod))

      return newClass
