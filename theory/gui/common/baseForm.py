# -*- coding: utf-8 -*-
#!/usr/bin/env python
from __future__ import unicode_literals

##### System wide lib #####
from abc import ABCMeta, abstractmethod
from collections import OrderedDict
import copy
import json
import datetime
import warnings

##### Theory lib #####
from theory.core.exceptions import (
    CommandSyntaxError,
    ValidationError,
    NON_FIELD_ERRORS
    )
from theory.gui.common import baseField as FormField
from theory.gui.util import flatatt, ErrorDict, ErrorList
from theory.gui.transformer.theoryJSONEncoder import TheoryJSONEncoder
from theory.utils.deprecation import RemovedInTheory19Warning
from theory.utils.encoding import smartText, forceText, python2UnicodeCompatible
from theory.utils.html import conditionalEscape, formatHtml
from theory.utils.safestring import markSafe
from theory.utils.translation import ugettext as _
from theory.utils import six

##### Theory third-party lib #####

##### Local app #####

##### Theory app #####

##### Misc #####

"""
Form classes
"""

__all__ = ('Form',)


def prettyName(name):
  """Converts 'firstName' to 'First name'"""
  if not name:
    return ''
  return name.replace('_', ' ').capitalize()


def getDeclaredFields(bases, attrs, withBaseFields=True):
  """
  Create a list of form field instances from the passed in 'attrs', plus any
  similar fields on the base classes (in 'bases'). This is used by both the
  Form and ModelForm metaclasses.

  If 'withBaseFields' is True, all fields from the bases are used.
  Otherwise, only fields in the 'declaredFields' attribute on the bases are
  used. The distinction is useful in ModelForm subclassing.
  Also integrates any additional media definitions.
  """

  warnings.warn(
    "getDeclaredFields is deprecated and will be removed in Theory 1.9.",
    RemovedInTheory19Warning,
    stacklevel=2,
  )

  fields = [(fieldName, attrs.pop(fieldName)) for fieldName, obj in list(six.iteritems(attrs)) if isinstance(obj, FormField.Field)]
  fields.sort(key=lambda x: x[1].creationCounter)

  # If this class is subclassing another Form, add that Form's fields.
  # Note that we loop over the bases in *reverse*. This is necessary in
  # order to preserve the correct order of fields.
  if withBaseFields:
    for base in bases[::-1]:
      if hasattr(base, 'baseFields'):
        fields = list(six.iteritems(base.baseFields)) + fields
  else:
    for base in bases[::-1]:
      if hasattr(base, 'declaredFields'):
        fields = list(six.iteritems(base.declaredFields)) + fields

  return OrderedDict(fields)


class DeclarativeFieldsMetaclass(type):
  """
  Metaclass that collects Fields declared on the base classes.
  """
  def __new__(mcs, name, bases, attrs):
    # Collect fields from current class.
    currentFields = []
    for key, value in list(attrs.items()):
      if isinstance(value, FormField.Field):
        currentFields.append((key, value))
        attrs.pop(key)
    currentFields.sort(key=lambda x: x[1].creationCounter)
    attrs['declaredFields'] = OrderedDict(currentFields)

    newClass = (super(DeclarativeFieldsMetaclass, mcs)
      .__new__(mcs, name, bases, attrs))

    # Walk through the MRO.
    declaredFields = OrderedDict()
    for base in reversed(newClass.__mro__):
      # Collect fields from base class.
      if hasattr(base, 'declaredFields'):
        declaredFields.update(base.declaredFields)

      # Field shadowing.
      for attr, value in base.__dict__.items():
        if value is None and attr in declaredFields:
          declaredFields.pop(attr)

    newClass.baseFields = declaredFields
    newClass.declaredFields = declaredFields

    return newClass


@python2UnicodeCompatible
class FormBase(object):
  # This is the main implementation of all the Form logic. Note that this
  # class is different than Form. See the comments by the Form class for more
  # information. Any improvements to the form API should be made to *this*
  # class, not to the Form class.

  # True is assuming connection is expensive and hence field will connect with
  # widget as least as possible. Ex: if an error has been detected and the
  # fullClean() has been called. The lazy mode will only update the error field
  # while the not lazy mode will update every field.
  isLazy = True
  def __init__(
      self,
      initData=None,
      autoId='id_%s',
      errorClass=ErrorList,
      emptyPermitted=False
      ):

    self.isBound = True
    self.errorClass = errorClass
    # Translators: This is the default suffix added to form field labels
    self.emptyPermitted = emptyPermitted
    self._errors = None  # Stores the errors after clean() has been called.
    self._changedData = None
    self.jsonData = None
    self.initData = initData or {}
    self.emptyForgivenLst = []

    # The baseFields class attribute is the *class-wide* definition of
    # fields. Because a particular *instance* of the class might want to
    # alter self.fields, we create self.fields here by copying baseFields.
    # Instances should always modify self.fields; they should not modify
    # self.baseFields.
    super(FormBase, self).__init__()
    self.fields = copy.deepcopy(self.baseFields)

  def __str__(self):
    return self.__class__.__name__

  def __iter__(self):
    for name in self.fields:
      yield self[name]

  def __getitem__(self, name):
    "Returns a BoundField with the given name."
    try:
      field = self.fields[name]
    except KeyError:
      raise KeyError(
        "Key %r not found in '%s'" % (name, self.__class__.__name__))
    return BoundField(self, field, name)

  @property
  def errors(self):
    "Returns an ErrorDict for the data provided for the form"
    if self._errors is None:
      self.fullClean()
    return self._errors

  def isValid(self):
    """
    Returns True if the form has no errors. Otherwise, False. If errors are
    being ignored, returns False.
    """
    return self.isBound and not self.errors

  def addPrefix(self, fieldName):
    """
    Returns the field name with a prefix appended, if this Form has a
    prefix set.

    Subclasses may wish to override.
    """
    return '%s-%s' % (self.prefix, fieldName) if self.prefix else fieldName

  def addInitialPrefix(self, fieldName):
    """
    Add a 'initial' prefix for checking dynamic initial values
    """
    return 'initial-%s' % self.addPrefix(fieldName)

  def nonFieldErrors(self):
    """
    Returns an ErrorList of errors that aren't associated with a particular
    field -- i.e., from Form.clean(). Returns an empty ErrorList if there
    are none.
    """
    return self.errors.get(NON_FIELD_ERRORS, self.errorClass(errorClass='nonfield'))

  def _rawValue(self, fieldname):
    """
    Returns the rawValue for a particular field name. This is just a
    convenient wrapper around widget.valueFromDatadict.
    """
    field = self.fields[fieldname]
    prefix = self.addPrefix(fieldname)
    return field.widget.valueFromDatadict(self.data, self.files, prefix)

  def addError(self, field, error):
    """
    Update the content of `self._errors`.

    The `field` argument is the name of the field to which the errors
    should be added. If its value is None the errors will be treated as
    NON_FIELD_ERRORS.

    The `error` argument can be a single error, a list of errors, or a
    dictionary that maps field names to lists of errors. What we define as
    an "error" can be either a simple string or an instance of
    ValidationError with its message attribute set and what we define as
    list or dictionary can be an actual `list` or `dict` or an instance
    of ValidationError with its `errorList` or `errorDict` attribute set.

    If `error` is a dictionary, the `field` argument *must* be None and
    errors will be added to the fields that correspond to the keys of the
    dictionary.
    """
    if not isinstance(error, ValidationError):
      # Normalize to ValidationError and let its constructor
      # do the hard work of making sense of the input.
      error = ValidationError(error)

    if hasattr(error, 'errorDict'):
      if field is not None:
        raise TypeError(
          "The argument `field` must be `None` when the `error` "
          "argument contains errors for multiple fields."
        )
      else:
        error = error.errorDict
    else:
      error = {field or NON_FIELD_ERRORS: error.errorList}

    for field, errorList in error.items():
      if field not in self.errors:
        if field != NON_FIELD_ERRORS and field not in self.fields:
          raise ValueError(
            "'%s' has no field named '%s'." % (self.__class__.__name__, field))
        if field == NON_FIELD_ERRORS:
          self._errors[field] = self.errorClass(errorClass='nonfield')
        else:
          self._errors[field] = self.errorClass()
      self._errors[field].extend(errorList)
      if field in self.cleanedData:
        del self.cleanedData[field]

  def hasError(self, field, code=None):
    if code is None:
      return field in self.errors
    if field in self.errors:
      for error in self.errors.asData()[field]:
        if error.code == code:
          return True
    return False

  def _validateNonSingularField(self):
    pass

  def fullClean(self):
    """
    Cleans all of self.data and populates self._errors and
    self.cleanedData.
    """
    self._errors = {}
    self.jsonData = None
    #!!!!!!!! Do we want errors transparent or add one more layer
    #self._errors = ErrorDict()
    if not self.isBound: # Stop further processing.
      return
    self.cleanedData = {}
    # If the form is permitted to be empty, and none of the form data has
    # changed from the initial data, short circuit any validation.
    if self.emptyPermitted and not self.hasChanged():
      return

    self._validateNonSingularField()
    self._cleanFields()
    self._cleanForm()
    self._postClean()

  def _cleanFields(self):
    for name, field in self.fields.items():
      # valueFromDatadict() gets the data from the data dictionaries.
      # Each widget type knows how to retrieve its own data, because some
      # widgets split data over several HTML fields.

      # The forceUpdate is for clearing the invalid data stored in the last
      # round and force update the field finalData either from widget or
      # initData
      if(not self.isLazy):
        field.forceUpdate()
      value = field.finalData
      #value = field.widget.valueFromDatadict(self.data, self.files, self.addPrefix(name))
      try:
        isEmptyForgiven = True if name in self.emptyForgivenLst else False
        if isinstance(field, FormField.FileField):
          initData = self.initData.get(name, field.initData)
          value = field.clean(value, initData, isEmptyForgiven)
        else:
          value = field.clean(value, isEmptyForgiven)
        self.cleanedData[name] = value
        if hasattr(self, 'clean_%s' % name):
          value = getattr(self, 'clean_%s' % name)()
          self.cleanedData[name] = value
      except ValidationError as e:
        if(self.isLazy):
          field.finalData = None
        self.addError(name, e)
        if name in self.cleanedData:
          del self.cleanedData[name]

  def _cleanForm(self):
    try:
      cleanedData = self.clean()
    except ValidationError as e:
      self.addError(None, e)
    else:
      if cleanedData is not None:
        self.cleanedData = cleanedData

  def _postClean(self):
    """
    An internal hook for performing additional cleaning after form cleaning
    is complete. Used for model validation in model forms.
    """
    pass

  def clean(self):
    """
    Hook for doing any extra form-wide cleaning after Field.clean() been
    called on every field. Any ValidationError raised by this method will
    not be associated with a particular field; it will have a special-case
    association with the field named '__all__'.
    """
    return self.cleanedData

  def hasChanged(self):
    """
    Returns True if data differs from initial.
    """
    return bool(self.changedData)

  @property
  def changedData(self):
    if self._changedData is None:
      self._changedData = []
      # XXX: For now we're asking the individual widgets whether or not the
      # data has changed. It would probably be more efficient to hash the
      # initial data, store it in a hidden field, and compare a hash of the
      # submitted data, but we'd need a way to easily get the string value
      # for a given field. Right now, that logic is embedded in the render
      # method of each widget.
      for name, field in self.fields.items():
        prefixedName = self.addPrefix(name)
        dataValue = field.widget.valueFromDatadict(self.data, self.files, prefixedName)
        if not field.showHiddenInitial:
          initialValue = self.initData.get(name, field.initData)
          if callable(initialValue):
            initialValue = initialValue()
        else:
          initialPrefixedName = self.addInitialPrefix(name)
          hiddenWidget = field.hiddenWidget()
          try:
            initialValue = field.toPython(hiddenWidget.valueFromDatadict(
              self.data, self.files, initialPrefixedName))
          except ValidationError:
            # Always assume data has changed if validation fails.
            self._changedData.append(name)
            continue
        if field._hasChanged(initialValue, dataValue):
          self._changedData.append(name)
    return self._changedData

  def _chainGetattr(self, o, path):
    r = o
    for tok in path:
      try:
        r = getattr(r, tok)
      except AttributeError:
        try:
          r = r[tok]
        except KeyError as e:
          raise e
      except Exception as e:
        raise e
    return r

  def syncFormDataWithUi(self, fieldName, uiPropagate):
    for path in uiPropagate:
      prop = self._chainGetattr(self, path[:-1])
      # To avoid lazy update
      self.fields[fieldName].forceUpdate()
      setattr(prop, path[-1], self.fields[fieldName].finalData)

  def fillInitFields(self, cmdModel, args, kwargs):
    # Not being called in Gui's form
    if cmdModel is not None:
      cmdArgs = [i for i in cmdModel.cmdFieldSet.all() if(not i.isOptional)]
      if args!=[]:
        for i in range(len(cmdArgs)):
          try:
            self.fields[cmdArgs[i].name].initData = args[i]

            self.syncFormDataWithUi(
              cmdArgs[i].name,
              self.fields[cmdArgs[i].name].uiPropagate,
            )
          except IndexError as e:
            # This means the number of param given unmatch the number of param
            # register in *.command
            raise CommandSyntaxError(str(e))
    for k,v in kwargs.items():
      self.fields[k].initData = v
      self.syncFormDataWithUi(
        k,
        self.fields[k].uiPropagate,
      )

  def fillFinalFields(self, cmdModel, args, kwargs):
    # Not being called in Gui's form
    if cmdModel is not None:
      cmdArgs = [i for i in cmdModel.cmdFieldSet.all() if(not i.isOptional)]
      if args!=[]:
        for i in range(len(cmdArgs)):
          try:
            self.fields[cmdArgs[i].name].finalData = args[i]

            self.syncFormDataWithUi(
              cmdArgs[i].name,
              self.fields[cmdArgs[i].name].uiPropagate,
            )
          except IndexError as e:
            # This means the number of param given unmatch the number of param
            # register in *.command
            raise CommandSyntaxError(str(e))
    for k,v in kwargs.items():
      self.fields[k].finalData = v
      self.syncFormDataWithUi(
        k,
        self.fields[k].uiPropagate,
      )

  def toPython(self):
    if self.isValid():
      pythonDict = {}
      for fieldName, field in self.fields.items():
        try:
          pythonDict[fieldName] = field.toPython(field.clean(field.finalData))
        except Exception as e:
          raise ValidationError(str(e))

      return pythonDict

  def toJson(self):
    if self.isValid():
      if(self.jsonData is None):
        encoderKwargs = {"cls": TheoryJSONEncoder}
        pythonDict = self.toPython()
        try:
          self.jsonData = json.dumps(pythonDict, **encoderKwargs)
        except Exception as e: # eval can throw many different errors
          raise ValidationError(str(e))
      return self.jsonData

  def toModelForm(self):
    if self.isValid():
      pythonDict = {}
      # Never cache model form data
      for fieldName, field in self.fields.items():
        # Make sure not getting data from widget because the widget may be
        # destroied
        tmpWidget = field.widget
        field.widget = field.widget.__class__

        try:
          if type(field).__name__ in [
              "ModelChoiceField",
              "ModelMultipleChoiceField"
              ]:
            pythonDict[fieldName + field.getModelFieldNameSuffix()] \
                = field.prepareValue(field.finalData)
          else:
            pythonDict[fieldName + field.getModelFieldNameSuffix()] \
                = field.toPython(field.clean(field.finalData))
        except Exception as e: # eval can throw many different errors
          raise ValidationError(fieldName + ": " + str(e))

      encoderKwargs = {"cls": TheoryJSONEncoder}
      try:
        return json.dumps(pythonDict, **encoderKwargs)
      except Exception as e: # eval can throw many different errors
        import logging
        logger = logging.getLogger(__name__)
        logger.error(e, exc_info=True)
        raise ValidationError(str(e))

  def exportToHistory(self):
    data = self.toPython()
    r = {}
    for fieldName, field in self.fields.items():
      if field.isSkipInHistory:
        continue
      r[fieldName] = data[fieldName]
    try:
      return json.dumps(r, cls=TheoryJSONEncoder)
    except Exception as e: # eval can throw many different errors
      import logging
      logger = logging.getLogger(__name__)
      logger.error(e, exc_info=True)
      raise ValidationError(str(e))

class Form(six.withMetaclass(DeclarativeFieldsMetaclass, FormBase)):
  """A collection of Fields, plus their associated data."""
  # This is a separate class from BaseForm in order to abstract the way
  # self.fields is specified. This class (Form) is the one that does the
  # fancy metaclass stuff purely for the semantic sugar -- it allows one
  # to define a form using declarative syntax.
  # BaseForm itself has no way of designating self.fields.


@python2UnicodeCompatible
class BoundField(object):
  "A Field plus data"
  def __init__(self, form, field, name):
    self.form = form
    self.field = field
    self.name = name
    self.htmlName = form.addPrefix(name)
    self.htmlInitialName = form.addInitialPrefix(name)
    self.htmlInitialId = form.addInitialPrefix(self.autoId)
    if self.field.label is None:
      self.label = prettyName(name)
    else:
      self.label = self.field.label
    self.helpText = field.helpText or ''

  def __str__(self):
    """Renders this field as an HTML widget."""
    if self.field.showHiddenInitial:
      return self.asWidget() + self.asHidden(onlyInitial=True)
    return self.asWidget()

  def __iter__(self):
    """
    Yields rendered strings that comprise all widgets in this BoundField.

    This really is only useful for RadioSelect widgets, so that you can
    iterate over individual radio buttons in a template.
    """
    id_ = self.field.widget.attrs.get('id') or self.autoId
    attrs = {'id': id_} if id_ else {}
    for subwidget in self.field.widget.subwidgets(self.htmlName, self.value(), attrs):
      yield subwidget

  def __len__(self):
    return len(list(self.__iter__()))

  def __getitem__(self, idx):
    return list(self.__iter__())[idx]

  @property
  def errors(self):
    """
    Returns an ErrorList for this field. Returns an empty ErrorList
    if there are none.
    """
    return self.form.errors.get(self.name, self.form.errorClass())

  @property
  def data(self):
    """
    Returns the data for this BoundField, or None if it wasn't given.
    """
    return self.field.widget.valueFromDatadict(self.form.data, self.form.files, self.htmlName)

  def value(self):
    """
    Returns the value for this BoundField, using the initial value if
    the form is not bound or the data otherwise.
    """
    if not self.form.isBound:
      data = self.form.initial.get(self.name, self.field.initial)
      if callable(data):
        data = data()
        # If this is an auto-generated default date, nix the
        # microseconds for standardized handling. See #22502.
        if (isinstance(data, (datetime.datetime, datetime.time)) and
            not getattr(self.field.widget, 'supportsMicroseconds', True)):
          data = data.replace(microsecond=0)
    else:
      data = self.field.boundData(
        self.data, self.form.initial.get(self.name, self.field.initial)
      )
    return self.field.prepareValue(data)

  @property
  def autoId(self):
    """
    Calculates and returns the ID attribute for this BoundField, if the
    associated Form has specified autoId. Returns an empty string otherwise.
    """
    autoId = self.form.autoId
    if autoId and '%s' in smartText(autoId):
      return smartText(autoId) % self.htmlName
    elif autoId:
      return self.htmlName
    return ''
