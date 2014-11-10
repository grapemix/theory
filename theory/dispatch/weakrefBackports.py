"""
weakrefBackports is a partial backport of the weakref module for python
versions below 3.4.

Copyright (C) 2013 Python Software Foundation, see license.python.txt for
details.

The following changes were made to the original sources during backporting:

 * Added `self` to `super` calls.
 * Removed `from None` when raising exceptions.

"""
from weakref import ref


class WeakMethod(ref):
  """
  A custom `weakref.ref` subclass which simulates a weak reference to
  a bound method, working around the lifetime problem of bound methods.
  """

  __slots__ = "_funcRef", "_methType", "_alive", "__weakref__"

  def __new__(cls, meth, callback=None):
    try:
      obj = meth.__self__
      func = meth.__func__
    except AttributeError:
      raise TypeError("argument should be a bound method, not {}"
              .format(type(meth)))
    def _cb(arg):
      # The self-weakref trick is needed to avoid creating a reference
      # cycle.
      self = selfWr()
      if self._alive:
        self._alive = False
        if callback is not None:
          callback(self)
    self = ref.__new__(cls, obj, _cb)
    self._funcRef = ref(func, _cb)
    self._methType = type(meth)
    self._alive = True
    selfWr = ref(self)
    return self

  def __call__(self):
    obj = super(WeakMethod, self).__call__()
    func = self._funcRef()
    if obj is None or func is None:
      return None
    return self._methType(func, obj)

  def __eq__(self, other):
    if isinstance(other, WeakMethod):
      if not self._alive or not other._alive:
        return self is other
      return ref.__eq__(self, other) and self._funcRef == other._funcRef
    return False

  def __ne__(self, other):
    if isinstance(other, WeakMethod):
      if not self._alive or not other._alive:
        return self is not other
      return ref.__ne__(self, other) or self._funcRef != other._funcRef
    return True

  __hash__ = ref.__hash__

