# -*- coding: utf-8 -*-
#!/usr/bin/env python
##### System wide lib #####
from __future__ import unicode_literals
import locale
import os
import re
import sys
import gettext as gettextModule
from theory.thevent import gevent
import warnings

##### Theory lib #####
from theory.utils.importlib import importModule
from theory.utils.datastructures import SortedDict
from theory.utils.encoding import forceStr, forceText
from theory.utils.functional import memoize
from theory.utils._os import upath
from theory.utils.safestring import markSafe, SafeData
from theory.utils import six
from theory.utils.six import StringIO
from theory.utils.translation import TranslatorCommentWarning

##### Theory third-party lib #####

##### Local app #####

##### Theory app #####

##### Misc #####

"""Translation helper functions."""
# Translations are cached in a dictionary for every language+app tuple.
# The active translations are stored by threadid to make them thread local.
_translations = {}
_active = gevent.local.local()

# The default translation is based on the settings file.
_default = None

# This is a cache for normalized accept-header languages to prevent multiple
# file lookups when checking the same locale on repeated requests.
_accepted = {}
_checkedLanguages = {}

# magic gettext number to separate context from message
CONTEXT_SEPARATOR = "\x04"

# Format of Accept-Language header values. From RFC 2616, section 14.4 and 3.9
# and RFC 3066, section 2.1
acceptLanguageRe = re.compile(r'''
    ([A-Za-z]{1,8}(?:-[A-Za-z0-9]{1,8})*|\*)      # "en", "en-au", "x-y-z", "es-419", "*"
    (?:\s*;\s*q=(0(?:\.\d{,3})?|1(?:.0{,3})?))?   # Optional "q=1.00", "q=0.8"
    (?:\s*,\s*|$)                                 # Multiple accepts per header.
    ''', re.VERBOSE)

languageCodePrefixRe = re.compile(r'^/([\w-]+)(/|$)')


def toLocale(language, toLower=False):
  """
  Turns a language name (en-us) into a locale name (en_US). If 'toLower' is
  True, the last component is lower-cased (enUs).
  """
  p = language.find('-')
  if p >= 0:
    if toLower:
      return language[:p].lower()+'_'+language[p+1:].lower()
    else:
      # Get correct locale for sr-latn
      if len(language[p+1:]) > 2:
        return language[:p].lower()+'_'+language[p+1].upper()+language[p+2:].lower()
      return language[:p].lower()+'_'+language[p+1:].upper()
  else:
    return language.lower()

def toLanguage(locale):
  """Turns a locale name (en_US) into a language name (en-us)."""
  p = locale.find('_')
  if p >= 0:
    return locale[:p].lower()+'-'+locale[p+1:].lower()
  else:
    return locale.lower()

class TheoryTranslation(gettextModule.GNUTranslations):
  """
  This class sets up the GNUTranslations context with regard to output
  charset.
  """
  def __init__(self, *args, **kw):
    gettextModule.GNUTranslations.__init__(self, *args, **kw)
    self.setOutputCharset('utf-8')
    self.__language = '??'

  def merge(self, other):
    self._catalog.update(other._catalog)

  def setLanguage(self, language):
    self.__language = language
    self.__toLanguage = toLanguage(language)

  def language(self):
    return self.__language

  def toLanguage(self):
    return self.__toLanguage

  def __repr__(self):
    return "<TheoryTranslation lang:%s>" % self.__language

def translation(language):
  """
  Returns a translation object.

  This translation object will be constructed out of multiple GNUTranslations
  objects by merging their catalogs. It will construct a object for the
  requested language and add a fallback to the default language, if it's
  different from the requested language.
  """
  global _translations

  t = _translations.get(language, None)
  if t is not None:
    return t

  from theory.conf import settings

  globalpath = os.path.join(os.path.dirname(upath(sys.modules[settings.__module__].__file__)), 'locale')

  def _fetch(lang, fallback=None):

    global _translations

    res = _translations.get(lang, None)
    if res is not None:
      return res

    loc = toLocale(lang)

    def _translation(path):
      try:
        t = gettextModule.translation('theory', path, [loc], TheoryTranslation)
        t.setLanguage(lang)
        return t
      except IOError:
        return None

    res = _translation(globalpath)

    # We want to ensure that, for example,  "en-gb" and "en-us" don't share
    # the same translation object (thus, merging en-us with a local update
    # doesn't affect en-gb), even though they will both use the core "en"
    # translation. So we have to subvert Python's internal gettext caching.
    baseLang = lambda x: x.split('-', 1)[0]
    if baseLang(lang) in [baseLang(trans) for trans in list(_translations)]:
      res._info = res._info.copy()
      res._catalog = res._catalog.copy()

    def _merge(path):
      t = _translation(path)
      if t is not None:
        if res is None:
          return t
        else:
          res.merge(t)
      return res

    for appname in reversed(settings.INSTALLED_APPS):
      app = importModule(appname)
      apppath = os.path.join(os.path.dirname(upath(app.__file__)), 'locale')

      if os.path.isdir(apppath):
        res = _merge(apppath)

    for localepath in reversed(settings.LOCALE_PATHS):
      if os.path.isdir(localepath):
        res = _merge(localepath)

    if res is None:
      if fallback is not None:
        res = fallback
      else:
        return gettextModule.NullTranslations()
    _translations[lang] = res
    return res

  defaultTranslation = _fetch(settings.LANGUAGE_CODE)
  currentTranslation = _fetch(language, fallback=defaultTranslation)

  return currentTranslation

def activate(language):
  """
  Fetches the translation object for a given tuple of application name and
  language and installs it as the current translation object for the current
  thread.
  """
  _active.value = translation(language)

def deactivate():
  """
  Deinstalls the currently active translation object so that further _ calls
  will resolve against the default translation object, again.
  """
  if hasattr(_active, "value"):
    del _active.value

def deactivateAll():
  """
  Makes the active translation object a NullTranslations() instance. This is
  useful when we want delayed translations to appear as the original string
  for some reason.
  """
  _active.value = gettextModule.NullTranslations()

def getLanguage():
  """Returns the currently selected language."""
  t = getattr(_active, "value", None)
  if t is not None:
    try:
      return t.toLanguage()
    except AttributeError:
      pass
  # If we don't have a real translation object, assume it's the default language.
  from theory.conf import settings
  return settings.LANGUAGE_CODE

def getLanguageBidi():
  """
  Returns selected language's BiDi layout.

  * False = left-to-right layout
  * True = right-to-left layout
  """
  from theory.conf import settings

  baseLang = getLanguage().split('-')[0]
  return baseLang in settings.LANGUAGES_BIDI

def catalog():
  """
  Returns the current active catalog for further processing.
  This can be used if you need to modify the catalog or want to access the
  whole message catalog instead of just translating one string.
  """
  global _default

  t = getattr(_active, "value", None)
  if t is not None:
    return t
  if _default is None:
    from theory.conf import settings
    _default = translation(settings.LANGUAGE_CODE)
  return _default

def doTranslate(message, translationFunction):
  """
  Translates 'message' using the given 'translationFunction' name -- which
  will be either gettext or ugettext. It uses the current thread to find the
  translation object to use. If no current translation is activated, the
  message will be run through the default translation object.
  """
  global _default

  # str() is allowing a bytestring message to remain bytestring on Python 2
  eolMessage = message.replace(str('\r\n'), str('\n')).replace(str('\r'), str('\n'))
  t = getattr(_active, "value", None)
  if t is not None:
    result = getattr(t, translationFunction)(eolMessage)
  else:
    if _default is None:
      from theory.conf import settings
      _default = translation(settings.LANGUAGE_CODE)
    result = getattr(_default, translationFunction)(eolMessage)
  if isinstance(message, SafeData):
    return markSafe(result)
  return result

def gettext(message):
  """
  Returns a string of the translation of the message.

  Returns a string on Python 3 and an UTF-8-encoded bytestring on Python 2.
  """
  return doTranslate(message, 'gettext')

if six.PY3:
  ugettext = gettext
else:
  def ugettext(message):
    return doTranslate(message, 'ugettext')

def pgettext(context, message):
  msgWithCtxt = "%s%s%s" % (context, CONTEXT_SEPARATOR, message)
  result = ugettext(msgWithCtxt)
  if CONTEXT_SEPARATOR in result:
    # Translation not found
    result = message
  return result

def gettextNoop(message):
  """
  Marks strings for translation but doesn't translate them now. This can be
  used to store strings in global variables that should stay in the base
  language (because they might be used externally) and will be translated
  later.
  """
  return message

def doNtranslate(singular, plural, number, translationFunction):
  global _default

  t = getattr(_active, "value", None)
  if t is not None:
    return getattr(t, translationFunction)(singular, plural, number)
  if _default is None:
    from theory.conf import settings
    _default = translation(settings.LANGUAGE_CODE)
  return getattr(_default, translationFunction)(singular, plural, number)

def ngettext(singular, plural, number):
  """
  Returns a string of the translation of either the singular or plural,
  based on the number.

  Returns a string on Python 3 and an UTF-8-encoded bytestring on Python 2.
  """
  return doNtranslate(singular, plural, number, 'ngettext')

if six.PY3:
  ungettext = ngettext
else:
  def ungettext(singular, plural, number):
    """
    Returns a unicode strings of the translation of either the singular or
    plural, based on the number.
    """
    return doNtranslate(singular, plural, number, 'ungettext')

def npgettext(context, singular, plural, number):
  msgsWithCtxt = ("%s%s%s" % (context, CONTEXT_SEPARATOR, singular),
           "%s%s%s" % (context, CONTEXT_SEPARATOR, plural),
           number)
  result = ungettext(*msgsWithCtxt)
  if CONTEXT_SEPARATOR in result:
    # Translation not found
    result = ungettext(singular, plural, number)
  return result

def allLocalePaths():
  """
  Returns a list of paths to user-provides languages files.
  """
  from theory.conf import settings
  globalpath = os.path.join(
    os.path.dirname(upath(sys.modules[settings.__module__].__file__)), 'locale')
  return [globalpath] + list(settings.LOCALE_PATHS)

def checkForLanguage(langCode):
  """
  Checks whether there is a global language file for the given language
  code. This is used to decide whether a user-provided language is
  available. This is only used for language codes from either the cookies
  or session and during format localization.
  """
  for path in allLocalePaths():
    if gettextModule.find('theory', path, [toLocale(langCode)]) is not None:
      return True
  return False
checkForLanguage = memoize(checkForLanguage, _checkedLanguages, 1)

def getSupportedLanguageVariant(langCode, supported=None, strict=False):
  """
  Returns the language-code that's listed in supported languages, possibly
  selecting a more generic variant. Raises LookupError if nothing found.

  If `strict` is False (the default), the function will look for an alternative
  country-specific variant when the currently checked is not found.
  """
  if supported is None:
    from theory.conf import settings
    supported = SortedDict(settings.LANGUAGES)
  if langCode:
    # if fr-CA is not supported, try fr-ca; if that fails, fallback to fr.
    genericLangCode = langCode.split('-')[0]
    variants = (langCode, langCode.lower(), genericLangCode,
          genericLangCode.lower())
    for code in variants:
      if code in supported and checkForLanguage(code):
        return code
    if not strict:
      # if fr-fr is not supported, try fr-ca.
      for supportedCode in supported:
        if supportedCode.startswith((genericLangCode + '-',
                       genericLangCode.lower() + '-')):
          return supportedCode
  raise LookupError(langCode)

def getLanguageFromPath(path, supported=None, strict=False):
  """
  Returns the language-code if there is a valid language-code
  found in the `path`.

  If `strict` is False (the default), the function will look for an alternative
  country-specific variant when the currently checked is not found.
  """
  if supported is None:
    from theory.conf import settings
    supported = SortedDict(settings.LANGUAGES)
  regexMatch = languageCodePrefixRe.match(path)
  if not regexMatch:
    return None
  langCode = regexMatch.group(1)
  try:
    return getSupportedLanguageVariant(langCode, supported, strict=strict)
  except LookupError:
    return None

def getLanguageFromRequest(request, checkPath=False):
  """
  Analyzes the request to find what language the user wants the system to
  show. Only languages listed in settings.LANGUAGES are taken into account.
  If the user requests a sublanguage where we have a main language, we send
  out the main language.

  If checkPath is True, the URL path prefix will be checked for a language
  code, otherwise this is skipped for backwards compatibility.
  """
  global _accepted
  from theory.conf import settings
  supported = SortedDict(settings.LANGUAGES)

  if checkPath:
    langCode = getLanguageFromPath(request.pathInfo, supported)
    if langCode is not None:
      return langCode

  if hasattr(request, 'session'):
    langCode = request.session.get('theoryLanguage', None)
    if langCode in supported and langCode is not None and checkForLanguage(langCode):
      return langCode

  langCode = request.COOKIES.get(settings.LANGUAGE_COOKIE_NAME)

  try:
    return getSupportedLanguageVariant(langCode, supported)
  except LookupError:
    pass

  accept = request.META.get('HTTP_ACCEPT_LANGUAGE', '')
  for acceptLang, unused in parseAcceptLangHeader(accept):
    if acceptLang == '*':
      break

    # 'normalized' is the root name of the locale in POSIX format (which is
    # the format used for the directories holding the MO files).
    normalized = locale.localeAlias.get(toLocale(acceptLang, True))
    if not normalized:
      continue
    # Remove the default encoding from localeAlias.
    normalized = normalized.split('.')[0]

    if normalized in _accepted:
      # We've seen this locale before and have an MO file for it, so no
      # need to check again.
      return _accepted[normalized]

    try:
      acceptLang = getSupportedLanguageVariant(acceptLang, supported)
    except LookupError:
      continue
    else:
      _accepted[normalized] = acceptLang
      return acceptLang

  try:
    return getSupportedLanguageVariant(settings.LANGUAGE_CODE, supported)
  except LookupError:
    return settings.LANGUAGE_CODE

dotRe = re.compile(r'\S')
def blankout(src, char):
  """
  Changes every non-whitespace character to the given char.
  Used in the templatize function.
  """
  return dotRe.sub(char, src)

contextRe = re.compile(r"""^\s+.*context\s+((?:"[^"]*?")|(?:'[^']*?'))\s*""")
inlineRe = re.compile(r"""^\s*trans\s+((?:"[^"]*?")|(?:'[^']*?'))(\s+.*context\s+((?:"[^"]*?")|(?:'[^']*?')))?\s*""")
blockRe = re.compile(r"""^\s*blocktrans(\s+.*context\s+((?:"[^"]*?")|(?:'[^']*?')))?(?:\s+|$)""")
endblockRe = re.compile(r"""^\s*endblocktrans$""")
pluralRe = re.compile(r"""^\s*plural$""")
constantRe = re.compile(r"""_\(((?:".*?")|(?:'.*?'))\)""")
onePercentRe = re.compile(r"""(?<!%)%(?!%)""")


def templatize(src, origin=None):
  """
  Turns a Theory template into something that is understood by xgettext. It
  does so by translating the Theory translation tags into standard gettext
  function invocations.
  """
  from theory.conf import settings
  from theory.template import (Lexer, TOKEN_TEXT, TOKEN_VAR, TOKEN_BLOCK,
      TOKEN_COMMENT, TRANSLATOR_COMMENT_MARK)
  src = forceText(src, settings.FILE_CHARSET)
  out = StringIO()
  messageContext = None
  intrans = False
  inplural = False
  singular = []
  plural = []
  incomment = False
  comment = []
  linenoCommentMap = {}
  commentLinenoCache = None

  for t in Lexer(src, origin).tokenize():
    if incomment:
      if t.tokenType == TOKEN_BLOCK and t.contents == 'endcomment':
        content = ''.join(comment)
        translatorsCommentStart = None
        for lineno, line in enumerate(content.splitlines(True)):
          if line.lstrip().startswith(TRANSLATOR_COMMENT_MARK):
            translatorsCommentStart = lineno
        for lineno, line in enumerate(content.splitlines(True)):
          if translatorsCommentStart is not None and lineno >= translatorsCommentStart:
            out.write(' # %s' % line)
          else:
            out.write(' #\n')
        incomment = False
        comment = []
      else:
        comment.append(t.contents)
    elif intrans:
      if t.tokenType == TOKEN_BLOCK:
        endbmatch = endblockRe.match(t.contents)
        pluralmatch = pluralRe.match(t.contents)
        if endbmatch:
          if inplural:
            if messageContext:
              out.write(' npgettext(%r, %r, %r,count) ' % (messageContext, ''.join(singular), ''.join(plural)))
            else:
              out.write(' ngettext(%r, %r, count) ' % (''.join(singular), ''.join(plural)))
            for part in singular:
              out.write(blankout(part, 'S'))
            for part in plural:
              out.write(blankout(part, 'P'))
          else:
            if messageContext:
              out.write(' pgettext(%r, %r) ' % (messageContext, ''.join(singular)))
            else:
              out.write(' gettext(%r) ' % ''.join(singular))
            for part in singular:
              out.write(blankout(part, 'S'))
          messageContext = None
          intrans = False
          inplural = False
          singular = []
          plural = []
        elif pluralmatch:
          inplural = True
        else:
          filemsg = ''
          if origin:
            filemsg = 'file %s, ' % origin
          raise SyntaxError("Translation blocks must not include other block tags: %s (%sline %d)" % (t.contents, filemsg, t.lineno))
      elif t.tokenType == TOKEN_VAR:
        if inplural:
          plural.append('%%(%s)s' % t.contents)
        else:
          singular.append('%%(%s)s' % t.contents)
      elif t.tokenType == TOKEN_TEXT:
        contents = onePercentRe.sub('%%', t.contents)
        if inplural:
          plural.append(contents)
        else:
          singular.append(contents)

    else:
      # Handle comment tokens (`{# ... #}`) plus other constructs on
      # the same line:
      if commentLinenoCache is not None:
        curLineno = t.lineno + t.contents.count('\n')
        if commentLinenoCache == curLineno:
          if t.tokenType != TOKEN_COMMENT:
            for c in linenoCommentMap[commentLinenoCache]:
              filemsg = ''
              if origin:
                filemsg = 'file %s, ' % origin
              warnMsg = ("The translator-targeted comment '%s' "
                "(%sline %d) was ignored, because it wasn't the last item "
                "on the line.") % (c, filemsg, commentLinenoCache)
              warnings.warn(warnMsg, TranslatorCommentWarning)
            linenoCommentMap[commentLinenoCache] = []
        else:
          out.write('# %s' % ' | '.join(linenoCommentMap[commentLinenoCache]))
        commentLinenoCache = None

      if t.tokenType == TOKEN_BLOCK:
        imatch = inlineRe.match(t.contents)
        bmatch = blockRe.match(t.contents)
        cmatches = constantRe.findall(t.contents)
        if imatch:
          g = imatch.group(1)
          if g[0] == '"':
            g = g.strip('"')
          elif g[0] == "'":
            g = g.strip("'")
          g = onePercentRe.sub('%%', g)
          if imatch.group(2):
            # A context is provided
            contextMatch = contextRe.match(imatch.group(2))
            messageContext = contextMatch.group(1)
            if messageContext[0] == '"':
              messageContext = messageContext.strip('"')
            elif messageContext[0] == "'":
              messageContext = messageContext.strip("'")
            out.write(' pgettext(%r, %r) ' % (messageContext, g))
            messageContext = None
          else:
            out.write(' gettext(%r) ' % g)
        elif bmatch:
          for fmatch in constantRe.findall(t.contents):
            out.write(' _(%s) ' % fmatch)
          if bmatch.group(1):
            # A context is provided
            contextMatch = contextRe.match(bmatch.group(1))
            messageContext = contextMatch.group(1)
            if messageContext[0] == '"':
              messageContext = messageContext.strip('"')
            elif messageContext[0] == "'":
              messageContext = messageContext.strip("'")
          intrans = True
          inplural = False
          singular = []
          plural = []
        elif cmatches:
          for cmatch in cmatches:
            out.write(' _(%s) ' % cmatch)
        elif t.contents == 'comment':
          incomment = True
        else:
          out.write(blankout(t.contents, 'B'))
      elif t.tokenType == TOKEN_VAR:
        parts = t.contents.split('|')
        cmatch = constantRe.match(parts[0])
        if cmatch:
          out.write(' _(%s) ' % cmatch.group(1))
        for p in parts[1:]:
          if p.find(':_(') >= 0:
            out.write(' %s ' % p.split(':',1)[1])
          else:
            out.write(blankout(p, 'F'))
      elif t.tokenType == TOKEN_COMMENT:
        if t.contents.lstrip().startswith(TRANSLATOR_COMMENT_MARK):
          linenoCommentMap.setdefault(t.lineno,
                         []).append(t.contents)
          commentLinenoCache = t.lineno
      else:
        out.write(blankout(t.contents, 'X'))
  return forceStr(out.getvalue())

def parseAcceptLangHeader(langString):
  """
  Parses the langString, which is the body of an HTTP Accept-Language
  header, and returns a list of (lang, q-value), ordered by 'q' values.

  Any format errors in langString results in an empty list being returned.
  """
  result = []
  pieces = acceptLanguageRe.split(langString)
  if pieces[-1]:
    return []
  for i in range(0, len(pieces) - 1, 3):
    first, lang, priority = pieces[i : i + 3]
    if first:
      return []
    if priority:
      priority = float(priority)
    if not priority:        # if priority is 0.0 at this point make it 1.0
       priority = 1.0
    result.append((lang, priority))
  result.sort(key=lambda k: k[1], reverse=True)
  return result
