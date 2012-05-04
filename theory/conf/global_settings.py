# -*- coding: utf-8 -*-
#!/usr/bin/env python
# Default Theory settings. Override these with settings in the module
# pointed-to by the THEORY_SETTINGS_MODULE environment variable.

# This is defined here as a do-nothing function because we can't import
# theory.utils.translation -- that module depends on the settings.
gettext_noop = lambda s: s

####################
# CORE             #
####################

DEBUG = False
UI_DEBUG = False

# Whether the framework should propagate raw exceptions rather than catching
# them. This is useful under some testing siutations and should never be used
# on a live site.
DEBUG_PROPAGATE_EXCEPTIONS = False

# People who get code error notifications.
# In the format (('Full Name', 'email@example.com'), ('Full Name', 'anotheremail@example.com'))
ADMINS = ()

# Tuple of IP addresses, as strings, that:
#   * See debug comments, when DEBUG is true
#   * Receive x-headers
INTERNAL_IPS = ()

# Local time zone for this installation. All choices can be found here:
# http://en.wikipedia.org/wiki/List_of_tz_zones_by_name (although not all
# systems may support all possibilities).
TIME_ZONE = 'America/Chicago'

# If you set this to True, Django will use timezone-aware datetimes.
USE_TZ = False

# Language code for this installation. All choices can be found here:
# http://www.i18nguy.com/unicode/language-identifiers.html
LANGUAGE_CODE = 'en-us'

# Languages we provide translations for, out of the box. The language name
# should be the utf-8 encoded local name for the language.
LANGUAGES = (
  ('ar', gettext_noop('Arabic')),
  ('az', gettext_noop('Azerbaijani')),
  ('bg', gettext_noop('Bulgarian')),
  ('bn', gettext_noop('Bengali')),
  ('bs', gettext_noop('Bosnian')),
  ('ca', gettext_noop('Catalan')),
  ('cs', gettext_noop('Czech')),
  ('cy', gettext_noop('Welsh')),
  ('da', gettext_noop('Danish')),
  ('de', gettext_noop('German')),
  ('el', gettext_noop('Greek')),
  ('en', gettext_noop('English')),
  ('en-gb', gettext_noop('British English')),
  ('es', gettext_noop('Spanish')),
  ('es-ar', gettext_noop('Argentinian Spanish')),
  ('es-mx', gettext_noop('Mexican Spanish')),
  ('es-ni', gettext_noop('Nicaraguan Spanish')),
  ('et', gettext_noop('Estonian')),
  ('eu', gettext_noop('Basque')),
  ('fa', gettext_noop('Persian')),
  ('fi', gettext_noop('Finnish')),
  ('fr', gettext_noop('French')),
  ('fy-nl', gettext_noop('Frisian')),
  ('ga', gettext_noop('Irish')),
  ('gl', gettext_noop('Galician')),
  ('he', gettext_noop('Hebrew')),
  ('hi', gettext_noop('Hindi')),
  ('hr', gettext_noop('Croatian')),
  ('hu', gettext_noop('Hungarian')),
  ('id', gettext_noop('Indonesian')),
  ('is', gettext_noop('Icelandic')),
  ('it', gettext_noop('Italian')),
  ('ja', gettext_noop('Japanese')),
  ('ka', gettext_noop('Georgian')),
  ('km', gettext_noop('Khmer')),
  ('kn', gettext_noop('Kannada')),
  ('ko', gettext_noop('Korean')),
  ('lt', gettext_noop('Lithuanian')),
  ('lv', gettext_noop('Latvian')),
  ('mk', gettext_noop('Macedonian')),
  ('ml', gettext_noop('Malayalam')),
  ('mn', gettext_noop('Mongolian')),
  ('nl', gettext_noop('Dutch')),
  ('no', gettext_noop('Norwegian')),
  ('nb', gettext_noop('Norwegian Bokmal')),
  ('nn', gettext_noop('Norwegian Nynorsk')),
  ('pa', gettext_noop('Punjabi')),
  ('pl', gettext_noop('Polish')),
  ('pt', gettext_noop('Portuguese')),
  ('pt-br', gettext_noop('Brazilian Portuguese')),
  ('ro', gettext_noop('Romanian')),
  ('ru', gettext_noop('Russian')),
  ('sk', gettext_noop('Slovak')),
  ('sl', gettext_noop('Slovenian')),
  ('sq', gettext_noop('Albanian')),
  ('sr', gettext_noop('Serbian')),
  ('sr-latn', gettext_noop('Serbian Latin')),
  ('sv', gettext_noop('Swedish')),
  ('ta', gettext_noop('Tamil')),
  ('te', gettext_noop('Telugu')),
  ('th', gettext_noop('Thai')),
  ('tr', gettext_noop('Turkish')),
  ('uk', gettext_noop('Ukrainian')),
  ('ur', gettext_noop('Urdu')),
  ('vi', gettext_noop('Vietnamese')),
  ('zh-cn', gettext_noop('Simplified Chinese')),
  ('zh-tw', gettext_noop('Traditional Chinese')),
)

# Languages using BiDi (right-to-left) layout
LANGUAGES_BIDI = ("he", "ar", "fa")

# If you set this to False, Theory will make some optimizations so as not
# to load the internationalization machinery.
USE_I18N = True
LOCALE_PATHS = ()

# If you set this to True, Theory will format dates, numbers and calendars
# according to user current locale
USE_L10N = False

# Not-necessarily-technical managers of the site. They get broken link
# notifications and other various e-mails.
MANAGERS = ADMINS

DEFAULT_CHARSET = 'utf-8'

# Encoding of files read from disk (template and initial SQL files).
FILE_CHARSET = 'utf-8'

# Database connection info.
# Legacy format
DATABASE_ENGINE = ''           # 'mongoengone'
DATABASE_NAME = ''
DATABASE_USER = ''
DATABASE_PASSWORD = ''
DATABASE_HOST = ''             # Set to empty string for localhost.
DATABASE_PORT = ''             # Set to empty string for default.
DATABASE_OPTIONS = {}          # Set to empty dictionary for default.

# New format
DATABASES = {
}

# The default mood
DEFAULT_MOOD = "norm"

# Classes used to implement db routing behaviour
DATABASE_ROUTERS = []

# List of strings representing installed apps.
INSTALLED_APPS = ()

# List of locations of the template source files, in search order.
UI_DIRS = ()

# List of callables that know how to import templates from various sources.
# See the comments in theory/core/template/loader.py for interface
# documentation.
UI_LOADERS = (
)

# Output to use in template system for invalid (e.g. misspelled) variables.
UI_STRING_IF_INVALID = ''

# If this is a admin settings module, this should be a list of
# settings modules (in the format 'foo.bar.baz') for which this admin
# is an admin.
ADMIN_FOR = ()

# A secret key for this particular Theory installation. Used in secret-key
# hashing algorithms. Set this in your settings, or Theory will complain
# loudly.
SECRET_KEY = ''

# Default file storage mechanism that holds media.
DEFAULT_FILE_STORAGE = 'theory.core.files.storage.FileSystemStorage'

# Python module path where user will place custom format definition.
# The directory where this setting is pointing should contain subdirectories
# named as the locales, containing a formats.py file
# (i.e. "myproject.locale" for myproject/locale/en/formats.py etc. use)
FORMAT_MODULE_PATH = None

# Default formatting for date objects. See all available format strings here:
# http://docs.theoryproject.com/en/dev/ref/templates/builtins/#date
DATE_FORMAT = 'N j, Y'

# Default formatting for datetime objects. See all available format strings here:
# http://docs.theoryproject.com/en/dev/ref/templates/builtins/#date
DATETIME_FORMAT = 'N j, Y, P'

# Default formatting for time objects. See all available format strings here:
# http://docs.theoryproject.com/en/dev/ref/templates/builtins/#date
TIME_FORMAT = 'P'

# Default formatting for date objects when only the year and month are relevant.
# See all available format strings here:
# http://docs.theoryproject.com/en/dev/ref/templates/builtins/#date
YEAR_MONTH_FORMAT = 'F Y'

# Default formatting for date objects when only the month and day are relevant.
# See all available format strings here:
# http://docs.theoryproject.com/en/dev/ref/templates/builtins/#date
MONTH_DAY_FORMAT = 'F j'

# Default short formatting for date objects. See all available format strings here:
# http://docs.theoryproject.com/en/dev/ref/templates/builtins/#date
SHORT_DATE_FORMAT = 'm/d/Y'

# Default short formatting for datetime objects.
# See all available format strings here:
# http://docs.theoryproject.com/en/dev/ref/templates/builtins/#date
SHORT_DATETIME_FORMAT = 'm/d/Y P'

# Default formats to be used when parsing dates from input boxes, in order
# See all available format string here:
# http://docs.python.org/library/datetime.html#strftime-behavior
# * Note that these format strings are different from the ones to display dates
DATE_INPUT_FORMATS = (
  '%Y-%m-%d', '%m/%d/%Y', '%m/%d/%y', # '2006-10-25', '10/25/2006', '10/25/06'
  '%b %d %Y', '%b %d, %Y',            # 'Oct 25 2006', 'Oct 25, 2006'
  '%d %b %Y', '%d %b, %Y',            # '25 Oct 2006', '25 Oct, 2006'
  '%B %d %Y', '%B %d, %Y',            # 'October 25 2006', 'October 25, 2006'
  '%d %B %Y', '%d %B, %Y',            # '25 October 2006', '25 October, 2006'
)

# Default formats to be used when parsing times from input boxes, in order
# See all available format string here:
# http://docs.python.org/library/datetime.html#strftime-behavior
# * Note that these format strings are different from the ones to display dates
TIME_INPUT_FORMATS = (
  '%H:%M:%S',     # '14:30:59'
  '%H:%M',        # '14:30'
)

# Default formats to be used when parsing dates and times from input boxes,
# in order
# See all available format string here:
# http://docs.python.org/library/datetime.html#strftime-behavior
# * Note that these format strings are different from the ones to display dates
DATETIME_INPUT_FORMATS = (
  '%Y-%m-%d %H:%M:%S',     # '2006-10-25 14:30:59'
  '%Y-%m-%d %H:%M',        # '2006-10-25 14:30'
  '%Y-%m-%d',              # '2006-10-25'
  '%m/%d/%Y %H:%M:%S',     # '10/25/2006 14:30:59'
  '%m/%d/%Y %H:%M',        # '10/25/2006 14:30'
  '%m/%d/%Y',              # '10/25/2006'
  '%m/%d/%y %H:%M:%S',     # '10/25/06 14:30:59'
  '%m/%d/%y %H:%M',        # '10/25/06 14:30'
  '%m/%d/%y',              # '10/25/06'
)

# First day of week, to be used on calendars
# 0 means Sunday, 1 means Monday...
FIRST_DAY_OF_WEEK = 0

# Decimal separator symbol
DECIMAL_SEPARATOR = '.'

# Boolean that sets whether to add thousand separator when formatting numbers
USE_THOUSAND_SEPARATOR = False

# Number of digits that will be together, when spliting them by
# THOUSAND_SEPARATOR. 0 means no grouping, 3 means splitting by thousands...
NUMBER_GROUPING = 0

# Thousand separator symbol
THOUSAND_SEPARATOR = ','

# The User-Agent string to use when checking for URL validity through the
# isExistingURL validator.
from theory import get_version
URL_VALIDATOR_USER_AGENT = "Theory/%s (https://www.theoryproject.com)" % get_version()

# The tablespaces to use for each model when not specified otherwise.
DEFAULT_TABLESPACE = ''
DEFAULT_INDEX_TABLESPACE = ''

##############
# MIDDLEWARE #
##############

# List of middleware classes to use.  Order is important; in the request phase,
# this middleware classes will be applied in the order given, and in the
# response phase the middleware will be applied in reverse order.
MIDDLEWARE_CLASSES = (
)

###########
# LOGGING #
###########

# The callable to use to configure logging
LOGGING_CONFIG = 'theory.utils.log.dictConfig'

# The default logging configuration. This sends an email to
# the site admins on every HTTP 500 error. All other log
# records are sent to the bit bucket.
LOGGING = {
  'version': 1,
  'disable_existing_loggers': False,
  'handlers': {
    'mail_admins': {
      'level': 'ERROR',
      'class': 'theory.utils.log.AdminEmailHandler'
    }
  },
  'loggers': {
    'theory.request': {
      'handlers': ['mail_admins'],
      'level': 'ERROR',
      'propagate': True,
    },
  }
}

###########
# TESTING #
###########

# The name of the class to use to run the test suite
TEST_RUNNER = 'theory.test.simple.TheoryTestSuiteRunner'

# The name of the database to use for testing purposes.
# If None, a name of 'test_' + DATABASE_NAME will be assumed
TEST_DATABASE_NAME = None

# Strings used to set the character set and collation order for the test
# database. These values are passed literally to the server, so they are
# backend-dependent. If None, no special settings are sent (system defaults are
# used).
TEST_DATABASE_CHARSET = None
TEST_DATABASE_COLLATION = None

############
# FIXTURES #
############

# The list of directories to search for fixtures
FIXTURE_DIRS = ()

MOOD = {}
