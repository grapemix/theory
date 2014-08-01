VERSION = (0, 0, 1, 'alpha', 0)


def getVersion(*args, **kwargs):
  # Don't litter theory/__init__.py with all the getVersion stuff.
  # Only import if it's actually called.
  from theory.utils.version import getVersion
  return getVersion(*args, **kwargs)


def setup():
  """
  Configure the settings (this happens as a side effect of accessing the
  first setting), configure logging and populate the app registry.
  """
  from theory.apps import apps
  from theory.conf import settings
  from theory.utils.log import configureLogging

  configureLogging(settings.LOGGING_CONFIG, settings.LOGGING)
  apps.populate(settings.INSTALLED_APPS)
