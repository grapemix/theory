# These are versions of the functions in theory.utils.translation.transReal
# that don't actually do anything. This is purely for performance, so that
# settings.USE_I18N = False can use this module rather than transReal.py.

from theory.conf import settings
from theory.utils.encoding import forceText
from theory.utils.safestring import markSafe, SafeData

def ngettext(singular, plural, number):
  if number == 1: return singular
  return plural
ngettextLazy = ngettext

def ungettext(singular, plural, number):
  return forceText(ngettext(singular, plural, number))

def pgettext(context, message):
  return ugettext(message)

def npgettext(context, singular, plural, number):
  return ungettext(singular, plural, number)

activate = lambda x: None
deactivate = deactivateAll = lambda: None
getLanguage = lambda: settings.LANGUAGE_CODE
getLanguageBidi = lambda: settings.LANGUAGE_CODE in settings.LANGUAGES_BIDI
checkForLanguage = lambda x: True

# date formats shouldn't be used using gettext anymore. This
# is kept for backward compatibility
TECHNICAL_ID_MAP = {
  "DATE_WITH_TIME_FULL": settings.DATETIME_FORMAT,
  "DATE_FORMAT": settings.DATE_FORMAT,
  "DATETIME_FORMAT": settings.DATETIME_FORMAT,
  "TIME_FORMAT": settings.TIME_FORMAT,
  "YEAR_MONTH_FORMAT": settings.YEAR_MONTH_FORMAT,
  "MONTH_DAY_FORMAT": settings.MONTH_DAY_FORMAT,
}

def gettext(message):
  result = TECHNICAL_ID_MAP.get(message, message)
  if isinstance(message, SafeData):
    return markSafe(result)
  return result

def ugettext(message):
  return forceText(gettext(message))

gettextNoop = gettextLazy = _ = gettext

def toLocale(language):
  p = language.find('-')
  if p >= 0:
    return language[:p].lower()+'_'+language[p+1:].upper()
  else:
    return language.lower()

def getLanguageFromRequest(request, checkPath=False):
  return settings.LANGUAGE_CODE

def getLanguageFromPath(request, supported=None):
  return None

