"""
Helper functions for creating Form classes from Theory model
and database field objects.
"""

import warnings

from theory.core.exceptions import ValidationError
from theory.gui.common.baseField import Field
from theory.utils import six
from theory.utils.deprecation import RemovedInTheory19Warning
from theory.utils.encoding import smartText, forceText
from theory.utils.importlib import importClass
from theory.utils.translation import ugettextLazy as _


# Fields #####################################################################

class InlineForeignKeyField(Field):
  """
  A basic integer field that deals with validating the given value to a
  given parent instance in an inline.
  """
  widget = "HiddenInput"
  defaultErrorMessages = {
    'invalidChoice': _('The inline foreign key did not match the parent instance primary key.'),
  }

  def __init__(self, parentInstance, *args, **kwargs):
    self.parentInstance = parentInstance
    self.pkField = kwargs.pop("pkField", False)
    self.toField = kwargs.pop("toField", None)
    if self.parentInstance is not None:
      if self.toField:
        kwargs["initData"] = getattr(self.parentInstance, self.toField)
      else:
        kwargs["initData"] = self.parentInstance.pk
    kwargs["required"] = False
    super(InlineForeignKeyField, self).__init__(*args, **kwargs)

  def clean(self, value, isEmptyForgiven=False):
    if value in self.emptyValues:
      if self.pkField:
        return None
      # if there is no value act as we did before.
      return self.parentInstance
    # ensure the we compare the values as equal types.
    if self.toField:
      orig = getattr(self.parentInstance, self.toField)
    else:
      orig = self.parentInstance.pk
    if forceText(value) != forceText(orig):
      raise ValidationError(self.errorMessages['invalidChoice'], code='invalidChoice')
    return self.parentInstance

  def _hasChanged(self, initData, data):
    return False


class ModelChoiceIterator(object):
  # We might use it in the future
  def __init__(self, field):
    self.field = field
    self.queryset = field.queryset

  def __iter__(self):
    if self.field.cacheChoices:
      if self.field.choiceCache is None:
        self.field.choiceCache = [
          self.choice(obj) for obj in self.queryset.all()
        ]
      for choice in self.field.choiceCache:
        yield choice
    else:
      for obj in self.queryset.all():
        yield self.choice(obj)

  def __len__(self):
    return len(self.queryset)

  def choice(self, obj):
    return (self.field.prepareValue(obj), self.field.labelFromInstance(obj))


class ModelChoiceField(Field):
  """A ChoiceField whose choices are a model QuerySet."""
  # This class is a subclass of ChoiceField for purity, but it doesn't
  # actually use any of ChoiceField's implementation.
  defaultErrorMessages = {
    'invalidChoice': _('Select a valid choice. That choice is not one of'
              ' the available choices.'),
  }
  widget = "QueryIdInput"

  def __init__(self, queryset, cacheChoices=None,
         required=True, widget=None, label=None, initData=None,
         helpText='', toFieldName=None, limitChoicesTo=None,
         *args, **kwargs):
    if cacheChoices is not None:
      warnings.warn("cacheChoices has been deprecated and will be "
        "removed in Theory 1.9.",
        RemovedInTheory19Warning, stacklevel=2)
    else:
      cacheChoices = False
    self.cacheChoices = cacheChoices

    if "widget" not in kwargs:
      kwargs["widget"] = self.widget
    # Call Field instead of ChoiceField __init__() because we don't need
    # ChoiceField.__init__().
    Field.__init__(self, required, label, initData, helpText,
            *args, **kwargs)
    self.queryset = queryset
    self.limitChoicesTo = limitChoicesTo   # limit the queryset later.
    self.choiceCache = None
    self.toFieldName = toFieldName

  def renderWidget(self, *args, **kwargs):
    if("attrs" not in kwargs):
      kwargs["attrs"] = {}
    module = self.queryset.modal.__module__
    appName = module[:module.find(".model")]
    kwargs["initData"] = self.initData

    # queryset in here means all objects in db
    kwargs["attrs"].update({
      "appName": appName,
      "modelName": self.queryset.modal.__name__,
      "queryset": self.initData,
      "isMultiple": "list" in self.defaultErrorMessages,
      })
    super(ModelChoiceField, self).renderWidget(*args, **kwargs)
    self.widget.queryset = self.queryset
    self.widget.attrs["appName"] = appName
    self.widget.attrs["mdlName"] = self.queryset.modal.__name__

  #def __deepcopy__(self, memo):
  #  result = super(ChoiceField, self).__deepcopy__(memo)
  #  # Need to force a new ModelChoiceIterator to be created, bug #11183
  #  result.queryset = result.queryset
  #  return result

  def _getQueryset(self):
    return self._queryset

  def _setQueryset(self, queryset):
    if isinstance(self.widget, str):
      self._queryset = queryset
    elif isinstance(queryset, dict):
      self.widget.app = queryset["appName"]
      self.widget.model = queryset["modelName"]
      modelKlass = importClass("{appName}.model.{modelName}".format(**queryset))
      if "idLst" in queryset:
        self._queryset = modelKlass.objects.filter(id__in=queryset["idLst"])
      elif "id" in queryset:
        self._queryset = modelKlass.objects.filter(id=queryset["id"])
      else:
        raise self
    else:
      self._queryset = queryset
      self.widget.queryset = queryset
      module = queryset.modal.__module__
      appName = module[:module.find(".model")]
      self.widget.attrs["appName"] = appName
      self.widget.attrs["mdlName"] = queryset.modal.__name__

  queryset = property(_getQueryset, _setQueryset)

  # this method will be used to create object labels by the QuerySetIterator.
  # Override it to customize the label.
  def labelFromInstance(self, obj):
    """
    This method is used to convert objects into strings; it's used to
    generate the labels for the choices presented by this object. Subclasses
    can override this method to customize the display of the choices.
    """
    return smartText(obj)

  def _getChoices(self):
    # If self._choices is set, then somebody must have manually set
    # the property self.choices. In this case, just return self._choices.
    if hasattr(self, '_choices'):
      return self._choices

    # Otherwise, execute the QuerySet in self.queryset to determine the
    # choices dynamically. Return a fresh ModelChoiceIterator that has not been
    # consumed. Note that we're instantiating a new ModelChoiceIterator *each*
    # time _getChoices() is called (and, thus, each time self.choices is
    # accessed) so that we can ensure the QuerySet has not been consumed. This
    # construct might look complicated but it allows for lazy evaluation of
    # the queryset.
    return ModelChoiceIterator(self)

  #choices = property(_getChoices, ChoiceField._setChoices)

  def prepareValue(self, value):
    if hasattr(value, '_meta'):
      if self.toFieldName:
        return value.serializableValue(self.toFieldName)
      else:
        return value.pk
    return super(ModelChoiceField, self).prepareValue(value)

  def toPython(self, value):
    if value in self.emptyValues:
      return None
    elif type(value.__class__.__bases__[0]).__name__ == "ModelBase":
      # Already an model instance
      return value
    try:
      key = self.toFieldName or 'pk'
      value = self.queryset.get(**{key: value})
    except (ValueError, self.queryset.modal.DoesNotExist):
      raise ValidationError(self.errorMessages['invalidChoice'], code='invalidChoice')
    return value

  def validate(self, value):
    return Field.validate(self, value)

  def _hasChanged(self, initData, data):
    initDataValue = initData if initData is not None else ''
    dataValue = data if data is not None else ''
    return forceText(self.prepareValue(initDataValue)) != forceText(dataValue)

  def getModelFieldNameSuffix(self):
    return "Id"

class ModelMultipleChoiceField(ModelChoiceField):
  """A MultipleChoiceField whose choices are a model QuerySet."""
  widget =  "QueryIdInput"
  defaultErrorMessages = {
    'list': _('Enter a list of values.'),
    'invalidChoice': _('Select a valid choice. %(value)s is not one of the'
              ' available choices.'),
    'invalidPkValue': _('"%(pk)s" is not a valid value for a primary key.')
  }

  def __init__(self, queryset, cacheChoices=None, required=True,
         widget=None, label=None, initData=None,
         helpText='', *args, **kwargs):
    super(ModelMultipleChoiceField, self).__init__(queryset,
      cacheChoices, required, widget, label, initData, helpText,
      *args, **kwargs)

  def toPython(self, value):
    if not value:
      return []
    toPy = super(ModelMultipleChoiceField, self).toPython
    return [toPy(val) for val in value]

  def clean(self, value, isEmptyForgiven=False):
    if self.required and not value:
      raise ValidationError(self.errorMessages['required'], code='required')
    elif not self.required and not value:
      return self.queryset.none()
    elif type(value).__name__=="QuerySet":
      return value
    if not isinstance(value, (list, tuple)):
      raise ValidationError(self.errorMessages['list'], code='list')
    if len(value) > 0 and isinstance(value[0], dict):
      # after seialize, we got [{"modelName": "", "id": "", "appName": ""]
      value = [i["id"] for i in value]
    key = self.toFieldName or 'pk'

    # if the initData is none, the queryset is empty and hence any id lst
    # provided by user will be invalid
    if self.initData is None:
      self.queryset = self.queryset.modal.objects.all()

    for pk in value:
      try:
        self.queryset.filter(**{key: pk})
      except ValueError:
        raise ValidationError(
          self.errorMessages['invalidPkValue'],
          code='invalidPkValue',
          params={'pk': pk},
        )
    qs = self.queryset.filter(**{'%s__in' % key: value})
    pks = set(forceText(getattr(o, key)) for o in qs)
    for val in value:
      if forceText(val) not in pks:
        raise ValidationError(
          self.errorMessages['invalidChoice'],
          code='invalidChoice',
          params={'value': val},
        )
    # Since this overrides the inherited ModelChoiceField.clean
    # we run custom validators here
    self.runValidators(value)
    return qs

  def prepareValue(self, value):
    if (hasattr(value, '__iter__') and
        not isinstance(value, six.textType) and
        not hasattr(value, '_meta')):
      return [super(ModelMultipleChoiceField, self).prepareValue(v) for v in value]
    return super(ModelMultipleChoiceField, self).prepareValue(value)

  def _hasChanged(self, initData, data):
    if initData is None:
      initData = []
    if data is None:
      data = []
    if len(initData) != len(data):
      return True
    initDataSet = set(forceText(value) for value in self.prepareValue(initData))
    dataSet = set(forceText(value) for value in data)
    return dataSet != initDataSet


  def getModelFieldNameSuffix(self):
    return "__m2m"


