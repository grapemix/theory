"""
Helper functions for creating Form classes from Theory model
and database field objects.
"""

from __future__ import unicode_literals

from collections import OrderedDict
import warnings

from theory.core.exceptions import (
  ImproperlyConfigured, ValidationError, NON_FIELD_ERRORS, FieldError)
from theory.gui.field import Field
from theory.gui.common.baseForm import DeclarativeFieldsMetaclass, FormBase
from theory.gui.formset import BaseFormSet, formsetFactory
from theory.gui.util import ErrorList
from theory.gui.widget import (
    QueryIdInput,
    HiddenInput,
    )
from theory.utils import six
from theory.utils.deprecation import RemovedInTheory19Warning
from theory.utils.encoding import smartText, forceText
from theory.utils.importlib import importClass
from theory.utils.text import getTextList, capfirst
from theory.utils.translation import ugettextLazy as _, ugettext


__all__ = (
  'ModelForm', 'BaseModelForm', 'modelToDict', 'fieldsForModel',
  'saveInstance', 'ModelChoiceField', 'ModelMultipleChoiceField',
  'ALL_FIELDS', 'BaseModelFormSet', 'modelformsetFactory',
  'BaseInlineFormSet', 'inlineformsetFactory',
)

ALL_FIELDS = '__all__'


def constructInstance(form, instance, fields=None, exclude=None):
  """
  Constructs and returns a model instance from the bound ``form``'s
  ``cleanedData``, but does not save the returned instance to the
  database.
  """
  from theory.db import model
  opts = instance._meta

  cleanedData = form.cleanedData
  fileFieldList = []
  for f in opts.fields:
    if not f.editable or isinstance(f, model.AutoField) \
        or f.name not in cleanedData:
      continue
    if fields is not None and f.name not in fields:
      continue
    if exclude and f.name in exclude:
      continue
    # Defer saving file-type fields until after the other fields, so a
    # callable uploadTo can use the values from other fields.
    if isinstance(f, model.FileField):
      fileFieldList.append(f)
    else:
      f.saveFormData(instance, cleanedData[f.name])

  for f in fileFieldList:
    f.saveFormData(instance, cleanedData[f.name])

  return instance


def saveInstance(form, instance, fields=None, failMessage='saved',
         commit=True, exclude=None, construct=True):
  """
  Saves bound Form ``form``'s cleanedData into model instance ``instance``.

  If commit=True, then the changes to ``instance`` will be saved to the
  database. Returns ``instance``.

  If construct=False, assume ``instance`` has already been constructed and
  just needs to be saved.
  """
  if construct:
    instance = constructInstance(form, instance, fields, exclude)
  opts = instance._meta
  if form.errors:
    raise ValueError("The %s could not be %s because the data didn't"
             " validate." % (opts.objectName, failMessage))

  # Wrap up the saving of m2m data as a function.
  def saveM2m():
    cleanedData = form.cleanedData
    # Note that for historical reasons we want to include also
    # virtualFields here. (GenericRelation was previously a fake
    # m2m field).
    for f in opts.manyToMany + opts.virtualFields:
      if not hasattr(f, 'saveFormData'):
        continue
      if fields and f.name not in fields:
        continue
      if exclude and f.name in exclude:
        continue
      if f.name in cleanedData:
        f.saveFormData(instance, cleanedData[f.name])
  if commit:
    # If we are committing, save the instance and the m2m data immediately.
    instance.save()
    saveM2m()
  else:
    # We're not committing. Add a method to the form to allow deferred
    # saving of m2m data.
    form.saveM2m = saveM2m
  return instance


# ModelForms #################################################################

def modelToDict(instance, fields=None, exclude=None):
  """
  Returns a dict containing the data in ``instance`` suitable for passing as
  a Form's ``initData`` keyword argument.

  ``fields`` is an optional list of field names. If provided, only the named
  fields will be included in the returned dict.

  ``exclude`` is an optional list of field names. If provided, the named
  fields will be excluded from the returned dict, even if they are listed in
  the ``fields`` argument.
  """
  # avoid a circular import
  from theory.db.model.fields.related import ManyToManyField
  opts = instance._meta
  data = {}
  for f in opts.concreteFields + opts.virtualFields + opts.manyToMany:
    if not getattr(f, 'editable', False):
      continue
    if fields and f.name not in fields:
      continue
    if exclude and f.name in exclude:
      continue
    if isinstance(f, ManyToManyField):
      # If the object doesn't have a primary key yet, just use an empty
      # list for its m2m fields. Calling f.valueFromObject will raise
      # an exception.
      if instance.pk is None:
        data[f.name] = []
      else:
        # MultipleChoiceWidget needs a list of pks, not object instances.
        qs = f.valueFromObject(instance)
        if qs._resultCache is not None:
          data[f.name] = [item.pk for item in qs]
        else:
          data[f.name] = list(qs.valuesList('pk', flat=True))
    else:
      data[f.name] = f.valueFromObject(instance)
  return data


def fieldsForModel(model, fields=None, exclude=None, widgets=None,
           formfieldCallback=None, localizedFields=None,
           labels=None, helpTexts=None, errorMessages=None):
  """
  Returns a ``OrderedDict`` containing form fields for the given model.

  ``fields`` is an optional list of field names. If provided, only the named
  fields will be included in the returned fields.

  ``exclude`` is an optional list of field names. If provided, the named
  fields will be excluded from the returned fields, even if they are listed
  in the ``fields`` argument.

  ``widgets`` is a dictionary of model field names mapped to a widget.

  ``localizedFields`` is a list of names of fields which should be localized.

  ``labels`` is a dictionary of model field names mapped to a label.

  ``helpTexts`` is a dictionary of model field names mapped to a help text.

  ``errorMessages`` is a dictionary of model field names mapped to a
  dictionary of error messages.

  ``formfieldCallback`` is a callable that takes a model field and returns
  a form field.
  """
  fieldList = []
  ignored = []
  opts = model._meta
  # Avoid circular import
  from theory.db.model.fields import Field as ModelField
  sortableVirtualFields = [f for f in opts.virtualFields
                if isinstance(f, ModelField)]
  for f in sorted(opts.concreteFields + sortableVirtualFields + opts.manyToMany):
    if not getattr(f, 'editable', False):
      continue
    if fields is not None and f.name not in fields:
      continue
    if exclude and f.name in exclude:
      continue

    kwargs = {}
    if widgets and f.name in widgets:
      kwargs['widget'] = widgets[f.name]
    if localizedFields == ALL_FIELDS or (localizedFields and f.name in localizedFields):
      kwargs['localize'] = True
    if labels and f.name in labels:
      kwargs['label'] = labels[f.name]
    if helpTexts and f.name in helpTexts:
      kwargs['helpText'] = helpTexts[f.name]
    if errorMessages and f.name in errorMessages:
      kwargs['errorMessages'] = errorMessages[f.name]

    if formfieldCallback is None:
      formfield = f.formfield(**kwargs)
    elif not callable(formfieldCallback):
      raise TypeError('formfieldCallback must be a function or callable')
    else:
      formfield = formfieldCallback(f, **kwargs)

    if formfield:
      fieldList.append((f.name, formfield))
    else:
      ignored.append(f.name)
  fieldDict = OrderedDict(fieldList)
  if fields:
    fieldDict = OrderedDict(
      [(f, fieldDict.get(f)) for f in fields
        if ((not exclude) or (exclude and f not in exclude)) and (f not in ignored)]
    )
  return fieldDict


class ModelFormOptions(object):
  def __init__(self, options=None):
    self.model = getattr(options, 'model', None)
    self.fields = getattr(options, 'fields', None)
    self.exclude = getattr(options, 'exclude', None)
    self.widgets = getattr(options, 'widgets', None)
    self.localizedFields = getattr(options, 'localizedFields', None)
    self.labels = getattr(options, 'labels', None)
    self.helpTexts = getattr(options, 'helpTexts', None)
    self.errorMessages = getattr(options, 'errorMessages', None)


class ModelFormMetaclass(DeclarativeFieldsMetaclass):
  def __new__(mcs, name, bases, attrs):
    formfieldCallback = attrs.pop('formfieldCallback', None)

    newClass = super(ModelFormMetaclass, mcs).__new__(mcs, name, bases, attrs)

    if bases == (BaseModelForm,):
      return newClass

    opts = newClass._meta = ModelFormOptions(getattr(newClass, 'Meta', None))

    # We check if a string was passed to `fields` or `exclude`,
    # which is likely to be a mistake where the user typed ('foo') instead
    # of ('foo',)
    for opt in ['fields', 'exclude', 'localizedFields']:
      value = getattr(opts, opt)
      if isinstance(value, six.stringTypes) and value != ALL_FIELDS:
        msg = ("%(model)s.Meta.%(opt)s cannot be a string. "
            "Did you mean to type: ('%(value)s',)?" % {
              'model': newClass.__name__,
              'opt': opt,
              'value': value,
            })
        raise TypeError(msg)

    if opts.model:
      # If a model is defined, extract form fields from it.
      if opts.fields is None and opts.exclude is None:
        raise ImproperlyConfigured(
          "Creating a ModelForm without either the 'fields' attribute "
          "or the 'exclude' attribute is prohibited; form %s "
          "needs updating." % name
        )

      if opts.fields == ALL_FIELDS:
        # Sentinel for fieldsForModel to indicate "get the list of
        # fields from the model"
        opts.fields = None

      fields = fieldsForModel(
          opts.model,
          fields=opts.fields,
          exclude=opts.exclude,
          widgets=opts.widgets,
          formfieldCallback=formfieldCallback,
          localizedFields=opts.localizedFields,
          labels=opts.labels,
          helpTexts=opts.helpTexts,
          errorMessages=opts.errorMessages
          )

      # make sure opts.fields doesn't specify an invalid field
      noneModelFields = [k for k, v in six.iteritems(fields) if not v]
      missingFields = (set(noneModelFields) -
               set(newClass.declaredFields.keys()))
      if missingFields:
        message = 'Unknown field(s) (%s) specified for %s'
        message = message % (', '.join(missingFields),
                   opts.model.__name__)
        raise FieldError(message)
      # Override default model fields with any custom declared ones
      # (plus, include all the other declared fields).
      fields.update(newClass.declaredFields)
    else:
      fields = newClass.declaredFields

    newClass.baseFields = fields

    return newClass


class BaseModelForm(FormBase):
  def __init__(self, initData=None, autoId='id_%s',
         errorClass=ErrorList, emptyPermitted=False, instance=None):
    opts = self._meta
    if opts.model is None:
      raise ValueError('ModelForm has no model class specified.')
    if instance is None:
      # if we didn't get an instance, instantiate a new one
      self.instance = opts.model()
      objectData = {}
    else:
      self.instance = instance
      objectData = modelToDict(instance, opts.fields, opts.exclude)
    # if initData was provided, it should override the values from instance
    if initData is not None:
      objectData.update(initData)
    # self._validateUnique will be set to True by BaseModelForm.clean().
    # It is False by default so overriding self.clean() and failing to call
    # super will stop validateUnique from being called.
    self._validateUnique = False
    super(BaseModelForm, self).__init__(
        initData=objectData,
        autoId=autoId,
        errorClass=errorClass,
        emptyPermitted=emptyPermitted
        )
    # Apply ``limitChoicesTo`` to each field.
    for fieldName in self.fields:
      formfield = self.fields[fieldName]
      try:
        formfield.initData = objectData[fieldName]
      except KeyError:
        pass
      if hasattr(formfield, 'queryset'):
        limitChoicesTo = formfield.limitChoicesTo
        if limitChoicesTo is not None:
          if callable(limitChoicesTo):
            limitChoicesTo = limitChoicesTo()
          formfield.queryset = formfield.queryset.complexFilter(limitChoicesTo)

  def _getValidationExclusions(self):
    """
    For backwards-compatibility, several types of fields need to be
    excluded from model validation. See the following tickets for
    details: #12507, #12521, #12553
    """
    exclude = []
    # Build up a list of fields that should be excluded from model field
    # validation and unique checks.
    for f in self.instance._meta.fields:
      field = f.name
      # Exclude fields that aren't on the form. The developer may be
      # adding these values to the model after form validation.
      if field not in self.fields:
        exclude.append(f.name)

      # Don't perform model validation on fields that were defined
      # manually on the form and excluded via the ModelForm's Meta
      # class. See #12901.
      elif self._meta.fields and field not in self._meta.fields:
        exclude.append(f.name)
      elif self._meta.exclude and field in self._meta.exclude:
        exclude.append(f.name)

      # Exclude fields that failed form validation. There's no need for
      # the model fields to validate them as well.
      elif field in self._errors.keys():
        exclude.append(f.name)

      # Exclude empty fields that are not required by the form, if the
      # underlying model field is required. This keeps the model field
      # from raising a required error. Note: don't exclude the field from
      # validation if the model field allows blanks. If it does, the blank
      # value may be included in a unique check, so cannot be excluded
      # from validation.
      else:
        formField = self.fields[field]
        fieldValue = self.cleanedData.get(field, None)
        if not f.blank and not formField.required and fieldValue in formField.emptyValues:
          exclude.append(f.name)
    return exclude

  def clean(self):
    self._validateUnique = True
    return self.cleanedData

  def _updateErrors(self, errors):
    # Override any validation error messages defined at the model level
    # with those defined at the form level.
    opts = self._meta
    for field, messages in errors.errorDict.items():
      if (field == NON_FIELD_ERRORS and opts.errorMessages and
          NON_FIELD_ERRORS in opts.errorMessages):
        errorMessages = opts.errorMessages[NON_FIELD_ERRORS]
      elif field in self.fields:
        errorMessages = self.fields[field].errorMessages
      else:
        continue

      for message in messages:
        if (isinstance(message, ValidationError) and
            message.code in errorMessages):
          message.message = errorMessages[message.code]

    self.addError(None, errors)

  def _postClean(self):
    opts = self._meta

    exclude = self._getValidationExclusions()
    # a subset of `exclude` which won't have the InlineForeignKeyField
    # if we're adding a new object since that value doesn't exist
    # until after the new instance is saved to the database.
    constructInstanceExclude = list(exclude)

    # Foreign Keys being used to represent inline relationships
    # are excluded from basic field value validation. This is for two
    # reasons: firstly, the value may not be supplied (#12507; the
    # case of providing new values to the admin); secondly the
    # object being referred to may not yet fully exist (#12749).
    # However, these fields *must* be included in uniqueness checks,
    # so this can't be part of _getValidationExclusions().
    for name, field in self.fields.items():
      if isinstance(field, InlineForeignKeyField):
        if self.cleanedData.get(name) is not None and self.cleanedData[name]._state.adding:
          constructInstanceExclude.append(name)
        exclude.append(name)

    # Update the model instance with self.cleanedData.
    self.instance = constructInstance(self, self.instance, opts.fields, constructInstanceExclude)

    try:
      self.instance.fullClean(exclude=exclude, validateUnique=False)
    except ValidationError as e:
      self._updateErrors(e)

    # Validate uniqueness if needed.
    if self._validateUnique:
      self.validateUnique()

  def validateUnique(self):
    """
    Calls the instance's validateUnique() method and updates the form's
    validation errors if any were raised.
    """
    exclude = self._getValidationExclusions()
    try:
      self.instance.validateUnique(exclude=exclude)
    except ValidationError as e:
      self._updateErrors(e)

  def save(self, commit=True):
    """
    Saves this ``form``'s cleanedData into model instance
    ``self.instance``.

    If commit=True, then the changes to ``instance`` will be saved to the
    database. Returns ``instance``.
    """
    if self.instance.pk is None:
      failMessage = 'created'
    else:
      failMessage = 'changed'
    return saveInstance(self, self.instance, self._meta.fields,
               failMessage, commit, self._meta.exclude,
               construct=False)

  save.altersData = True


class ModelForm(six.withMetaclass(ModelFormMetaclass, BaseModelForm)):
  pass


def modelformFactory(model, form=ModelForm, fields=None, exclude=None,
           formfieldCallback=None, widgets=None, localizedFields=None,
           labels=None, helpTexts=None, errorMessages=None):
  """
  Returns a ModelForm containing form fields for the given model.

  ``fields`` is an optional list of field names. If provided, only the named
  fields will be included in the returned fields. If omitted or '__all__',
  all fields will be used.

  ``exclude`` is an optional list of field names. If provided, the named
  fields will be excluded from the returned fields, even if they are listed
  in the ``fields`` argument.

  ``widgets`` is a dictionary of model field names mapped to a widget.

  ``localizedFields`` is a list of names of fields which should be localized.

  ``formfieldCallback`` is a callable that takes a model field and returns
  a form field.

  ``labels`` is a dictionary of model field names mapped to a label.

  ``helpTexts`` is a dictionary of model field names mapped to a help text.

  ``errorMessages`` is a dictionary of model field names mapped to a
  dictionary of error messages.
  """
  # Create the inner Meta class. FIXME: ideally, we should be able to
  # construct a ModelForm without creating and passing in a temporary
  # inner class.

  # Build up a list of attributes that the Meta object will have.
  attrs = {'model': model}
  if fields is not None:
    attrs['fields'] = fields
  if exclude is not None:
    attrs['exclude'] = exclude
  if widgets is not None:
    attrs['widgets'] = widgets
  if localizedFields is not None:
    attrs['localizedFields'] = localizedFields
  if labels is not None:
    attrs['labels'] = labels
  if helpTexts is not None:
    attrs['helpTexts'] = helpTexts
  if errorMessages is not None:
    attrs['errorMessages'] = errorMessages

  # If parent form class already has an inner Meta, the Meta we're
  # creating needs to inherit from the parent's inner meta.
  parent = (object,)
  if hasattr(form, 'Meta'):
    parent = (form.Meta, object)
  Meta = type(str('Meta'), parent, attrs)

  # Give this new form class a reasonable name.
  className = model.__name__ + str('Form')

  # Class attributes for the new form class.
  formClassAttrs = {
    'Meta': Meta,
    'formfieldCallback': formfieldCallback
  }

  if (getattr(Meta, 'fields', None) is None and
      getattr(Meta, 'exclude', None) is None):
    raise ImproperlyConfigured(
      "Calling modelformFactory without defining 'fields' or "
      "'exclude' explicitly is prohibited."
    )

  # Instatiate type(form) in order to use the same metaclass as form.
  return type(form)(className, (form,), formClassAttrs)


# ModelFormSets ##############################################################

class BaseModelFormSet(BaseFormSet):
  """
  A ``FormSet`` for editing a queryset and/or adding new objects to it.
  """
  model = None

  def __init__(self, data=None, files=None, autoId='id_%s', prefix=None,
         queryset=None, **kwargs):
    self.queryset = queryset
    self.initDataExtra = kwargs.pop('initData', None)
    defaults = {'data': data, 'files': files, 'autoId': autoId, 'prefix': prefix}
    defaults.update(kwargs)
    super(BaseModelFormSet, self).__init__(**defaults)

  def initDataFormCount(self):
    """Returns the number of forms that are required in this FormSet."""
    if not (self.data or self.files):
      return len(self.getQueryset())
    return super(BaseModelFormSet, self).initDataFormCount()

  def _existingObject(self, pk):
    if not hasattr(self, '_objectDict'):
      self._objectDict = dict((o.pk, o) for o in self.getQueryset())
    return self._objectDict.get(pk)

  def _getToPython(self, field):
    """
    If the field is a related field, fetch the concrete field's (that
    is, the ultimate pointed-to field's) getPrepValue.
    """
    while field.rel is not None:
      field = field.rel.getRelatedField()
    return field.toPython

  def _constructForm(self, i, **kwargs):
    if self.isBound and i < self.initDataFormCount():
      pkKey = "%s-%s" % (self.addPrefix(i), self.model._meta.pk.name)
      pk = self.data[pkKey]
      pkField = self.model._meta.pk
      toPython = self._getToPython(pkField)
      pk = toPython(pk)
      kwargs['instance'] = self._existingObject(pk)
    if i < self.initDataFormCount() and 'instance' not in kwargs:
      kwargs['instance'] = self.getQueryset()[i]
    if i >= self.initDataFormCount() and self.initDataExtra:
      # Set initData values for extra forms
      try:
        kwargs['initData'] = self.initDataExtra[i - self.initDataFormCount()]
      except IndexError:
        pass
    return super(BaseModelFormSet, self)._constructForm(i, **kwargs)

  def getQueryset(self):
    if not hasattr(self, '_queryset'):
      if self.queryset is not None:
        qs = self.queryset
      else:
        qs = self.model._defaultManager.getQueryset()

      # If the queryset isn't already ordered we need to add an
      # artificial ordering here to make sure that all formsets
      # constructed from this queryset have the same form order.
      if not qs.ordered:
        qs = qs.orderBy(self.model._meta.pk.name)

      # Removed queryset limiting here. As per discussion re: #13023
      # on theory-dev, maxNum should not prevent existing
      # related objects/inlines from being displayed.
      self._queryset = qs
    return self._queryset

  def saveNew(self, form, commit=True):
    """Saves and returns a new model instance for the given form."""
    return form.save(commit=commit)

  def saveExisting(self, form, instance, commit=True):
    """Saves and returns an existing model instance for the given form."""
    return form.save(commit=commit)

  def save(self, commit=True):
    """Saves model instances for every form, adding and changing instances
    as necessary, and returns the list of instances.
    """
    if not commit:
      self.savedForms = []

      def saveM2m():
        for form in self.savedForms:
          form.saveM2m()
      self.saveM2m = saveM2m
    return self.saveExistingObjects(commit) + self.saveNewObjects(commit)

  save.altersData = True

  def clean(self):
    self.validateUnique()

  def validateUnique(self):
    # Collect uniqueChecks and dateChecks to run from all the forms.
    allUniqueChecks = set()
    allDateChecks = set()
    formsToDelete = self.deletedForms
    validForms = [form for form in self.forms if form.isValid() and form not in formsToDelete]
    for form in validForms:
      exclude = form._getValidationExclusions()
      uniqueChecks, dateChecks = form.instance._getUniqueChecks(exclude=exclude)
      allUniqueChecks = allUniqueChecks.union(set(uniqueChecks))
      allDateChecks = allDateChecks.union(set(dateChecks))

    errors = []
    # Do each of the unique checks (unique and uniqueTogether)
    for uclass, uniqueCheck in allUniqueChecks:
      seenData = set()
      for form in validForms:
        # get data for each field of each of uniqueCheck
        rowData = (form.cleanedData[field]
              for field in uniqueCheck if field in form.cleanedData)
        # Reduce Model instances to their primary key values
        rowData = tuple(d._getPkVal() if hasattr(d, '_getPkVal') else d
                 for d in rowData)
        if rowData and None not in rowData:
          # if we've already seen it then we have a uniqueness failure
          if rowData in seenData:
            # poke error messages into the right places and mark
            # the form as invalid
            errors.append(self.getUniqueErrorMessage(uniqueCheck))
            form._errors[NON_FIELD_ERRORS] = self.errorClass([self.getFormError()])
            # remove the data from the cleanedData dict since it was invalid
            for field in uniqueCheck:
              if field in form.cleanedData:
                del form.cleanedData[field]
          # mark the data as seen
          seenData.add(rowData)
    # iterate over each of the date checks now
    for dateCheck in allDateChecks:
      seenData = set()
      uclass, lookup, field, uniqueFor = dateCheck
      for form in validForms:
        # see if we have data for both fields
        if (form.cleanedData and form.cleanedData[field] is not None
            and form.cleanedData[uniqueFor] is not None):
          # if it's a date lookup we need to get the data for all the fields
          if lookup == 'date':
            date = form.cleanedData[uniqueFor]
            dateData = (date.year, date.month, date.day)
          # otherwise it's just the attribute on the date/datetime
          # object
          else:
            dateData = (getattr(form.cleanedData[uniqueFor], lookup),)
          data = (form.cleanedData[field],) + dateData
          # if we've already seen it then we have a uniqueness failure
          if data in seenData:
            # poke error messages into the right places and mark
            # the form as invalid
            errors.append(self.getDateErrorMessage(dateCheck))
            form._errors[NON_FIELD_ERRORS] = self.errorClass([self.getFormError()])
            # remove the data from the cleanedData dict since it was invalid
            del form.cleanedData[field]
          # mark the data as seen
          seenData.add(data)

    if errors:
      raise ValidationError(errors)

  def getUniqueErrorMessage(self, uniqueCheck):
    if len(uniqueCheck) == 1:
      return ugettext("Please correct the duplicate data for %(field)s.") % {
        "field": uniqueCheck[0],
      }
    else:
      return ugettext("Please correct the duplicate data for %(field)s, "
        "which must be unique.") % {
        "field": getTextList(uniqueCheck, six.textType(_("and"))),
      }

  def getDateErrorMessage(self, dateCheck):
    return ugettext("Please correct the duplicate data for %(fieldName)s "
      "which must be unique for the %(lookup)s in %(dateField)s.") % {
      'fieldName': dateCheck[2],
      'dateField': dateCheck[3],
      'lookup': six.textType(dateCheck[1]),
    }

  def getFormError(self):
    return ugettext("Please correct the duplicate values below.")

  def saveExistingObjects(self, commit=True):
    self.changedObjects = []
    self.deletedObjects = []
    if not self.initDataForms:
      return []

    savedInstances = []
    formsToDelete = self.deletedForms
    for form in self.initDataForms:
      obj = form.instance
      if form in formsToDelete:
        # If the pk is None, it means that the object can't be
        # deleted again. Possible reason for this is that the
        # object was already deleted from the DB. Refs #14877.
        if obj.pk is None:
          continue
        self.deletedObjects.append(obj)
        if commit:
          obj.delete()
      elif form.hasChanged():
        self.changedObjects.append((obj, form.changedData))
        savedInstances.append(self.saveExisting(form, obj, commit=commit))
        if not commit:
          self.savedForms.append(form)
    return savedInstances

  def saveNewObjects(self, commit=True):
    self.newObjects = []
    for form in self.extraForms:
      if not form.hasChanged():
        continue
      # If someone has marked an add form for deletion, don't save the
      # object.
      if self.canDelete and self._shouldDeleteForm(form):
        continue
      self.newObjects.append(self.saveNew(form, commit=commit))
      if not commit:
        self.savedForms.append(form)
    return self.newObjects

  def addFields(self, form, index):
    """Add a hidden field for the object's primary key."""
    from theory.db.model import AutoField, OneToOneField, ForeignKey
    self._pkField = pk = self.model._meta.pk
    # If a pk isn't editable, then it won't be on the form, so we need to
    # add it here so we can tell which object is which when we get the
    # data back. Generally, pk.editable should be false, but for some
    # reason, autoCreated pk fields and AutoField's editable attribute is
    # True, so check for that as well.

    def pkIsNotEditable(pk):
      return ((not pk.editable) or (pk.autoCreated or isinstance(pk, AutoField))
        or (pk.rel and pk.rel.parentLink and pkIsNotEditable(pk.rel.to._meta.pk)))
    if pkIsNotEditable(pk) or pk.name not in form.fields:
      if form.isBound:
        pkValue = form.instance.pk
      else:
        try:
          if index is not None:
            pkValue = self.getQueryset()[index].pk
          else:
            pkValue = None
        except IndexError:
          pkValue = None
      if isinstance(pk, OneToOneField) or isinstance(pk, ForeignKey):
        qs = pk.rel.to._defaultManager.getQueryset()
      else:
        qs = self.model._defaultManager.getQueryset()
      qs = qs.using(form.instance._state.db)
      if form._meta.widgets:
        widget = form._meta.widgets.get(self._pkField.name, HiddenInput)
      else:
        widget = HiddenInput
      form.fields[self._pkField.name] = ModelChoiceField(qs, initData=pkValue, required=False, widget=widget)
    super(BaseModelFormSet, self).addFields(form, index)


def modelformsetFactory(model, form=ModelForm, formfieldCallback=None,
             formset=BaseModelFormSet, extra=1, canDelete=False,
             canOrder=False, maxNum=None, fields=None, exclude=None,
             widgets=None, validateMax=False, localizedFields=None,
             labels=None, helpTexts=None, errorMessages=None,
             minNum=None, validateMin=False):
  """
  Returns a FormSet class for the given Theory model class.
  """
  meta = getattr(form, 'Meta', None)
  if meta is None:
    meta = type(str('Meta'), (object,), {})
  if (getattr(meta, 'fields', fields) is None and
      getattr(meta, 'exclude', exclude) is None):
    raise ImproperlyConfigured(
      "Calling modelformsetFactory without defining 'fields' or "
      "'exclude' explicitly is prohibited."
    )

  form = modelformFactory(model, form=form, fields=fields, exclude=exclude,
               formfieldCallback=formfieldCallback,
               widgets=widgets, localizedFields=localizedFields,
               labels=labels, helpTexts=helpTexts, errorMessages=errorMessages)
  FormSet = formsetFactory(form, formset, extra=extra, minNum=minNum, maxNum=maxNum,
               canOrder=canOrder, canDelete=canDelete,
               validateMin=validateMin, validateMax=validateMax)
  FormSet.model = model
  return FormSet


# InlineFormSets #############################################################

class BaseInlineFormSet(BaseModelFormSet):
  """A formset for child objects related to a parent."""
  def __init__(self, data=None, files=None, instance=None,
         saveAsNew=False, prefix=None, queryset=None, **kwargs):
    if instance is None:
      self.instance = self.fk.rel.to()
    else:
      self.instance = instance
    self.saveAsNew = saveAsNew
    if queryset is None:
      queryset = self.model._defaultManager
    if self.instance.pk is not None:
      qs = queryset.filter(**{self.fk.name: self.instance})
    else:
      qs = queryset.none()
    super(BaseInlineFormSet, self).__init__(data, files, prefix=prefix,
                        queryset=qs, **kwargs)

  def initDataFormCount(self):
    if self.saveAsNew:
      return 0
    return super(BaseInlineFormSet, self).initDataFormCount()

  def _constructForm(self, i, **kwargs):
    form = super(BaseInlineFormSet, self)._constructForm(i, **kwargs)
    if self.saveAsNew:
      # Remove the primary key from the form's data, we are only
      # creating new instances
      form.data[form.addPrefix(self._pkField.name)] = None

      # Remove the foreign key from the form's data
      form.data[form.addPrefix(self.fk.name)] = None

    # Set the fk value here so that the form can do its validation.
    fkValue = self.instance.pk
    if self.fk.rel.fieldName != self.fk.rel.to._meta.pk.name:
      fkValue = getattr(self.instance, self.fk.rel.fieldName)
      fkValue = getattr(fkValue, 'pk', fkValue)
    setattr(form.instance, self.fk.getAttname(), fkValue)
    return form

  @classmethod
  def getDefaultPrefix(cls):
    from theory.db.model.fields.related import RelatedObject
    return RelatedObject(cls.fk.rel.to, cls.model, cls.fk).getAccessorName().replace('+', '')

  def saveNew(self, form, commit=True):
    # Use commit=False so we can assign the parent key afterwards, then
    # save the object.
    obj = form.save(commit=False)
    pkValue = getattr(self.instance, self.fk.rel.fieldName)
    setattr(obj, self.fk.getAttname(), getattr(pkValue, 'pk', pkValue))
    if commit:
      obj.save()
    # form.saveM2m() can be called via the formset later on if commit=False
    if commit and hasattr(form, 'saveM2m'):
      form.saveM2m()
    return obj

  def addFields(self, form, index):
    super(BaseInlineFormSet, self).addFields(form, index)
    if self._pkField == self.fk:
      name = self._pkField.name
      kwargs = {'pkField': True}
    else:
      # The foreign key field might not be on the form, so we poke at the
      # Model field to get the label, since we need that for error messages.
      name = self.fk.name
      kwargs = {
        'label': getattr(form.fields.get(name), 'label', capfirst(self.fk.verboseName))
      }
      if self.fk.rel.fieldName != self.fk.rel.to._meta.pk.name:
        kwargs['toField'] = self.fk.rel.fieldName

    form.fields[name] = InlineForeignKeyField(self.instance, **kwargs)

    # Add the generated field to form._meta.fields if it's defined to make
    # sure validation isn't skipped on that field.
    if form._meta.fields:
      if isinstance(form._meta.fields, tuple):
        form._meta.fields = list(form._meta.fields)
      form._meta.fields.append(self.fk.name)

  def getUniqueErrorMessage(self, uniqueCheck):
    uniqueCheck = [field for field in uniqueCheck if field != self.fk.name]
    return super(BaseInlineFormSet, self).getUniqueErrorMessage(uniqueCheck)


def _getForeignKey(parentModel, model, fkName=None, canFail=False):
  """
  Finds and returns the ForeignKey from model to parent if there is one
  (returns None if canFail is True and no such field exists). If fkName is
  provided, assume it is the name of the ForeignKey field. Unless canFail is
  True, an exception is raised if there is no ForeignKey from model to
  parentModel.
  """
  # avoid circular import
  from theory.db.model import ForeignKey
  opts = model._meta
  if fkName:
    fksToParent = [f for f in opts.fields if f.name == fkName]
    if len(fksToParent) == 1:
      fk = fksToParent[0]
      if not isinstance(fk, ForeignKey) or \
          (fk.rel.to != parentModel and
           fk.rel.to not in parentModel._meta.getParentList()):
        raise ValueError(
          "fkName '%s' is not a ForeignKey to '%s.%'."
          % (fkName, parentModel._meta.appLabel, parentModel._meta.objectName))
    elif len(fksToParent) == 0:
      raise ValueError(
        "'%s.%s' has no field named '%s'."
        % (model._meta.appLabel, model._meta.objectName, fkName))
  else:
    # Try to discover what the ForeignKey from model to parentModel is
    fksToParent = [
      f for f in opts.fields
      if isinstance(f, ForeignKey)
      and (f.rel.to == parentModel
        or f.rel.to in parentModel._meta.getParentList())
    ]
    if len(fksToParent) == 1:
      fk = fksToParent[0]
    elif len(fksToParent) == 0:
      if canFail:
        return
      raise ValueError(
        "'%s.%s' has no ForeignKey to '%s.%s'."
        % (model._meta.appLabel, model._meta.objectName, parentModel._meta.appLabel, parentModel._meta.objectName))
    else:
      raise ValueError(
        "'%s.%s' has more than one ForeignKey to '%s.%s'."
        % (model._meta.appLabel, model._meta.objectName, parentModel._meta.appLabel, parentModel._meta.objectName))
  return fk


def inlineformsetFactory(parentModel, model, form=ModelForm,
             formset=BaseInlineFormSet, fkName=None,
             fields=None, exclude=None, extra=3, canOrder=False,
             canDelete=True, maxNum=None, formfieldCallback=None,
             widgets=None, validateMax=False, localizedFields=None,
             labels=None, helpTexts=None, errorMessages=None,
             minNum=None, validateMin=False):
  """
  Returns an ``InlineFormSet`` for the given kwargs.

  You must provide ``fkName`` if ``model`` has more than one ``ForeignKey``
  to ``parentModel``.
  """
  fk = _getForeignKey(parentModel, model, fkName=fkName)
  # enforce a maxNum=1 when the foreign key to the parent model is unique.
  if fk.unique:
    maxNum = 1
  kwargs = {
    'form': form,
    'formfieldCallback': formfieldCallback,
    'formset': formset,
    'extra': extra,
    'canDelete': canDelete,
    'canOrder': canOrder,
    'fields': fields,
    'exclude': exclude,
    'minNum': minNum,
    'maxNum': maxNum,
    'widgets': widgets,
    'validateMin': validateMin,
    'validateMax': validateMax,
    'localizedFields': localizedFields,
    'labels': labels,
    'helpTexts': helpTexts,
    'errorMessages': errorMessages,
  }
  FormSet = modelformsetFactory(model, **kwargs)
  FormSet.fk = fk
  return FormSet


# Fields #####################################################################

class InlineForeignKeyField(Field):
  """
  A basic integer field that deals with validating the given value to a
  given parent instance in an inline.
  """
  widget = HiddenInput
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
  widget = QueryIdInput

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
    if isinstance(queryset, dict):
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
  widget =  QueryIdInput
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

def modelformDefinesFields(formClass):
  return (formClass is not None and (
      hasattr(formClass, '_meta') and
      (formClass._meta.fields is not None or
       formClass._meta.exclude is not None)
      ))
