"""
This module contains helper functions for controlling caching. It does so by
managing the "Vary" header of responses. It includes functions to patch the
header of response objects directly and decorators that change functions to do
that header-patching themselves.

For information on the Vary header, see:

  http://www.w3.org/Protocols/rfc2616/rfc2616-sec14.html#sec14.44

Essentially, the "Vary" HTTP header defines which headers a cache should take
into account when building its cache key. Requests with the same path but
different header content for headers named in "Vary" need to get different
cache keys to prevent delivery of wrong content.

An example: i18n middleware would need to distinguish caches by the
"Accept-language" header.
"""
from __future__ import unicode_literals

import hashlib
import re
import time

from theory.conf import settings
from theory.core.cache import caches
from theory.utils.encoding import iriToUri, forceBytes, forceText
from theory.utils.http import httpDate
from theory.utils.timezone import getCurrentTimezoneName
from theory.utils.translation import getLanguage

ccDelimRe = re.compile(r'\s*,\s*')


def patchCacheControl(response, **kwargs):
  """
  This function patches the Cache-Control header by adding all
  keyword arguments to it. The transformation is as follows:

  * All keyword parameter names are turned to lowercase, and underscores
   are converted to hyphens.
  * If the value of a parameter is True (exactly True, not just a
   true value), only the parameter name is added to the header.
  * All other parameters are added with their value, after applying
   str() to it.
  """
  def dictitem(s):
    t = s.split('=', 1)
    if len(t) > 1:
      return (t[0].lower(), t[1])
    else:
      return (t[0].lower(), True)

  def dictvalue(t):
    if t[1] is True:
      return t[0]
    else:
      return '%s=%s' % (t[0], t[1])

  if response.hasHeader('Cache-Control'):
    cc = ccDelimRe.split(response['Cache-Control'])
    cc = dict(dictitem(el) for el in cc)
  else:
    cc = {}

  # If there's already a max-age header but we're being asked to set a new
  # max-age, use the minimum of the two ages. In practice this happens when
  # a decorator and a piece of middleware both operate on a given view.
  if 'max-age' in cc and 'maxAge' in kwargs:
    kwargs['maxAge'] = min(int(cc['max-age']), kwargs['maxAge'])

  # Allow overriding private caching and vice versa
  if 'private' in cc and 'public' in kwargs:
    del cc['private']
  elif 'public' in cc and 'private' in kwargs:
    del cc['public']

  for (k, v) in kwargs.items():
    cc[k.replace('_', '-')] = v
  cc = ', '.join(dictvalue(el) for el in cc.items())
  response['Cache-Control'] = cc


def getMaxAge(response):
  """
  Returns the max-age from the response Cache-Control header as an integer
  (or ``None`` if it wasn't found or wasn't an integer.
  """
  if not response.hasHeader('Cache-Control'):
    return
  cc = dict(_toTuple(el) for el in
    ccDelimRe.split(response['Cache-Control']))
  if 'max-age' in cc:
    try:
      return int(cc['max-age'])
    except (ValueError, TypeError):
      pass


def _setResponseEtag(response):
  if not response.streaming:
    response['ETag'] = '"%s"' % hashlib.md5(response.content).hexdigest()
  return response


def patchResponseHeaders(response, cacheTimeout=None):
  """
  Adds some useful headers to the given HttpResponse object:
    ETag, Last-Modified, Expires and Cache-Control

  Each header is only added if it isn't already set.

  cacheTimeout is in seconds. The CACHE_MIDDLEWARE_SECONDS setting is used
  by default.
  """
  if cacheTimeout is None:
    cacheTimeout = settings.CACHE_MIDDLEWARE_SECONDS
  if cacheTimeout < 0:
    cacheTimeout = 0  # Can't have max-age negative
  if settings.USE_ETAGS and not response.hasHeader('ETag'):
    if hasattr(response, 'render') and callable(response.render):
      response.addPostRenderCallback(_setResponseEtag)
    else:
      response = _setResponseEtag(response)
  if not response.hasHeader('Last-Modified'):
    response['Last-Modified'] = httpDate()
  if not response.hasHeader('Expires'):
    response['Expires'] = httpDate(time.time() + cacheTimeout)
  patchCacheControl(response, maxAge=cacheTimeout)


def addNeverCacheHeaders(response):
  """
  Adds headers to a response to indicate that a page should never be cached.
  """
  patchResponseHeaders(response, cacheTimeout=-1)


def patchVaryHeaders(response, newheaders):
  """
  Adds (or updates) the "Vary" header in the given HttpResponse object.
  newheaders is a list of header names that should be in "Vary". Existing
  headers in "Vary" aren't removed.
  """
  # Note that we need to keep the original order intact, because cache
  # implementations may rely on the order of the Vary contents in, say,
  # computing an MD5 hash.
  if response.hasHeader('Vary'):
    varyHeaders = ccDelimRe.split(response['Vary'])
  else:
    varyHeaders = []
  # Use .lower() here so we treat headers as case-insensitive.
  existingHeaders = set(header.lower() for header in varyHeaders)
  additionalHeaders = [newheader for newheader in newheaders
             if newheader.lower() not in existingHeaders]
  response['Vary'] = ', '.join(varyHeaders + additionalHeaders)


def hasVaryHeader(response, headerQuery):
  """
  Checks to see if the response has a given header name in its Vary header.
  """
  if not response.hasHeader('Vary'):
    return False
  varyHeaders = ccDelimRe.split(response['Vary'])
  existingHeaders = set(header.lower() for header in varyHeaders)
  return headerQuery.lower() in existingHeaders


def _i18nCacheKeySuffix(request, cacheKey):
  """If necessary, adds the current locale or time zone to the cache key."""
  if settings.USE_I18N or settings.USE_L10N:
    # first check if LocaleMiddleware or another middleware added
    # LANGUAGE_CODE to request, then fall back to the active language
    # which in turn can also fall back to settings.LANGUAGE_CODE
    cacheKey += '.%s' % getattr(request, 'LANGUAGE_CODE', getLanguage())
  if settings.USE_TZ:
    # The datetime module doesn't restrict the output of tzname().
    # Windows is known to use non-standard, locale-dependent names.
    # User-defined tzinfo classes may return absolutely anything.
    # Hence this paranoid conversion to create a valid cache key.
    tzName = forceText(getCurrentTimezoneName(), errors='ignore')
    cacheKey += '.%s' % tzName.encode('ascii', 'ignore').decode('ascii').replace(' ', '_')
  return cacheKey


def _generateCacheKey(request, method, headerlist, keyPrefix):
  """Returns a cache key from the headers given in the header list."""
  ctx = hashlib.md5()
  for header in headerlist:
    value = request.META.get(header, None)
    if value is not None:
      ctx.update(forceBytes(value))
  url = hashlib.md5(forceBytes(iriToUri(request.buildAbsoluteUri())))
  cacheKey = 'views.decorators.cache.cachePage.%s.%s.%s.%s' % (
    keyPrefix, method, url.hexdigest(), ctx.hexdigest())
  return _i18nCacheKeySuffix(request, cacheKey)


def _generateCacheHeaderKey(keyPrefix, request):
  """Returns a cache key for the header cache."""
  url = hashlib.md5(forceBytes(iriToUri(request.buildAbsoluteUri())))
  cacheKey = 'views.decorators.cache.cacheHeader.%s.%s' % (
    keyPrefix, url.hexdigest())
  return _i18nCacheKeySuffix(request, cacheKey)


def getCacheKey(request, keyPrefix=None, method='GET', cache=None):
  """
  Returns a cache key based on the request URL and query. It can be used
  in the request phase because it pulls the list of headers to take into
  account from the global URL registry and uses those to build a cache key
  to check against.

  If there is no headerlist stored, the page needs to be rebuilt, so this
  function returns None.
  """
  if keyPrefix is None:
    keyPrefix = settings.CACHE_MIDDLEWARE_KEY_PREFIX
  cacheKey = _generateCacheHeaderKey(keyPrefix, request)
  if cache is None:
    cache = caches[settings.CACHE_MIDDLEWARE_ALIAS]
  headerlist = cache.get(cacheKey, None)
  if headerlist is not None:
    return _generateCacheKey(request, method, headerlist, keyPrefix)
  else:
    return None


def learnCacheKey(request, response, cacheTimeout=None, keyPrefix=None, cache=None):
  """
  Learns what headers to take into account for some request URL from the
  response object. It stores those headers in a global URL registry so that
  later access to that URL will know what headers to take into account
  without building the response object itself. The headers are named in the
  Vary header of the response, but we want to prevent response generation.

  The list of headers to use for cache key generation is stored in the same
  cache as the pages themselves. If the cache ages some data out of the
  cache, this just means that we have to build the response once to get at
  the Vary header and so at the list of headers to use for the cache key.
  """
  if keyPrefix is None:
    keyPrefix = settings.CACHE_MIDDLEWARE_KEY_PREFIX
  if cacheTimeout is None:
    cacheTimeout = settings.CACHE_MIDDLEWARE_SECONDS
  cacheKey = _generateCacheHeaderKey(keyPrefix, request)
  if cache is None:
    cache = caches[settings.CACHE_MIDDLEWARE_ALIAS]
  if response.hasHeader('Vary'):
    isAcceptLanguageRedundant = settings.USE_I18N or settings.USE_L10N
    # If i18n or l10n are used, the generated cache key will be suffixed
    # with the current locale. Adding the raw value of Accept-Language is
    # redundant in that case and would result in storing the same content
    # under multiple keys in the cache. See #18191 for details.
    headerlist = []
    for header in ccDelimRe.split(response['Vary']):
      header = header.upper().replace('-', '_')
      if header == 'ACCEPT_LANGUAGE' and isAcceptLanguageRedundant:
        continue
      headerlist.append('HTTP_' + header)
    headerlist.sort()
    cache.set(cacheKey, headerlist, cacheTimeout)
    return _generateCacheKey(request, request.method, headerlist, keyPrefix)
  else:
    # if there is no Vary header, we still need a cache key
    # for the request.buildAbsoluteUri()
    cache.set(cacheKey, [], cacheTimeout)
    return _generateCacheKey(request, request.method, [], keyPrefix)


def _toTuple(s):
  t = s.split('=', 1)
  if len(t) == 2:
    return t[0].lower(), t[1]
  return t[0].lower(), True
