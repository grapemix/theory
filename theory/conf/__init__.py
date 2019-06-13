# -*- coding: utf-8 -*-
#!/usr/bin/env python

##
# Settings and configuration for Theory.
#
# Values will be read from the module specified by the THEORY_SETTINGS_MODULE environment
# variable, and then from theory.conf.global_settings; see the global settings file for
# a list of all possible variables.

import os
import re
import time     # Needed for Windows
import warnings

from theory.conf import global_settings
from theory.utils.functional import LazyObject
from theory.utils import importlib

ENVIRONMENT_VARIABLE = "THEORY_SETTINGS_MODULE"


###
# A lazy proxy for either global Theory settings or a custom settings object.
# The user can manually configure settings prior to using them. Otherwise,
# Theory uses the settings module pointed to by THEORY_SETTINGS_MODULE.
class LazySettings(LazyObject):
  ##
  # Load the settings module pointed to by the environment variable. This
  # is used the first time we need any settings at all, if the user has not
  # previously configured the settings manually.
  def _setup(self):
    try:
      settings_module = os.environ[ENVIRONMENT_VARIABLE]
      if not settings_module: # If it's set but is an empty string.
        raise KeyError
    except KeyError:
      # NOTE: This is arguably an EnvironmentError, but that causes
      # problems with Python's interactive help.
      raise ImportError("Settings cannot be imported, because environment variable %s is undefined." % ENVIRONMENT_VARIABLE)

    self._wrapped = Settings(settings_module)

  ##
  # Called to manually configure the settings. The 'default_settings'
  # parameter sets where to retrieve any unspecified values from (its
  # argument must support attribute access (__getattr__)).
  def configure(self, default_settings=global_settings, **options):
    if self._wrapped != None:
      raise RuntimeError('Settings already configured.')
    holder = UserSettingsHolder(default_settings)
    for name, value in options.items():
      setattr(holder, name, value)
    self._wrapped = holder

  ##
  # Returns True if the settings have already been configured.
  def configured(self):
    return bool(self._wrapped)
  configured = property(configured)


class Settings(object):
  def __init__(self, settings_module):
    # update this dict from global settings (but only for ALL_CAPS settings)
    for setting in dir(global_settings):
      if setting == setting.upper():
        setattr(self, setting, getattr(global_settings, setting))

    # store the settings module in case someone later cares
    self.SETTINGS_MODULE = settings_module

    try:
      mod = importlib.importModule(self.SETTINGS_MODULE)
    except ImportError as e:
      raise ImportError(
        "Could not import settings '%s' (Is it on sys.path?): %s" % (
          self.SETTINGS_MODULE,
          e
        )
      )

    # Settings that should be converted into tuples if they're mistakenly entered
    # as strings.
    tuple_settings = ("INSTALLED_APPS", "UI_DIRS")

    for setting in dir(mod):
      if setting == setting.upper():
        setting_value = getattr(mod, setting)
        if setting in tuple_settings and type(setting_value) == str:
          setting_value = (setting_value,) # In case the user forgot the comma.
        setattr(self, setting, setting_value)

    # Expand entries in INSTALLED_APPS like "theory.contrib.*" to a list
    # of all those apps.
    new_installed_apps = []
    for app in self.INSTALLED_APPS:
      if app.endswith('.*'):
        app_mod = importlib.importModule(app[:-2])
        appdir = os.path.dirname(app_mod.__file__)
        app_subdirs = os.listdir(appdir)
        app_subdirs.sort()
        name_pattern = re.compile(r'[a-zA-Z]\w*')
        for d in app_subdirs:
          if name_pattern.match(d) and os.path.isdir(os.path.join(appdir, d)):
            new_installed_apps.append('%s.%s' % (app[:-2], d))
      else:
        new_installed_apps.append(app)
    self.INSTALLED_APPS = new_installed_apps

    if hasattr(time, 'tzset') and self.TIME_ZONE:
      # When we can, attempt to validate the timezone. If we can't find
      # this file, no check happens and it's harmless.
      zoneinfo_root = '/usr/share/zoneinfo'
      if (os.path.exists(zoneinfo_root) and not
          os.path.exists(os.path.join(zoneinfo_root, *(self.TIME_ZONE.split('/'))))):
        raise ValueError("Incorrect timezone setting: %s" % self.TIME_ZONE)
      # Move the time zone info into os.environ. See ticket #2315 for why
      # we don't do this unconditionally (breaks Windows).
      os.environ['TZ'] = self.TIME_ZONE
      time.tzset()

    # Settings are configured, so we can set up the logger if required
    if self.LOGGING_CONFIG:
      # First find the logging configuration function ...
      logging_config_path, logging_config_func_name = self.LOGGING_CONFIG.rsplit('.', 1)
      logging_config_module = importlib.importModule(logging_config_path)
      logging_config_func = getattr(logging_config_module, logging_config_func_name)

      # ... then invoke it with the logging settings
      logging_config_func(self.LOGGING)

class UserSettingsHolder(object):
#class UserSettingsHolder(BaseSettings):
  """
  Holder for user configured settings.
  """
  # SETTINGS_MODULE doesn't make much sense in the manually configured
  # (standalone) case.
  SETTINGS_MODULE = None
  def __init__(self, default_settings):
    """
    Requests for configuration variables not in this class are satisfied
    from the module specified in default_settings (if possible).
    """
    self.default_settings = default_settings
  def __getattr__(self, name):
    return getattr(self.default_settings, name)
  def __dir__(self):
    return self.__dict__.keys() + dir(self.default_settings)
  # For Python < 2.6:
  __members__ = property(lambda self: self.__dir__())

settings = LazySettings()
