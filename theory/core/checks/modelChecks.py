# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from itertools import chain
import types

from theory.apps import apps

from . import Error, Tags, register


@register(Tags.models)
def checkAllModels(appConfigs=None, **kwargs):
  errors = [model.check(**kwargs)
    for model in apps.getModels()
    if appConfigs is None or model._meta.appConfig in appConfigs]
  return list(chain(*errors))


@register(Tags.models, Tags.signals)
def checkModelSignals(appConfigs=None, **kwargs):
  """Ensure lazily referenced model signals senders are installed."""
  from theory.db import models
  errors = []

  for name in dir(models.signals):
    obj = getattr(models.signals, name)
    if isinstance(obj, models.signals.ModelSignal):
      for reference, receivers in obj.unresolvedReferences.items():
        for receiver, _, _ in receivers:
          # The receiver is either a function or an instance of class
          # defining a `__call__` method.
          if isinstance(receiver, types.FunctionType):
            description = "The '%s' function" % receiver.__name__
          else:
            description = "An instance of the '%s' class" % receiver.__class__.__name__
          errors.append(
            Error(
              "%s was connected to the '%s' signal "
              "with a lazy reference to the '%s' sender, "
              "which has not been installed." % (
                description, name, '.'.join(reference)
              ),
              obj=receiver.__module__,
              hint=None,
              id='signals.E001'
            )
          )
  return errors
