# -*- coding: utf-8 -*-
#!/usr/bin/env python
import logging
import sys
import warnings

from theory.conf import settings
#from theory.core import mail
#from theory.core.mail import getConnection
from theory.utils.deprecation import RemovedInNextVersionWarning
from theory.utils.moduleLoading import importString
#from theory.views.debug import ExceptionReporter, getExceptionReporterFilter

# Imports kept for backwards-compatibility in Theory 1.7.
from logging import NullHandler  # NOQA
from logging.config import dictConfig  # NOQA

getLogger = logging.getLogger

# Default logging for Theory. This sends an email to the site admins on every
# HTTP 500 error. Depending on DEBUG, all other log records are either sent to
# the console (DEBUG=True) or discarded by mean of the NullHandler (DEBUG=False).
DEFAULT_LOGGING = {
  'version': 1,
  'disableExistingLoggers': False,
  'filters': {
    'requireDebugFalse': {
      '()': 'theory.utils.log.RequireDebugFalse',
    },
    'requireDebugTrue': {
      '()': 'theory.utils.log.RequireDebugTrue',
    },
  },
  'handlers': {
    'console': {
      'level': 'INFO',
      'filters': ['requireDebugTrue'],
      'class': 'logging.StreamHandler',
    },
    'null': {
      'class': 'logging.NullHandler',
    },
  },
  'loggers': {
    'theory': {
      'handlers': ['console'],
    },
    'theory.request': {
      'handlers': [],
      'level': 'ERROR',
      'propagate': False,
    },
    'theory.security': {
      'handlers': [],
      'level': 'ERROR',
      'propagate': False,
    },
    'py.warnings': {
      'handlers': ['console'],
    },
  }
}


def configureLogging(loggingConfig, loggingSettings):
  if not sys.warnoptions:
    # Route warnings through python logging
    logging.captureWarnings(True)
    # RemovedInNextVersionWarning is a subclass of DeprecationWarning which
    # is hidden by default, hence we force the "default" behavior
    warnings.simplefilter("default", RemovedInNextVersionWarning)

  if loggingConfig:
    # First find the logging configuration function ...
    loggingConfigFunc = importString(loggingConfig)

    loggingConfigFunc(DEFAULT_LOGGING)

    # ... then invoke it with the logging settings
    if loggingSettings:
      loggingConfigFunc(loggingSettings)


#class AdminEmailHandler(logging.Handler):
#  """An exception log handler that emails log entries to site admins.
#
#  If the request is passed as the first argument to the log record,
#  request data will be provided in the email report.
#  """
#
#  def __init__(self, includeHtml=False, emailBackend=None):
#    logging.Handler.__init__(self)
#    self.includeHtml = includeHtml
#    self.emailBackend = emailBackend
#
#  def emit(self, record):
#    try:
#      request = record.request
#      subject = '%s (%s IP): %s' % (
#        record.levelname,
#        ('internal' if request.META.get('REMOTE_ADDR') in settings.INTERNAL_IPS
#         else 'EXTERNAL'),
#        record.getMessage()
#      )
#      filter = getExceptionReporterFilter(request)
#      requestRepr = '\n{0}'.format(filter.getRequestRepr(request))
#    except Exception:
#      subject = '%s: %s' % (
#        record.levelname,
#        record.getMessage()
#      )
#      request = None
#      requestRepr = "unavailable"
#    subject = self.formatSubject(subject)
#
#    if record.excInfo:
#      excInfo = record.excInfo
#    else:
#      excInfo = (None, record.getMessage(), None)
#
#    message = "%s\n\nRequest repr(): %s" % (self.format(record), requestRepr)
#    reporter = ExceptionReporter(request, isEmail=True, *excInfo)
#    htmlMessage = reporter.getTracebackHtml() if self.includeHtml else None
#    mail.mailAdmins(subject, message, failSilently=True,
#             htmlMessage=htmlMessage,
#             connection=self.connection())
#
#  def connection(self):
#    return getConnection(backend=self.emailBackend, failSilently=True)
#
#  def formatSubject(self, subject):
#    """
#    Escape CR and LF characters, and limit length.
#    RFC 2822's hard limit is 998 characters per line. So, minus "Subject: "
#    the actual subject must be no longer than 989 characters.
#    """
#    formattedSubject = subject.replace('\n', '\\n').replace('\r', '\\r')
#    return formattedSubject[:989]


class CallbackFilter(logging.Filter):
  """
  A logging filter that checks the return value of a given callable (which
  takes the record-to-be-logged as its only parameter) to decide whether to
  log a record.

  """
  def __init__(self, callback):
    self.callback = callback

  def filter(self, record):
    if self.callback(record):
      return 1
    return 0


class RequireDebugFalse(logging.Filter):
  def filter(self, record):
    return not settings.DEBUG


class RequireDebugTrue(logging.Filter):
  def filter(self, record):
    return settings.DEBUG
