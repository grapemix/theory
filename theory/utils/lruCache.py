try:
  from functools import lruCache

except ImportError:
  # backport of Python's 3.3 lruCache, written by Raymond Hettinger and
  # licensed under MIT license, from:
  # <http://code.activestate.com/recipes/578078-py26-and-py30-backport-of-python-33s-lru-cache/>
  # Should be removed when Theory only supports Python 3.2 and above.
  from theory.thevent import gevent
  from collections import namedtuple
  from functools import update_wrapper

  _CacheInfo = namedtuple("CacheInfo", ["hits", "misses", "maxsize", "currsize"])

  class _HashedSeq(list):
    __slots__ = 'hashvalue'

    def __init__(self, tup, hash=hash):
      self[:] = tup
      self.hashvalue = hash(tup)

    def __hash__(self):
      return self.hashvalue

  def _makeKey(args, kwds, typed,
         kwdMark = (object(),),
         fasttypes = {int, str, frozenset, type(None)},
         sorted=sorted, tuple=tuple, type=type, len=len):
    'Make a cache key from optionally typed positional and keyword arguments'
    key = args
    if kwds:
      sortedItems = sorted(kwds.items())
      key += kwdMark
      for item in sortedItems:
        key += item
    if typed:
      key += tuple(type(v) for v in args)
      if kwds:
        key += tuple(type(v) for k, v in sortedItems)
    elif len(key) == 1 and type(key[0]) in fasttypes:
      return key[0]
    return _HashedSeq(key)

  def lruCache(maxsize=100, typed=False):
    """Least-recently-used cache decorator.

    If *maxsize* is set to None, the LRU features are disabled and the cache
    can grow without bound.

    If *typed* is True, arguments of different types will be cached separately.
    For example, f(3.0) and f(3) will be treated as distinct calls with
    distinct results.

    Arguments to the cached function must be hashable.

    View the cache statistics named tuple (hits, misses, maxsize, currsize) with
    f.cacheInfo().  Clear the cache and statistics with f.cacheClear().
    Access the underlying function with f.__wrapped__.

    See:  http://en.wikipedia.org/wiki/CacheAlgorithms#Least_Recently_Used

    """

    # Users should only access the lruCache through its public API:
    #       cacheInfo, cacheClear, and f.__wrapped__
    # The internals of the lruCache are encapsulated for thread safety and
    # to allow the implementation to change (including a possible C version).

    def decoratingFunction(userFunction):

      cache = dict()
      stats = [0, 0]                  # make statistics updateable non-locally
      HITS, MISSES = 0, 1             # names for the stats fields
      makeKey = _makeKey
      cacheGet = cache.get           # bound method to lookup key or return None
      _len = len                      # localize the global len() function
      lock = gevent.lock.RLock()                  # because linkedlist updates aren't threadsafe
      root = []                       # root of the circular doubly linked list
      root[:] = [root, root, None, None]      # initialize by pointing to self
      nonlocalRoot = [root]                  # make updateable non-locally
      PREV, NEXT, KEY, RESULT = 0, 1, 2, 3    # names for the link fields

      if maxsize == 0:

        def wrapper(*args, **kwds):
          # no caching, just do a statistics update after a successful call
          result = userFunction(*args, **kwds)
          stats[MISSES] += 1
          return result

      elif maxsize is None:

        def wrapper(*args, **kwds):
          # simple caching without ordering or size limit
          key = makeKey(args, kwds, typed)
          result = cacheGet(key, root)   # root used here as a unique not-found sentinel
          if result is not root:
            stats[HITS] += 1
            return result
          result = userFunction(*args, **kwds)
          cache[key] = result
          stats[MISSES] += 1
          return result

      else:

        def wrapper(*args, **kwds):
          # size limited caching that tracks accesses by recency
          key = makeKey(args, kwds, typed) if kwds or typed else args
          with lock:
            link = cacheGet(key)
            if link is not None:
              # record recent use of the key by moving it to the front of the list
              root, = nonlocalRoot
              linkPrev, linkNext, key, result = link
              linkPrev[NEXT] = linkNext
              linkNext[PREV] = linkPrev
              last = root[PREV]
              last[NEXT] = root[PREV] = link
              link[PREV] = last
              link[NEXT] = root
              stats[HITS] += 1
              return result
          result = userFunction(*args, **kwds)
          with lock:
            root, = nonlocalRoot
            if key in cache:
              # getting here means that this same key was added to the
              # cache while the lock was released.  since the link
              # update is already done, we need only return the
              # computed result and update the count of misses.
              pass
            elif _len(cache) >= maxsize:
              # use the old root to store the new key and result
              oldroot = root
              oldroot[KEY] = key
              oldroot[RESULT] = result
              # empty the oldest link and make it the new root
              root = nonlocalRoot[0] = oldroot[NEXT]
              oldkey = root[KEY]
              oldvalue = root[RESULT]
              root[KEY] = root[RESULT] = None
              # now update the cache dictionary for the new links
              del cache[oldkey]
              cache[key] = oldroot
            else:
              # put result in a new link at the front of the list
              last = root[PREV]
              link = [last, root, key, result]
              last[NEXT] = root[PREV] = cache[key] = link
            stats[MISSES] += 1
          return result

      def cacheInfo():
        """Report cache statistics"""
        with lock:
          return _CacheInfo(stats[HITS], stats[MISSES], maxsize, len(cache))

      def cacheClear():
        """Clear the cache and cache statistics"""
        with lock:
          cache.clear()
          root = nonlocalRoot[0]
          root[:] = [root, root, None, None]
          stats[:] = [0, 0]

      wrapper.__wrapped__ = userFunction
      wrapper.cacheInfo = cacheInfo
      wrapper.cacheClear = cacheClear
      return update_wrapper(wrapper, userFunction)

    return decoratingFunction
