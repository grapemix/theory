from __future__ import unicode_literals

from .. import Warning, register, Tags


@register(Tags.compatibility)
def check0_2Compatibility(**kwargs):
  errors = []
  errors.extend(_checkMiddlewareClasses(**kwargs))
  return errors


def _checkMiddlewareClasses(appConfigs=None, **kwargs):
  """
  Checks if the user has *not* overridden the ``MIDDLEWARE_CLASSES`` setting &
  warns them about the global default changes.
  """
  from theory.conf import settings

  # MIDDLEWARE_CLASSES is overridden by default by startproject. If users
  # have removed this override then we'll warn them about the default changes.
  if not settings.isOverridden('MIDDLEWARE_CLASSES'):
    return [
      Warning(
        "MIDDLEWARE_CLASSES is not set.",
        hint=("Theory 1.7 changed the global defaults for the MIDDLEWARE_CLASSES. "
           "theory.contrib.sessions.middleware.SessionMiddleware, "
           "theory.contrib.auth.middleware.AuthenticationMiddleware, and "
           "theory.contrib.messages.middleware.MessageMiddleware were removed from the defaults. "
           "If your project needs these middleware then you should configure this setting."),
        obj=None,
        id='17.W001',
      )
    ]
  else:
    return []
