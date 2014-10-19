# -*- encoding: utf-8 -*-
from __future__ import unicode_literals

from theory.apps import apps

from .. import Warning, register, Tags


@register(Tags.compatibility)
def check0_1Compatibility(**kwargs):
  errors = []
  errors.extend(_checkTestRunner(**kwargs))
  errors.extend(_checkBooleanFieldDefaultValue(**kwargs))
  return errors


def _checkTestRunner(appConfigs=None, **kwargs):
  """
  Checks if the user has *not* overridden the ``TEST_RUNNER`` setting &
  warns them about the default behavior changes.

  If the user has overridden that setting, we presume they know what they're
  doing & avoid generating a message.
  """
  from theory.conf import settings

  # We need to establish if this is a project defined on the 1.5 project template,
  # because if the project was generated on the 1.6 template, it will have be been
  # developed with the new TEST_RUNNER behavior in mind.

  # There's no canonical way to do this; so we leverage off the fact that 1.6
  # also introduced a new project template, removing a bunch of settings from the
  # default that won't be in common usage.

  # We make this determination on a balance of probabilities. Each of these factors
  # contributes a weight; if enough of them trigger, we've got a likely 1.6 project.
  weight = 0

  # If TEST_RUNNER is explicitly set, it's all a moot point - if it's been explicitly set,
  # the user has opted into a specific set of behaviors, which won't change as the
  # default changes.
  if not settings.isOverridden('TEST_RUNNER'):
    # Strong markers:
    # SITE_ID = 1 is in 1.5 template, not defined in 1.6 template
    try:
      settings.SITE_ID
      weight += 2
    except AttributeError:
      pass

    # BASE_DIR is not defined in 1.5 template, set in 1.6 template
    try:
      settings.BASE_DIR
    except AttributeError:
      weight += 2

    # TEMPLATE_LOADERS defined in 1.5 template, not defined in 1.6 template
    if settings.isOverridden('TEMPLATE_LOADERS'):
      weight += 2

    # MANAGERS defined in 1.5 template, not defined in 1.6 template
    if settings.isOverridden('MANAGERS'):
      weight += 2

    # Weaker markers - These are more likely to have been added in common usage
    # ADMINS defined in 1.5 template, not defined in 1.6 template
    if settings.isOverridden('ADMINS'):
      weight += 1

    # Clickjacking enabled by default in 1.6
    if 'theory.middleware.clickjacking.XFrameOptionsMiddleware' not in set(settings.MIDDLEWARE_CLASSES):
      weight += 1

  if weight >= 6:
    return [
      Warning(
        "Some project unittests may not execute as expected.",
        hint=("Theory 1.6 introduced a new default test runner. It looks like "
           "this project was generated using Theory 1.5 or earlier. You should "
           "ensure your tests are all running & behaving as expected. See "
           "https://docs.theoryproject.com/en/dev/releases/1.6/#new-test-runner "
           "for more information."),
        obj=None,
        id='16.W001',
      )
    ]
  else:
    return []


def _checkBooleanFieldDefaultValue(appConfigs=None, **kwargs):
  """
  Checks if there are any BooleanFields without a default value, &
  warns the user that the default has changed from False to None.
  """
  from theory.db import models

  problemFields = [
    field
    for model in apps.getModels(**kwargs)
    if appConfigs is None or model._meta.appConfig in appConfigs
    for field in model._meta.localFields
    if isinstance(field, models.BooleanField) and not field.hasDefault()
  ]

  return [
    Warning(
      "BooleanField does not have a default value.",
      hint=("Theory 1.6 changed the default value of BooleanField from False to None. "
         "See https://docs.theoryproject.com/en/1.6/ref/models/fields/#booleanfield "
         "for more information."),
      obj=field,
      id='16.W002',
    )
    for field in problemFields
  ]
