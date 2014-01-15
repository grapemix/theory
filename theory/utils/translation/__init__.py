"""
Internationalization support.
"""
#from __future__ import unicodeLiterals

from theory.utils.encoding import forceText
from theory.utils.functional import lazy
from theory.utils import six


__all__ = [
  'activate', 'deactivate', 'override', 'deactivateAll',
  'getLanguage',  'getLanguageFromRequest',
  'getLanguageInfo', 'getLanguageBidi',
  'checkForLanguage', 'toLocale', 'templatize', 'stringConcat',
  'gettext', 'gettextLazy', 'gettextNoop',
  'ugettext', 'ugettextLazy', 'ugettextNoop',
  'ngettext', 'ngettextLazy',
  'ungettext', 'ungettextLazy',
  'pgettext', 'pgettextLazy',
  'npgettext', 'npgettextLazy',
]


class TranslatorCommentWarning(SyntaxWarning):
  pass


# Here be dragons, so a short explanation of the logic won't hurt:
# We are trying to solve two problems: (1) access settings, in particular
# settings.USE_I18N, as late as possible, so that modules can be imported
# without having to first configure Theory, and (2) if some other code creates
# a reference to one of these functions, don't break that reference when we
# replace the functions with their real counterparts (once we do access the
# settings).

class Trans(object):
  """
  The purpose of this class is to store the actual translation function upon
  receiving the first call to that function. After this is done, changes to
  USE_I18N will have no effect to which function is served upon request. If
  your tests rely on changing USE_I18N, you can delete all the functions
  from _trans.__dict__.

  Note that storing the function with setattr will have a noticeable
  performance effect, as access to the function goes the normal path,
  instead of using __getattr__.
  """

  def __getattr__(self, realName):
    from theory.conf import settings
    if settings.USE_I18N:
      from theory.utils.translation import transReal as trans
    else:
      from theory.utils.translation import transNull as trans
    setattr(self, realName, getattr(trans, realName))
    return getattr(trans, realName)

_trans = Trans()

# The Trans class is no more needed, so remove it from the namespace.
del Trans

def gettextNoop(message):
  return _trans.gettextNoop(message)

ugettextNoop = gettextNoop

def gettext(message):
  return _trans.gettext(message)

def ngettext(singular, plural, number):
  return _trans.ngettext(singular, plural, number)

def ugettext(message):
  return _trans.ugettext(message)

def ungettext(singular, plural, number):
  return _trans.ungettext(singular, plural, number)

def pgettext(context, message):
  return _trans.pgettext(context, message)

def npgettext(context, singular, plural, number):
  return _trans.npgettext(context, singular, plural, number)

gettextLazy = lazy(gettext, str)
ugettextLazy = lazy(ugettext, six.text_type)
pgettextLazy = lazy(pgettext, six.text_type)

def lazyNumber(func, resultclass, number=None, **kwargs):
  if isinstance(number, int):
    kwargs['number'] = number
    proxy = lazy(func, resultclass)(**kwargs)
  else:
    class NumberAwareString(resultclass):
      def __mod__(self, rhs):
        if isinstance(rhs, dict) and number:
          try:
            numberValue = rhs[number]
          except KeyError:
            raise KeyError('Your dictionary lacks key \'%s\'. '
              'Please provide it, because it is required to '
              'determine whether string is singular or plural.'
              % number)
        else:
          numberValue = rhs
        kwargs['number'] = numberValue
        translated = func(**kwargs)
        try:
          translated = translated % rhs
        except TypeError:
          # String doesn't contain a placeholder for the number
          pass
        return translated

    proxy = lazy(lambda **kwargs: NumberAwareString(), NumberAwareString)(**kwargs)
  return proxy

def ngettextLazy(singular, plural, number=None):
  return lazyNumber(ngettext, str, singular=singular, plural=plural, number=number)

def ungettextLazy(singular, plural, number=None):
  return lazyNumber(ungettext, six.text_type, singular=singular, plural=plural, number=number)

def npgettextLazy(context, singular, plural, number=None):
  return lazyNumber(npgettext, six.text_type, context=context, singular=singular, plural=plural, number=number)

def activate(language):
  return _trans.activate(language)

def deactivate():
  return _trans.deactivate()

class override(object):
  def __init__(self, language, deactivate=False):
    self.language = language
    self.deactivate = deactivate
    self.oldLanguage = getLanguage()

  def __enter__(self):
    if self.language is not None:
      activate(self.language)
    else:
      deactivateAll()

  def __exit__(self, excType, excValue, traceback):
    if self.deactivate:
      deactivate()
    else:
      activate(self.oldLanguage)

def getLanguage():
  return _trans.getLanguage()

def getLanguageBidi():
  return _trans.getLanguageBidi()

def checkForLanguage(langCode):
  return _trans.checkForLanguage(langCode)

def toLocale(language):
  return _trans.toLocale(language)

def getLanguageFromRequest(request, checkPath=False):
  return _trans.getLanguageFromRequest(request, checkPath)

def getLanguageFromPath(path, supported=None):
  return _trans.getLanguageFromPath(path, supported=supported)

def templatize(src, origin=None):
  return _trans.templatize(src, origin)

def deactivateAll():
  return _trans.deactivateAll()

def _stringConcat(*strings):
  """
  Lazy variant of string concatenation, needed for translations that are
  constructed from multiple parts.
  """
  return ''.join([forceText(s) for s in strings])
stringConcat = lazy(_stringConcat, six.text_type)

def getLanguageInfo(langCode):
  from theory.conf.locale import LANG_INFO
  try:
    return LANG_INFO[langCode]
  except KeyError:
    if '-' not in langCode:
      raise KeyError("Unknown language code %s." % langCode)
    genericLangCode = langCode.split('-')[0]
    try:
      return LANG_INFO[genericLangCode]
    except KeyError:
      raise KeyError("Unknown language code %s and %s." % (langCode, genericLangCode))
