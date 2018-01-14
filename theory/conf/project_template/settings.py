# -*- coding: utf-8 -*-
#!/usr/bin/env python
from os.path import abspath, dirname, join
import sys

DEPLOY_ROOT = dirname(dirname(dirname(dirname(abspath(__file__)))))
PROJECT_ROOT = join(DEPLOY_ROOT, 'project')
PROJECT_PATH = dirname(dirname(__file__))
MOODS_ROOT = join(DEPLOY_ROOT, 'mood')
APPS_ROOT = join(DEPLOY_ROOT, 'app')

sys.path.insert(0, DEPLOY_ROOT)
sys.path.insert(0, MOODS_ROOT)
sys.path.insert(0, APPS_ROOT)

DEBUG = True
UI_DEBUG = DEBUG

ADMINS = (
  # ('Your Name', 'your_email@domain.com'),
)

MANAGERS = ADMINS

DATABASES = {
  'default': {
    'ENGINE': 'theory.db.backends.postgresqlPsycopg2',
    'NAME': '',
    'USER': '',
    'PASSWORD': '',
    'HOST': '',
    'PORT': '',
  }
}


# Local time zone for this installation. Choices can be found here:
# http://en.wikipedia.org/wiki/List_of_tz_zones_by_name
# although not all choices may be available on all operating systems.
# On Unix systems, a value of None will cause Django to use the same
# timezone as the operating system.
# If running in a Windows environment this must be set to the same as your
# system time zone.
TIME_ZONE = 'America/Los_Angeles'

# Language code for this installation. All choices can be found here:
# http://www.i18nguy.com/unicode/language-identifiers.html
LANGUAGE_CODE = 'en-us'

# If you set this to False, Django will make some optimizations so as not
# to load the internationalization machinery.
USE_I18N = True

# If you set this to False, Django will not format dates, numbers and
# calendars according to the current locale
USE_L10N = True

MIDDLEWARE_CLASSES = (
)

INSTALLED_MOODS = (
)

INSTALLED_APPS = (
)

# A sample logging configuration. The only tangible logging
# performed by this configuration is to send an email to
# the site admins on every HTTP 500 error.
# See http://docs.theoryproject.com/en/dev/topics/logging for
# more details on how to customize your logging configuration.
LOGGING = {
  'version': 1,
  'disable_existing_loggers': False,
  'handlers': {
    'default': {
      'level': 'ERROR',
      'class': 'logging.handlers.RotatingFileHandler',
      'filename': join(PROJECT_PATH, 'logs', 'default.log'),
    }
  },
  'loggers': {
    '': {
      'handlers': ['default'],
      'level': 'ERROR',
      'propagate': True,
    },
  }
}
