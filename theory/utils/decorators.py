"Functions that help with dynamically creating decorators for views."

from functools import wraps, update_wrapper, WRAPPER_ASSIGNMENTS

from theory.utils import six


class classonlymethod(classmethod):
  def __get__(self, instance, owner):
    if instance is not None:
      raise AttributeError("This method is available only on the view class.")
    return super(classonlymethod, self).__get__(instance, owner)


def methodDecorator(decorator):
  """
  Converts a function decorator into a method decorator
  """
  # 'func' is a function at the time it is passed to _dec, but will eventually
  # be a method of the class it is defined it.
  def _dec(func):
    def _wrapper(self, *args, **kwargs):
      @decorator
      def boundFunc(*args2, **kwargs2):
        return func.__get__(self, type(self))(*args2, **kwargs2)
      # boundFunc has the signature that 'decorator' expects i.e.  no
      # 'self' argument, but it is a closure over self so it can call
      # 'func' correctly.
      return boundFunc(*args, **kwargs)
    # In case 'decorator' adds attributes to the function it decorates, we
    # want to copy those. We don't have access to boundFunc in this scope,
    # but we can cheat by using it on a dummy function.

    @decorator
    def dummy(*args, **kwargs):
      pass
    update_wrapper(_wrapper, dummy)
    # Need to preserve any existing attributes of 'func', including the name.
    update_wrapper(_wrapper, func)

    return _wrapper

  update_wrapper(_dec, decorator, assigned=availableAttrs(decorator))
  # Change the name to aid debugging.
  if hasattr(decorator, '__name__'):
    _dec.__name__ = 'methodDecorator(%s)' % decorator.__name__
  else:
    _dec.__name__ = 'methodDecorator(%s)' % decorator.__class__.__name__
  return _dec


def decoratorFromMiddlewareWithArgs(middlewareClass):
  """
  Like decoratorFromMiddleware, but returns a function
  that accepts the arguments to be passed to the middlewareClass.
  Use like::

     cachePage = decoratorFromMiddlewareWithArgs(CacheMiddleware)
     # ...

     @cachePage(3600)
     def myView(request):
       # ...
  """
  return makeMiddlewareDecorator(middlewareClass)


def decoratorFromMiddleware(middlewareClass):
  """
  Given a middleware class (not an instance), returns a view decorator. This
  lets you use middleware functionality on a per-view basis. The middleware
  is created with no params passed.
  """
  return makeMiddlewareDecorator(middlewareClass)()


def availableAttrs(fn):
  """
  Return the list of functools-wrappable attributes on a callable.
  This is required as a workaround for http://bugs.python.org/issue3445
  under Python 2.
  """
  if six.PY3:
    return WRAPPER_ASSIGNMENTS
  else:
    return tuple(a for a in WRAPPER_ASSIGNMENTS if hasattr(fn, a))


def makeMiddlewareDecorator(middlewareClass):
  def _makeDecorator(*mArgs, **mKwargs):
    middleware = middlewareClass(*mArgs, **mKwargs)

    def _decorator(viewFunc):
      @wraps(viewFunc, assigned=availableAttrs(viewFunc))
      def _wrappedView(request, *args, **kwargs):
        if hasattr(middleware, 'processRequest'):
          result = middleware.processRequest(request)
          if result is not None:
            return result
        if hasattr(middleware, 'processView'):
          result = middleware.processView(request, viewFunc, args, kwargs)
          if result is not None:
            return result
        try:
          response = viewFunc(request, *args, **kwargs)
        except Exception as e:
          if hasattr(middleware, 'processException'):
            result = middleware.processException(request, e)
            if result is not None:
              return result
          raise
        if hasattr(response, 'render') and callable(response.render):
          if hasattr(middleware, 'processTemplateResponse'):
            response = middleware.processTemplateResponse(request, response)
          # Defer running of processResponse until after the template
          # has been rendered:
          if hasattr(middleware, 'processResponse'):
            callback = lambda response: middleware.processResponse(request, response)
            response.addPostRenderCallback(callback)
        else:
          if hasattr(middleware, 'processResponse'):
            return middleware.processResponse(request, response)
        return response
      return _wrappedView
    return _decorator
  return _makeDecorator
