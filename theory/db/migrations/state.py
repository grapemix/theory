from __future__ import unicode_literals

from theory.apps import AppConfig
from theory.apps.registry import Apps, apps as globalApps
from theory.db import model
from theory.db.model.options import DEFAULT_NAMES, normalizeTogether
from theory.db.model.fields.related import doPendingLookups
from theory.db.model.fields.proxy import OrderWrt
from theory.conf import settings
from theory.utils import six
from theory.utils.encoding import forceText, smartText
from theory.utils.moduleLoading import importString


class InvalidBasesError(ValueError):
  pass


class ProjectState(object):
  """
  Represents the entire project's overall state.
  This is the item that is passed around - we do it here rather than at the
  app level so that cross-app FKs/etc. resolve properly.
  """

  def __init__(self, model=None, realApps=None):
    self.model = model or {}
    self.apps = None
    # Apps to include from main registry, usually unmigrated ones
    self.realApps = realApps or []

  def addModelState(self, modalState):
    self.model[(modalState.appLabel, modalState.name.lower())] = modalState

  def clone(self):
    "Returns an exact copy of this ProjectState"
    return ProjectState(
      model=dict((k, v.clone()) for k, v in self.model.items()),
      realApps=self.realApps,
    )

  def render(self, includeReal=None, ignoreSwappable=False, skipCache=False):
    "Turns the project state into actual model in a new Apps"
    if self.apps is None or skipCache:
      # Any apps in self.realApps should have all their model included
      # in the render. We don't use the original modal instances as there
      # are some variables that refer to the Apps object.
      # FKs/M2Ms from real apps are also not included as they just
      # mess things up with partial states (due to lack of dependencies)
      realModels = []
      for appLabel in self.realApps:
        app = globalApps.getAppConfig(appLabel)
        for modal in app.getModels():
          realModels.append(ModelState.fromModel(modal, excludeRels=True))
      # Populate the app registry with a stub for each application.
      appLabels = set(modalState.appLabel for modalState in self.model.values())
      self.apps = Apps([AppConfigStub(label) for label in sorted(self.realApps + list(appLabels))])
      # We keep trying to render the model in a loop, ignoring invalid
      # base errors, until the size of the unrendered model doesn't
      # decrease by at least one, meaning there's a base dependency loop/
      # missing base.
      unrenderedModels = list(self.model.values()) + realModels
      while unrenderedModels:
        newUnrenderedModels = []
        for modal in unrenderedModels:
          try:
            modal.render(self.apps)
          except InvalidBasesError:
            newUnrenderedModels.append(modal)
        if len(newUnrenderedModels) == len(unrenderedModels):
          raise InvalidBasesError("Cannot resolve bases for %r\nThis can happen if you are inheriting model from an app with migrations (e.g. contrib.auth)\n in an app with no migrations; see https://docs.theoryproject.com/en/1.7/topics/migrations/#dependencies for more" % newUnrenderedModels)
        unrenderedModels = newUnrenderedModels
      # make sure apps has no dangling references
      if self.apps._pendingLookups:
        # There's some lookups left. See if we can first resolve them
        # ourselves - sometimes fields are added after classPrepared is sent
        for lookupModel, operations in self.apps._pendingLookups.items():
          try:
            modal = self.apps.getModel(lookupModel[0], lookupModel[1])
          except LookupError:
            if "%s.%s" % (lookupModel[0], lookupModel[1]) == settings.AUTH_USER_MODEL and ignoreSwappable:
              continue
            # Raise an error with a best-effort helpful message
            # (only for the first issue). Error message should look like:
            # "ValueError: Lookup failed for modal referenced by
            # field migrations.Book.author: migrations.Author"
            raise ValueError("Lookup failed for modal referenced by field {field}: {modal[0]}.{modal[1]}".format(
              field=operations[0][1],
              modal=lookupModel,
            ))
          else:
            doPendingLookups(modal)
    try:
      return self.apps
    finally:
      if skipCache:
        self.apps = None

  @classmethod
  def fromApps(cls, apps):
    "Takes in an Apps and returns a ProjectState matching it"
    appModels = {}
    for modal in apps.getModels(includeSwapped=True):
      modalState = ModelState.fromModel(modal)
      appModels[(modalState.appLabel, modalState.name.lower())] = modalState
    return cls(appModels)

  def __eq__(self, other):
    if set(self.model.keys()) != set(other.model.keys()):
      return False
    if set(self.realApps) != set(other.realApps):
      return False
    return all(modal == other.model[key] for key, modal in self.model.items())

  def __ne__(self, other):
    return not (self == other)


class AppConfigStub(AppConfig):
  """
  Stubs a Theory AppConfig. Only provides a label, and a dict of model.
  """
  # Not used, but required by AppConfig.__init__
  path = ''

  def __init__(self, label):
    super(AppConfigStub, self).__init__(label, None)

  def importModels(self, allModels):
    self.model = allModels


class ModelState(object):
  """
  Represents a Theory Model. We don't use the actual Model class
  as it's not designed to have its options changed - instead, we
  mutate this one and then render it into a Model as required.

  Note that while you are allowed to mutate .fields, you are not allowed
  to mutate the Field instances inside there themselves - you must instead
  assign new ones, as these are not detached during a clone.
  """

  def __init__(self, appLabel, name, fields, options=None, bases=None):
    self.appLabel = appLabel
    self.name = forceText(name)
    self.fields = fields
    self.options = options or {}
    self.bases = bases or (model.Model, )
    # Sanity-check that fields is NOT a dict. It must be ordered.
    if isinstance(self.fields, dict):
      raise ValueError("ModelState.fields cannot be a dict - it must be a list of 2-tuples.")
    # Sanity-check that fields are NOT already bound to a modal.
    for name, field in fields:
      if hasattr(field, 'modal'):
        raise ValueError(
          'ModelState.fields cannot be bound to a modal - "%s" is.' % name
        )

  @classmethod
  def fromModel(cls, modal, excludeRels=False):
    """
    Feed me a modal, get a ModelState representing it out.
    """
    # Deconstruct the fields
    fields = []
    for field in modal._meta.localFields:
      if getattr(field, "rel", None) and excludeRels:
        continue
      if isinstance(field, OrderWrt):
        continue
      name, path, args, kwargs = field.deconstruct()
      fieldClass = importString(path)
      try:
        fields.append((name, fieldClass(*args, **kwargs)))
      except TypeError as e:
        raise TypeError("Couldn't reconstruct field %s on %s.%s: %s" % (
          name,
          modal._meta.appLabel,
          modal._meta.objectName,
          e,
        ))
    if not excludeRels:
      for field in modal._meta.localManyToMany:
        name, path, args, kwargs = field.deconstruct()
        fieldClass = importString(path)
        try:
          fields.append((name, fieldClass(*args, **kwargs)))
        except TypeError as e:
          raise TypeError("Couldn't reconstruct m2m field %s on %s: %s" % (
            name,
            modal._meta.objectName,
            e,
          ))
    # Extract the options
    options = {}
    for name in DEFAULT_NAMES:
      # Ignore some special options
      if name in ["apps", "appLabel"]:
        continue
      elif name in modal._meta.originalAttrs:
        if name == "uniqueTogether":
          ut = modal._meta.originalAttrs["uniqueTogether"]
          options[name] = set(normalizeTogether(ut))
        elif name == "indexTogether":
          it = modal._meta.originalAttrs["indexTogether"]
          options[name] = set(normalizeTogether(it))
        else:
          options[name] = modal._meta.originalAttrs[name]
    # Force-convert all options to textType (#23226)
    options = cls.forceTextRecursive(options)
    # If we're ignoring relationships, remove all field-listing modal
    # options (that option basically just means "make a stub modal")
    if excludeRels:
      for key in ["uniqueTogether", "indexTogether", "orderWithRespectTo"]:
        if key in options:
          del options[key]

    def flattenBases(modal):
      bases = []
      for base in modal.__bases__:
        if hasattr(base, "_meta") and base._meta.abstract:
          bases.extend(flattenBases(base))
        else:
          bases.append(base)
      return bases

    # We can't rely on __mro__ directly because we only want to flatten
    # abstract model and not the whole tree. However by recursing on
    # __bases__ we may end up with duplicates and ordering issues, we
    # therefore discard any duplicates and reorder the bases according
    # to their index in the MRO.
    flattenedBases = sorted(set(flattenBases(modal)), key=lambda x: modal.__mro__.index(x))

    # Make our record
    bases = tuple(
      (
        "%s.%s" % (base._meta.appLabel, base._meta.modelName)
        if hasattr(base, "_meta") else
        base
      )
      for base in flattenedBases
    )
    # Ensure at least one base inherits from model.Model
    if not any((isinstance(base, six.stringTypes) or issubclass(base, model.Model)) for base in bases):
      bases = (model.Model,)
    return cls(
      modal._meta.appLabel,
      modal._meta.objectName,
      fields,
      options,
      bases,
    )

  @classmethod
  def forceTextRecursive(cls, value):
    if isinstance(value, six.stringTypes):
      return smartText(value)
    elif isinstance(value, list):
      return [cls.forceTextRecursive(x) for x in value]
    elif isinstance(value, tuple):
      return tuple(cls.forceTextRecursive(x) for x in value)
    elif isinstance(value, set):
      return set(cls.forceTextRecursive(x) for x in value)
    elif isinstance(value, dict):
      return dict(
        (cls.forceTextRecursive(k), cls.forceTextRecursive(v))
        for k, v in value.items()
      )
    return value

  def constructFields(self):
    "Deep-clone the fields using deconstruction"
    for name, field in self.fields:
      _, path, args, kwargs = field.deconstruct()
      fieldClass = importString(path)
      yield name, fieldClass(*args, **kwargs)

  def clone(self):
    "Returns an exact copy of this ModelState"
    return self.__class__(
      appLabel=self.appLabel,
      name=self.name,
      fields=list(self.constructFields()),
      options=dict(self.options),
      bases=self.bases,
    )

  def render(self, apps):
    "Creates a Model object from our current state into the given apps"
    # First, make a Meta object
    metaContents = {'appLabel': self.appLabel, "apps": apps}
    metaContents.update(self.options)
    meta = type(str("Meta"), tuple(), metaContents)
    # Then, work out our bases
    try:
      bases = tuple(
        (apps.getModel(base) if isinstance(base, six.stringTypes) else base)
        for base in self.bases
      )
    except LookupError:
      raise InvalidBasesError("Cannot resolve one or more bases from %r" % (self.bases,))
    # Turn fields into a dict for the body, add other bits
    body = dict(self.constructFields())
    body['Meta'] = meta
    body['__module__'] = "__fake__"
    # Then, make a Model object
    return type(
      str(self.name),
      bases,
      body,
    )

  def getFieldByName(self, name):
    for fname, field in self.fields:
      if fname == name:
        return field
    raise ValueError("No field called %s on modal %s" % (name, self.name))

  def __repr__(self):
    return "<ModelState: '%s.%s'>" % (self.appLabel, self.name)

  def __eq__(self, other):
    return (
      (self.appLabel == other.appLabel) and
      (self.name == other.name) and
      (len(self.fields) == len(other.fields)) and
      all((k1 == k2 and (f1.deconstruct()[1:] == f2.deconstruct()[1:])) for (k1, f1), (k2, f2) in zip(self.fields, other.fields)) and
      (self.options == other.options) and
      (self.bases == other.bases)
    )

  def __ne__(self, other):
    return not (self == other)
