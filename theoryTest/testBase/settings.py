# -*- coding: utf-8 -*-
#!/usr/bin/env python

from os.path import abspath, dirname, join
import sys

APP_ROOT = dirname(abspath(__file__))

sys.path.insert(0, APP_ROOT)

DEBUG = True
TEMPLATE_DEBUG = DEBUG

ADMINS = (
    # ('Your Name', 'your_email@domain.com'),
)

MANAGERS = ADMINS

DEFAULT_MOOD = "norm"

DATABASES = {
    'default': {
        'ENGINE': 'theory.db.backends.postgresqlPsycopg2', # Add 'mongoengine',
        'NAME': 'theory',
        'USER': 'theory',                      # Not used with sqlite3.
        'PASSWORD': 'django',                  # Not used with sqlite3.
        'HOST': '127.0.0.1',                      # Set to empty string for localhost.
        'PORT': '',                      # Set to empty string for default.
    }
}

#DATABASES = {
#    'default': {
#        'ENGINE': 'theory.db.backends.mongoEngine', # Add 'mongoengine',
#        'NAME': 'theory',
#        'USER': 'theory',                      # Not used with sqlite3.
#        'PASSWORD': 'django',                  # Not used with sqlite3.
#        'HOST': '127.0.0.1',                      # Set to empty string for localhost.
#        'PORT': '27017',                      # Set to empty string for default.
#    }
#}

# Local time zone for this installation. Choices can be found here:
# http://en.wikipedia.org/wiki/List_of_tz_zones_by_name
# although not all choices may be available on all operating systems.
# On Unix systems, a value of None will cause Django to use the same
# timezone as the operating system.
# If running in a Windows environment this must be set to the same as your
# system time zone.
TIME_ZONE = 'America/Los_Angeles'

# If you set this to True, Django will use timezone-aware datetimes.
USE_TZ = False

# Language code for this installation. All choices can be found here:
# http://www.i18nguy.com/unicode/language-identifiers.html
LANGUAGE_CODE = 'en-us'

# If you set this to False, Django will make some optimizations so as not
# to load the internationalization machinery.
USE_I18N = True

# If you set this to False, Django will not format dates, numbers and
# calendars according to the current locale
USE_L10N = True

UI_CONTEXT_PROCESSORS = (
)

FIXTURE_DIRS = [join(APP_ROOT, "fixture"),]

# List of callables that know how to import templates from various sources.
UI_LOADERS = (
)

MIDDLEWARE_CLASSES = (
)

UI_DIRS = (
)

DIMENSION_HINTS = {
  "minWidth": 640,
  "minHeight":480,
  "maxWidth": 640,
  "maxHeight": 480,
}

INSTALLED_MOODS = (
  "norm",
)

INSTALLED_APPS = (
  "theory.apps",
  "testBase",
)

# A sample logging configuration. The only tangible logging
# performed by this configuration is to send an email to
# the site admins on every HTTP 500 error.
# See http://docs.theoryproject.com/en/dev/topics/logging for
# more details on how to customize your logging configuration.
LOGGING = {
    'version': 1,
    'disable_existing_loggers': True,
    #'disable_existing_loggers': False,
    'formatters': {
        'simple': {
            'format': '%(asctime)s %(levelname)s %(module)s [%(name)s] - %(message)s \n',
        },
        'verbose': {
            'format': '%(asctime)s %(levelname)s %(module)s % (process)d %(thread)d %(message)s'
        },
    },
    'handlers': {
        'default': {
            'level':'DEBUG',
            'class': 'logging.StreamHandler',
            'formatter':'simple',
        },
    },
    'loggers': {
        'theory': { 'handlers': ['default',] },
        '': {
            'handlers': ['default'],
        #    'level': 'DEBUG',
            'propagate': True
        },
        'error': {
            'handlers': ['default',],
        #    'level': 'DEBUG',
            'propagate': True
        },

    }
}

# ========================= Celery Settings =========================
CELERY_EAGER_PROPAGATES_EXCEPTIONS = True
BROKER_BACKEND = 'memory'
# for 3.x
CELERY_ALWAYS_EAGER = True
# for 4.x
CELERY_TASK_ALWAYS_EAGER = True

CELERY_SETTINGS = {
}
