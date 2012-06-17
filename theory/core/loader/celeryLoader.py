# -*- coding: utf-8 -*-
#!/usr/bin/env python
##### System wide lib #####
from celery.loaders.base import BaseLoader

##### Theory lib #####
from theory.conf import settings
from theory.model import Command
from theory.utils import timezone
from theory.utils.importlib import import_module

##### Theory third-party lib #####

##### Local app #####

##### Theory app #####

##### Misc #####


class CeleryLoader(BaseLoader):
  """Modified from celery default loader and django-celery DjangoLoader"""
  def now(self):
    return timezone.now()

  def read_configuration(self):
    """Read configuration from theory config file and configure
    celery and Theory so it can be used by regular Python."""
    self.configured = True
    return settings.CELERY_SETTINGS

  def on_worker_init(self):
    """Called when the worker starts.

    Automatically discovers any ``tasks.py`` files in the applications
    listed in ``INSTALLED_APPS``.

    """

    if settings.DEBUG:
      import warnings
      warnings.warn("Using settings.DEBUG leads to a memory leak, never "
                    "use this setting in production environments!")
    self.import_default_modules()

  def import_default_modules(self):
    super(CeleryLoader, self).import_default_modules()
    self.autodiscover()

  def autodiscover(self):
    #cmdImportPath = [cmd.moduleImportPath for cmd in Command.objects.all()]
    #import sys
    #for path in cmdImportPath:
    #  import_module(path)

    # TODO: should be support individual commands define themselves as
    # celery task instead using the default task wrapper. In that case,
    # all those celery task command should be added in here
    import theory.command.baseCommand
    #import_module("theory.command.baseCommand")
    self.task_modules.update(["theory.command.baseCommand"])

  # TODO: fix mail
  #def mail_admins(self, subject, body, fail_silently=False, **kwargs):
  #  return mail_admins(subject, body, fail_silently=fail_silently)

