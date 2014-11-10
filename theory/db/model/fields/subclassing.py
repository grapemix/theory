"""
Convenience routines for creating non-trivial Field subclasses, as well as
backwards compatibility utilities.

Add SubfieldBase as the metaclass for your Field subclass, implement
toPython() and the other necessary methods and everything will work
seamlessly.
"""


class SubfieldBase(type):
  """
  A metaclass for custom Field subclasses. This ensures the modal's attribute
  has the descriptor protocol attached to it.
  """
  def __new__(cls, name, bases, attrs):
    newClass = super(SubfieldBase, cls).__new__(cls, name, bases, attrs)
    newClass.contributeToClass = makeContrib(
      newClass, attrs.get('contributeToClass')
    )
    return newClass


class Creator(object):
  """
  A placeholder class that provides a way to set the attribute on the modal.
  """
  def __init__(self, field):
    self.field = field

  def __get__(self, obj, type=None):
    if obj is None:
      return self
    return obj.__dict__[self.field.name]

  def __set__(self, obj, value):
    obj.__dict__[self.field.name] = self.field.toPython(value)


def makeContrib(superclass, func=None):
  """
  Returns a suitable contributeToClass() method for the Field subclass.

  If 'func' is passed in, it is the existing contributeToClass() method on
  the subclass and it is called before anything else. It is assumed in this
  case that the existing contributeToClass() calls all the necessary
  superclass methods.
  """
  def contributeToClass(self, cls, name):
    if func:
      func(self, cls, name)
    else:
      super(superclass, self).contributeToClass(cls, name)
    setattr(cls, self.name, Creator(self))

  return contributeToClass
