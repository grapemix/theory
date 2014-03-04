# -*- coding: utf-8 -*-
#!/usr/bin/env python
##### System wide lib #####
import warnings

##### Theory lib #####
from theory.core.exceptions import ValidationError, NON_FIELD_ERRORS, FieldError
from theory.gui.common.baseForm import (
    DeclarativeFieldsMetaclass,
    FormBase,
    getDeclaredFields
    )
from theory.gui.field import Field, ChoiceField
from theory.gui.etk.form import StepFormBase
from theory.gui.formset import BaseFormSet, formsetFactory
from theory.gui.util import ErrorList
from theory.gui.transformer.mongoModelFormDetector import MongoModelFormDetector
from theory.gui.widget import (
    HiddenInput,
    )
from theory.model import AppModel
from theory.utils import six
from theory.utils.encoding import smartText, forceText
from theory.utils.datastructures import SortedDict
from theory.utils.importlib import importClass
from theory.utils.text import getTextList, capfirst
from theory.utils.translation import ugettextLazy as _, ugettext, stringConcat

##### Theory third-party lib #####

##### Local app #####

##### Theory app #####

##### Misc #####

"""
Helper functions for creating Form classes from Theory models
and database field objects.
"""

__all__ = (
  'ModelForm', 'ModelFormBase', 'fieldsForModel',
  'saveInstance', 'ModelChoiceField', 'ModelMultipleChoiceField',
  'ALL_FIELDS',
)

ALL_FIELDS = '__all__'


def constructInstance(form, instance, fields=None, exclude=None):
  """
  Constructs and returns a model instance from the bound ``form``'s
  ``cleanedData``, but does not save the returned instance to the
  database.
  """
  from theory.db import models
  opts = instance._meta

  cleanedData = form.cleanedData
  fileFieldList = []
  for f in opts.fields:
    if not f.editable or isinstance(f, models.AutoField) \
        or not f.name in cleanedData:
      continue
    if fields is not None and f.name not in fields:
      continue
    if exclude and f.name in exclude:
      continue
    # Defer saving file-type fields until after the other fields, so a
    # callable uploadTo can use the values from other fields.
    if isinstance(f, models.FileField):
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
    for f in opts.manyToMany:
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
def fieldsForModel(fieldDict, fields=None, exclude=None, widgets=None,
           formfieldCallback=None, localizedFields=None,
           labels=None, helpTexts=None, errorMessages=None):
  """
  Returns a ``SortedDict`` containing form fields for the given model.

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
  ignored = []
  for fieldName, fieldComplex in fieldDict.iteritems():
    (fieldKlass, args, kwargs) = fieldComplex
    if fields is not None and not fieldName in fields:
      continue
    if exclude and fieldName in exclude:
      continue

    if widgets and fieldName in widgets:
      kwargs['widget'] = widgets[fieldName]
    if localizedFields == ALL_FIELDS \
        or (localizedFields and fieldKlass.name in localizedFields):
      kwargs['localize'] = True
    kwargs['label'] = fieldName
    if helpTexts and f.name in helpTexts:
      kwargs['helpText'] = helpTexts[fieldName]
    if errorMessages and fieldKlass.name in errorMessages:
      kwargs['errorMessages'] = errorMessages[fieldName]

    if formfieldCallback is None:
      formfield = fieldKlass(*args, **kwargs)
    elif not callable(formfieldCallback):
      raise TypeError('formfieldCallback must be a function or callable')
    else:
      formfield = formfieldCallback(fieldName, **kwargs)

    if formfield:
      fieldDict[fieldName] = formfield
    else:
      ignored.append(fieldName)

  for i in ignored:
    del fieldDict[i]

  if fields:
    fieldDict = SortedDict(
      [(f, fieldDict.get(f)) for f in fields
        if ((not exclude) \
            or (exclude and f not in exclude)) \
            and (f not in ignored)
      ]
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


class ModelFormMetaclass(type):
  def __new__(cls, name, bases, attrs):
    formfieldCallback = attrs.pop('formfieldCallback', None)
    try:
      parents = [b for b in bases if issubclass(b, ModelForm)]
    except NameError:
      # We are defining ModelForm itself.
      parents = None
    declaredFields = getDeclaredFields(bases, attrs, False)
    newClass = super(ModelFormMetaclass, cls).__new__(cls, name, bases,
        attrs)
    if not parents:
      return newClass

    #if 'media' not in attrs:
    #  newClass.media = mediaProperty(newClass)
    opts = newClass._meta = ModelFormOptions(getattr(newClass, 'Meta', None))

    # We check if a string was passed to `fields` or `exclude`,
    # which is likely to be a mistake where the user typed ('foo') instead
    # of ('foo',)
    for opt in ['fields', 'exclude', 'localizedFields']:
      value = getattr(opts, opt)
      if isinstance(value, six.string_types) and value != ALL_FIELDS:
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
        # This should be some kind of assertion error once deprecation
        # cycle is complete.
        warnings.warn(
            "Creating a ModelForm without either the 'fields' attribute "
            "or the 'exclude' attribute is deprecated - form %s "
            "needs updating" % name,
               PendingDeprecationWarning,
               stacklevel=2
        )

      if opts.fields == ALL_FIELDS:
        # sentinel for fieldsForModel to indicate "get the list of
        # fields from the model"
        opts.fields = None

      fieldDict = MongoModelFormDetector().run(modelImportPath=opts.model)
      fields = fieldsForModel(fieldDict, opts.fields, opts.exclude,
                   opts.widgets, formfieldCallback,
                   opts.localizedFields, opts.labels,
                   opts.helpTexts, opts.errorMessages)
      opts.model = importClass(opts.model)

      # make sure opts.fields doesn't specify an invalid field
      noneModelFields = [k for k, v in six.iteritems(fields) if not v]
      missingFields = set(noneModelFields) - \
               set(declaredFields.keys())
      if missingFields:
        message = 'Unknown field(s) (%s) specified for %s'
        message = message % (', '.join(missingFields),
                   opts.model.__name__)
        raise FieldError(message)
      # Override default model fields with any custom declared ones
      # (plus, include all the other declared fields).
      fields.update(declaredFields)
    else:
      fields = declaredFields
    newClass.declaredFields = declaredFields
    newClass.baseFields = fields
    return newClass


class ModelFormBase(FormBase):
  def __init__(self, data=None, files=None, autoId='id_%s', prefix=None,
         initial=None, errorClass=ErrorList, labelSuffix=None,
         emptyPermitted=False, instance=None):
    opts = self._meta
    if opts.model is None:
      raise ValueError('ModelForm has no model class specified.')
    if instance is None:
      # if we didn't get an instance, instantiate a new one
      self.instance = opts.model()
    else:
      self.instance = instance
    for fieldName in self.baseFields.keys():
      self.baseFields[fieldName].initData = getattr(self.instance, fieldName)
    # self._validateUnique will be set to True by BaseModelForm.clean().
    # It is False by default so overriding self.clean() and failing to call
    # super will stop validateUnique from being called.
    self._validateUnique = False
    super(ModelFormBase, self).__init__(data, files, autoId, prefix,
                      errorClass, labelSuffix, emptyPermitted)

  def _updateErrors(self, errors):
    for field, messages in errors.errorDict.items():
      if field not in self.fields:
        continue
      field = self.fields[field]
      for message in messages:
        if isinstance(message, ValidationError):
          if message.code in field.errorMessages:
            message.message = field.errorMessages[message.code]

    messageDict = errors.messageDict
    for k, v in messageDict.items():
      if k != NON_FIELD_ERRORS:
        self._errors.setdefault(k, self.errorClass()).extend(v)
        # Remove the data from the cleanedData dict since it was invalid
        if k in self.cleanedData:
          del self.cleanedData[k]
    if NON_FIELD_ERRORS in messageDict:
      messages = messageDict[NON_FIELD_ERRORS]
      self._errors.setdefault(
          NON_FIELD_ERRORS,
          self.errorClass()
          ).extend(messages)

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
        if not f.blank \
            and not formField.required \
            and fieldValue in formField.emptyValues:
          exclude.append(f.name)
    return exclude

  def clean(self):
    self._validateUnique = True
    return self.cleaned_data

  def _postClean(self):
    opts = self._meta
    # Update the model instance with self.cleanedData.
    self.instance = constructInstance(
        self,
        self.instance,
        opts.fields,
        opts.exclude
        )

    exclude = self._getValidationExclusions()

    # Foreign Keys being used to represent inline relationships
    # are excluded from basic field value validation. This is for two
    # reasons: firstly, the value may not be supplied (#12507; the
    # case of providing new values to the admin); secondly the
    # object being referred to may not yet fully exist (#12749).
    # However, these fields *must* be included in uniqueness checks,
    # so this can't be part of _getValidationExclusions().
    for fName, field in self.fields.items():
      if isinstance(field, InlineForeignKeyField):
        exclude.append(fName)

    try:
      self.instance.fullClean(exclude=exclude,
        validateUnique=False)
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


class ModelForm(six.with_metaclass(ModelFormMetaclass, ModelFormBase)):
  pass

#class GuiModelForm(
#    six.with_metaclass(ModelFormMetaclass, StepFormBase, ModelFormBase)
#    #six.with_metaclass(ModelFormMetaclass, ModelFormBase, StepFormBase)
#    ):
#  pass

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

  # The ModelFormMetaclass will trigger a similar warning/error, but this will
  # be difficult to debug for code that needs updating, so we produce the
  # warning here too.
  if (getattr(Meta, 'fields', None) is None and
    getattr(Meta, 'exclude', None) is None):
    warnings.warn("Calling modelformFactory without defining 'fields' or "
           "'exclude' explicitly is deprecated",
           PendingDeprecationWarning, stacklevel=2)

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
    self.initialExtra = kwargs.pop('initial', None)
    defaults = {
        'data': data,
        'files': files,
        'autoId': autoId,
        'prefix': prefix
        }
    defaults.update(kwargs)
    super(BaseModelFormSet, self).__init__(**defaults)

  def initialFormCount(self):
    """Returns the number of forms that are required in this FormSet."""
    if not (self.data or self.files):
      return len(self.getQueryset())
    return super(BaseModelFormSet, self).initialFormCount()

  def _existingObject(self, pk):
    if not hasattr(self, '_objectDict'):
      self._objectDict = dict([(o.pk, o) for o in self.getQueryset()])
    return self._objectDict.get(pk)

  def _constructForm(self, i, **kwargs):
    if self.isBound and i < self.initialFormCount():
      # Import goes here instead of module-level because importing
      # theory.db has side effects.
      from theory.db import connections
      pkKey = "%s-%s" % (self.addPrefix(i), self.model._meta.pk.name)
      pk = self.data[pkKey]
      pkField = self.model._meta.pk
      pk = pkField.getDbPrepLookup('exact', pk,
        connection=connections[self.getQueryset().db])
      if isinstance(pk, list):
        pk = pk[0]
      kwargs['instance'] = self._existingObject(pk)
    if i < self.initialFormCount() and not kwargs.get('instance'):
      kwargs['instance'] = self.getQueryset()[i]
    if i >= self.initialFormCount() and self.initialExtra:
      # Set initial values for extra forms
      try:
        kwargs['initial'] = self.initialExtra[i-self.initialFormCount()]
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
    validForms = [
        form for form in self.forms \
            if form.isValid() and form not in formsToDelete
        ]
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
        rowData = tuple(
            [
              form.cleanedData[field] for field in uniqueCheck \
                  if field in form.cleanedData
            ]
        )
        if rowData and not None in rowData:
          # if we've already seen it then we have a uniqueness failure
          if rowData in seenData:
            # poke error messages into the right places and mark
            # the form as invalid
            errors.append(self.getUniqueErrorMessage(uniqueCheck))
            form._errors[NON_FIELD_ERRORS] = self.errorClass(
                [self.getFormError()]
                )
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
            form._errors[NON_FIELD_ERRORS] = self.errorClass(
                [self.getFormError()]
                )
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
          "field": getTextList(uniqueCheck, six.text_type(_("and"))),
        }

  def getDateErrorMessage(self, dateCheck):
    return ugettext("Please correct the duplicate data for %(fieldName)s "
      "which must be unique for the %(lookup)s in %(dateField)s.") % {
      'fieldName': dateCheck[2],
      'dateField': dateCheck[3],
      'lookup': six.text_type(dateCheck[1]),
    }

  def getFormError(self):
    return ugettext("Please correct the duplicate values below.")

  def saveExistingObjects(self, commit=True):
    self.changedObjects = []
    self.deletedObjects = []
    if not self.initialForms:
      return []

    savedInstances = []
    formsToDelete = self.deletedForms
    for form in self.initialForms:
      pkName = self._pkField.name
      rawPkValue = form._rawValue(pkName)

      # clean() for different types of PK fields can sometimes return
      # the model instance, and sometimes the PK. Handle either.
      pkValue = form.fields[pkName].clean(rawPkValue)
      pkValue = getattr(pkValue, 'pk', pkValue)

      obj = self._existingObject(pkValue)
      if form in formsToDelete:
        self.deletedObjects.append(obj)
        obj.delete()
        continue
      if form.hasChanged():
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
    from theory.db.models import AutoField, OneToOneField, ForeignKey
    self._pkField = pk = self.model._meta.pk
    # If a pk isn't editable, then it won't be on the form, so we need to
    # add it here so we can tell which object is which when we get the
    # data back. Generally, pk.editable should be false, but for some
    # reason, autoCreated pk fields and AutoField's editable attribute is
    # True, so check for that as well.
    def pkIsNotEditable(pk):
      return \
          (
              (not pk.editable) or (pk.autoCreated or isinstance(pk, AutoField)
          )
          or \
              (
                pk.rel
                and pk.rel.parentLink
                and pkIsNotEditable(pk.rel.to._meta.pk)
              )
          )
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
      form.fields[self._pkField.name] = ModelChoiceField(
          qs,
          initial=pkValue,
          required=False,
          widget=widget
          )
    super(BaseModelFormSet, self).addFields(form, index)

def modelformsetFactory(model, form=ModelForm, formfieldCallback=None,
             formset=BaseModelFormSet, extra=1, canDelete=False,
             canOrder=False, maxNum=None, fields=None, exclude=None,
             widgets=None, validateMax=False, localizedFields=None,
             labels=None, helpTexts=None, errorMessages=None):
  """
  Returns a FormSet class for the given Theory model class.
  """
  # modelformFactory will produce the same warning/error, but that will be
  # difficult to debug for code that needs upgrading, so we produce the
  # warning here too. This logic is reproducing logic inside
  # modelformFactory, but it can be removed once the deprecation cycle is
  # complete, since the validation exception will produce a helpful
  # stacktrace.
  meta = getattr(form, 'Meta', None)
  if meta is None:
    meta = type(str('Meta'), (object,), {})
  if (getattr(meta, 'fields', fields) is None and
    getattr(meta, 'exclude', exclude) is None):
    warnings.warn("Calling modelformsetFactory without defining 'fields' or "
           "'exclude' explicitly is deprecated",
           PendingDeprecationWarning, stacklevel=2)

  form = modelformFactory(model, form=form, fields=fields, exclude=exclude,
               formfieldCallback=formfieldCallback,
               widgets=widgets, localizedFields=localizedFields,
               labels=labels, helpTexts=helpTexts, errorMessages=errorMessages)
  FormSet = formsetFactory(form, formset, extra=extra, maxNum=maxNum,
               canOrder=canOrder, canDelete=canDelete,
               validateMax=validateMax)
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
    if self.instance.pk:
      qs = queryset.filter(**{self.fk.name: self.instance})
    else:
      qs = queryset.none()
    super(BaseInlineFormSet, self).__init__(data, files, prefix=prefix,
                        queryset=qs, **kwargs)

  def initialFormCount(self):
    if self.saveAsNew:
      return 0
    return super(BaseInlineFormSet, self).initialFormCount()


  def _constructForm(self, i, **kwargs):
    form = super(BaseInlineFormSet, self)._constructForm(i, **kwargs)
    if self.saveAsNew:
      # Remove the primary key from the form's data, we are only
      # creating new instances
      form.data[form.addPrefix(self._pkField.name)] = None

      # Remove the foreign key from the form's data
      form.data[form.addPrefix(self.fk.name)] = None

    # Set the fk value here so that the form can do its validation.
    setattr(form.instance, self.fk.getAttname(), self.instance.pk)
    return form

  @classmethod
  def getDefaultPrefix(cls):
    from theory.db.models.fields.related import RelatedObject
    return RelatedObject(
        cls.fk.rel.to,
        cls.model,
        cls.fk
        ).getAccessorName().replace('+','')

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
        'label': getattr(
          form.fields.get(name),
          'label',
          capfirst(self.fk.verboseName)
          )
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
  provided, assume it is the name of the ForeignKey field. Unles canFail is
  True, an exception is raised if there is no ForeignKey from model to
  parentModel.
  """
  # avoid circular import
  from theory.db.models import ForeignKey
  opts = model._meta
  if fkName:
    fksToParent = [f for f in opts.fields if f.name == fkName]
    if len(fksToParent) == 1:
      fk = fksToParent[0]
      if not isinstance(fk, ForeignKey) or \
          (fk.rel.to != parentModel and
           fk.rel.to not in parentModel._meta.getParentList()):
        raise Exception(
            "fkName '%s' is not a ForeignKey to %s" % (fkName, parentModel)
            )
    elif len(fksToParent) == 0:
      raise Exception("%s has no field named '%s'" % (model, fkName))
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
      raise Exception("%s has no ForeignKey to %s" % (model, parentModel))
    else:
      raise Exception(
          "%s has more than 1 ForeignKey to %s" % (model, parentModel)
          )
  return fk


def inlineformsetFactory(parentModel, model, form=ModelForm,
             formset=BaseInlineFormSet, fkName=None,
             fields=None, exclude=None, extra=3, canOrder=False,
             canDelete=True, maxNum=None, formfieldCallback=None,
             widgets=None, validateMax=False, localizedFields=None,
             labels=None, helpTexts=None, errorMessages=None):
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
    'maxNum': maxNum,
    'widgets': widgets,
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
    'invalidChoice': _(
      'The inline foreign key did not match the parent instance primary key.'
      ),
  }

  def __init__(self, parentInstance, *args, **kwargs):
    self.parentInstance = parentInstance
    self.pkField = kwargs.pop("pkField", False)
    self.toField = kwargs.pop("toField", None)
    if self.parentInstance is not None:
      if self.toField:
        kwargs["initial"] = getattr(self.parentInstance, self.toField)
      else:
        kwargs["initial"] = self.parentInstance.pk
    kwargs["required"] = False
    super(InlineForeignKeyField, self).__init__(*args, **kwargs)

  def clean(self, value):
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
      raise ValidationError(
          self.errorMessages['invalidChoice'],
          code='invalidChoice'
          )
    return self.parentInstance

  def _hasChanged(self, initial, data):
    return False

class ModelChoiceIterator(object):
  def __init__(self, field):
    self.field = field
    self.queryset = field.queryset

  def __iter__(self):
    if self.field.emptyLabel is not None:
      yield ("", self.field.emptyLabel)
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
    return len(self.queryset) +\
          (1 if self.field.emptyLabel is not None else 0)

  def choice(self, obj):
    return (self.field.prepareValue(obj), self.field.labelFromInstance(obj))

class ModelChoiceField(ChoiceField):
  """A ChoiceField whose choices are a model QuerySet."""
  # This class is a subclass of ChoiceField for purity, but it doesn't
  # actually use any of ChoiceField's implementation.
  defaultErrorMessages = {
    'invalidChoice': _('Select a valid choice. That choice is not one of'
              ' the available choices.'),
  }

  def __init__(self, queryset, emptyLabel="---------", cacheChoices=False,
         required=True, widget=None, label=None, initial=None,
         helpText='', toFieldName=None, *args, **kwargs):
    if required and (initial is not None):
      self.emptyLabel = None
    else:
      self.emptyLabel = emptyLabel
    self.cacheChoices = cacheChoices

    # Call Field instead of ChoiceField __init__() because we don't need
    # ChoiceField.__init__().
    Field.__init__(self, required, widget, label, initial, helpText,
            *args, **kwargs)
    self.queryset = queryset
    self.choiceCache = None
    self.toFieldName = toFieldName

  def __deepcopy__(self, memo):
    result = super(ChoiceField, self).__deepcopy__(memo)
    # Need to force a new ModelChoiceIterator to be created, bug #11183
    result.queryset = result.queryset
    return result

  def _getQueryset(self):
    return self._queryset

  def _setQueryset(self, queryset):
    self._queryset = queryset
    self.widget.choices = self.choices

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
    try:
      key = self.toFieldName or 'pk'
      value = self.queryset.get(**{key: value})
    except (ValueError, self.queryset.model.DoesNotExist):
      raise ValidationError(
          self.errorMessages['invalidChoice'],
          code='invalidChoice'
          )
    return value

  def validate(self, value):
    return Field.validate(self, value)

  def _hasChanged(self, initial, data):
    initialValue = initial if initial is not None else ''
    dataValue = data if data is not None else ''
    return forceText(self.prepareValue(initialValue)) != forceText(dataValue)

class ModelMultipleChoiceField(ModelChoiceField):
  """A MultipleChoiceField whose choices are a model QuerySet."""
  #widget = SelectMultiple
  #hiddenWidget = MultipleHiddenInput
  defaultErrorMessages = {
    'list': _('Enter a list of values.'),
    'invalidChoice': _('Select a valid choice. %(value)s is not one of the'
              ' available choices.'),
    'invalidPkValue': _('"%(pk)s" is not a valid value for a primary key.')
  }

  def __init__(self, queryset, cacheChoices=False, required=True,
         widget=None, label=None, initial=None,
         helpText='', *args, **kwargs):
    super(ModelMultipleChoiceField, self).__init__(queryset, None,
      cacheChoices, required, widget, label, initial, helpText,
      *args, **kwargs)
    # Remove this in Theory 1.8
    #if isinstance(self.widget, SelectMultiple) and not isinstance(self.widget, CheckboxSelectMultiple):
    #  msg = _('Hold down "Control", or "Command" on a Mac, to select more than one.')
    #  self.helpText = stringConcat(self.helpText, ' ', msg)

  def clean(self, value):
    if self.required and not value:
      raise ValidationError(self.errorMessages['required'], code='required')
    elif not self.required and not value:
      return self.queryset.none()
    if not isinstance(value, (list, tuple)):
      raise ValidationError(self.errorMessages['list'], code='list')
    key = self.toFieldName or 'pk'
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
    pks = set([forceText(getattr(o, key)) for o in qs])
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
        not isinstance(value, six.text_type) and
        not hasattr(value, '_meta')):
      return [
          super(ModelMultipleChoiceField, self).prepareValue(v) for v in value
          ]
    return super(ModelMultipleChoiceField, self).prepareValue(value)

  def _hasChanged(self, initial, data):
    if initial is None:
      initial = []
    if data is None:
      data = []
    if len(initial) != len(data):
      return True
    initialSet = set([forceText(value) for value in self.prepareValue(initial)])
    dataSet = set([forceText(value) for value in data])
    return dataSet != initialSet


def modelformDefinesFields(formClass):
  return (formClass is not None and (
      hasattr(formClass, '_meta') and
      (formClass._meta.fields is not None or
       formClass._meta.exclude is not None)
      ))