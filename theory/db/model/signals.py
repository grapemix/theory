from theory.apps import apps
from theory.dispatch import Signal
from theory.utils import six


classPrepared = Signal(providingArgs=["class"])


class ModelSignal(Signal):
  """
  Signal subclass that allows the sender to be lazily specified as a string
  of the `appLabel.ModelName` form.
  """

  def __init__(self, *args, **kwargs):
    super(ModelSignal, self).__init__(*args, **kwargs)
    self.unresolvedReferences = {}
    classPrepared.connect(self._resolveReferences)

  def _resolveReferences(self, sender, **kwargs):
    opts = sender._meta
    reference = (opts.appLabel, opts.objectName)
    try:
      receivers = self.unresolvedReferences.pop(reference)
    except KeyError:
      pass
    else:
      for receiver, weak, dispatchUid in receivers:
        super(ModelSignal, self).connect(
          receiver, sender=sender, weak=weak, dispatchUid=dispatchUid
        )

  def connect(self, receiver, sender=None, weak=True, dispatchUid=None):
    if isinstance(sender, six.stringTypes):
      try:
        appLabel, modelName = sender.split('.')
      except ValueError:
        raise ValueError(
          "Specified sender must either be a modal or a "
          "modal name of the 'appLabel.ModelName' form."
        )
      try:
        sender = apps.getRegisteredModel(appLabel, modelName)
      except LookupError:
        ref = (appLabel, modelName)
        refs = self.unresolvedReferences.setdefault(ref, [])
        refs.append((receiver, weak, dispatchUid))
        return
    super(ModelSignal, self).connect(
      receiver, sender=sender, weak=weak, dispatchUid=dispatchUid
    )

preInit = ModelSignal(providingArgs=["instance", "args", "kwargs"], useCaching=True)
postInit = ModelSignal(providingArgs=["instance"], useCaching=True)

preSave = ModelSignal(providingArgs=["instance", "raw", "using", "updateFields"],
            useCaching=True)
postSave = ModelSignal(providingArgs=["instance", "raw", "created", "using", "updateFields"], useCaching=True)

preDelete = ModelSignal(providingArgs=["instance", "using"], useCaching=True)
postDelete = ModelSignal(providingArgs=["instance", "using"], useCaching=True)

m2mChanged = ModelSignal(providingArgs=["action", "instance", "reverse", "modal", "pkSet", "using"], useCaching=True)

preMigrate = Signal(providingArgs=["appConfig", "verbosity", "interactive", "using"])
postMigrate = Signal(providingArgs=["appConfig", "verbosity", "interactive", "using"])

preSyncdb = Signal(providingArgs=["app", "createModels", "verbosity", "interactive", "db"])
postSyncdb = Signal(providingArgs=["class", "app", "createdModels", "verbosity", "interactive", "db"])
