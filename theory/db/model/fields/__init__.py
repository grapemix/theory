# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import collections
import copy
import datetime
import decimal
import math
import warnings
from base64 import b64decode, b64encode
from itertools import tee

from theory.apps import apps
from theory.db import connection
from theory.db.model.lookups import defaultLookups, RegisterLookupMixin
from theory.db.model.queryUtils import QueryWrapper
from theory.conf import settings
from theory.gui.common import baseField as field
from theory.core import exceptions, validators, checks
from theory.utils.datastructures import DictWrapper
from theory.utils.dateparse import parseDate, parseDatetime, parseTime
from theory.utils.deprecation import RemovedInTheory19Warning
from theory.utils.functional import cachedProperty, curry, totalOrdering, Promise
from theory.utils.text import capfirst
from theory.utils import timezone
from theory.utils.translation import ugettextLazy as _
from theory.utils.encoding import (smartText, forceText, forceBytes,
  python2UnicodeCompatible)
from theory.utils.ipv6 import cleanIpv6Address
from theory.utils import six
from theory.utils.itercompat import isIterable

# Avoid "TypeError: Item in ``from list'' not a string" -- unicode_literals
# makes these strings unicode
__all__ = [str(x) for x in (
  'AutoField', 'BLANK_CHOICE_DASH', 'BigIntegerField', 'BinaryField',
  'BooleanField', 'CharField', 'CommaSeparatedIntegerField', 'DateField',
  'DateTimeField', 'DecimalField', 'EmailField', 'Empty', 'Field',
  'FieldDoesNotExist', 'FilePathField', 'FloatField',
  'GenericIPAddressField', 'IPAddressField', 'IntegerField', 'NOT_PROVIDED',
  'NullBooleanField', 'PositiveIntegerField', 'PositiveSmallIntegerField',
  'SlugField', 'SmallIntegerField', 'TextField', 'TimeField', 'URLField',
)]


class Empty(object):
  pass


class NOT_PROVIDED:
  pass

# The values to use for "blank" in SelectFields. Will be appended to the start
# of most "choices" lists.
BLANK_CHOICE_DASH = [("", "---------")]


def _loadField(appLabel, modelName, fieldName):
  return apps.getModel(appLabel, modelName)._meta.getFieldByName(fieldName)[0]


class FieldDoesNotExist(Exception):
  pass


# A guide to Field parameters:
#
#   * name:      The name of the field specified in the modal.
#   * attname:   The attribute to use on the modal object. This is the same as
#                "name", except in the case of ForeignKeys, where "_id" is
#                appended.
#   * dbColumn: The dbColumn specified in the modal (or None).
#   * column:    The database column for this field. This is the same as
#                "attname", except if dbColumn is specified.
#
# Code that introspects values, or does other dynamic things, should use
# attname. For example, this gets the primary key value of object "obj":
#
#     getattr(obj, opts.pk.attname)

def _empty(ofCls):
  new = Empty()
  new.__class__ = ofCls
  return new


@totalOrdering
@python2UnicodeCompatible
class Field(RegisterLookupMixin):
  """Base class for all field types"""

  # Designates whether empty strings fundamentally are allowed at the
  # database level.
  emptyStringsAllowed = True
  emptyValues = list(validators.EMPTY_VALUES)

  # These track each time a Field instance is created. Used to retain order.
  # The autoCreationCounter is used for fields that Theory implicitly
  # creates, creationCounter is used for all user-specified fields.
  creationCounter = 0
  autoCreationCounter = -1
  defaultValidators = []  # Default set of validators
  defaultErrorMessages = {
    'invalidChoice': _('Value %(value)r is not a valid choice.'),
    'null': _('This field cannot be null.'),
    'blank': _('This field cannot be blank.'),
    'unique': _('%(modelName)s with this %(fieldLabel)s '
          'already exists.'),
    # Translators: The 'lookupType' is one of 'date', 'year' or 'month'.
    # Eg: "Title must be unique for pubDate year"
    'uniqueForDate': _("%(fieldLabel)s must be unique for "
               "%(dateFieldLabel)s %(lookupType)s."),
  }
  classLookups = defaultLookups.copy()

  # Generic field type description, usually overridden by subclasses
  def _description(self):
    return _('Field of type: %(fieldType)s') % {
      'fieldType': self.__class__.__name__
    }
  description = property(_description)

  def __init__(self, verboseName=None, name=None, primaryKey=False,
      maxLength=None, unique=False, blank=False, null=False,
      dbIndex=False, rel=None, default=NOT_PROVIDED, editable=True,
      serialize=True, uniqueForDate=None, uniqueForMonth=None,
      uniqueForYear=None, choices=None, helpText='', dbColumn=None,
      dbTablespace=None, autoCreated=False, validators=[],
      errorMessages=None):
    self.name = name
    self.verboseName = verboseName  # May be set by setAttributesFromName
    self._verboseName = verboseName  # Store original for deconstruction
    self.primaryKey = primaryKey
    self.maxLength, self._unique = maxLength, unique
    self.blank, self.null = blank, null
    self.rel = rel
    self.default = default
    self.editable = editable
    self.serialize = serialize
    self.uniqueForDate = uniqueForDate
    self.uniqueForMonth = uniqueForMonth
    self.uniqueForYear = uniqueForYear
    self._choices = choices or []
    self.helpText = helpText
    self.dbColumn = dbColumn
    self.dbTablespace = dbTablespace or settings.DEFAULT_INDEX_TABLESPACE
    self.autoCreated = autoCreated

    # Set dbIndex to True if the field has a relationship and doesn't
    # explicitly set dbIndex.
    self.dbIndex = dbIndex

    # Adjust the appropriate creation counter, and save our local copy.
    if autoCreated:
      self.creationCounter = Field.autoCreationCounter
      Field.autoCreationCounter -= 1
    else:
      self.creationCounter = Field.creationCounter
      Field.creationCounter += 1

    self._validators = validators  # Store for deconstruction later

    messages = {}
    for c in reversed(self.__class__.__mro__):
      messages.update(getattr(c, 'defaultErrorMessages', {}))
    messages.update(errorMessages or {})
    self._errorMessages = errorMessages  # Store for deconstruction later
    self.errorMessages = messages

  def __str__(self):
    """ Return "appLabel.modalLabel.fieldName". """
    modal = self.modal
    app = modal._meta.appLabel
    return '%s.%s.%s' % (app, modal._meta.objectName, self.name)

  def __repr__(self):
    """
    Displays the module, class and name of the field.
    """
    path = '%s.%s' % (self.__class__.__module__, self.__class__.__name__)
    name = getattr(self, 'name', None)
    if name is not None:
      return '<%s: %s>' % (path, name)
    return '<%s>' % path

  def check(self, **kwargs):
    errors = []
    errors.extend(self._checkFieldName())
    errors.extend(self._checkChoices())
    errors.extend(self._checkDbIndex())
    errors.extend(self._checkNullAllowedForPrimaryKeys())
    errors.extend(self._checkBackendSpecificChecks(**kwargs))
    return errors

  def _checkFieldName(self):
    """ Check if field name is valid, i.e. 1) does not end with an
    underscore, 2) does not contain "__" and 3) is not "pk". """

    if self.name.endswith('_'):
      return [
        checks.Error(
          'Field names must not end with an underscore.',
          hint=None,
          obj=self,
          id='fields.E001',
        )
      ]
    elif '__' in self.name:
      return [
        checks.Error(
          'Field names must not contain "__".',
          hint=None,
          obj=self,
          id='fields.E002',
        )
      ]
    elif self.name == 'pk':
      return [
        checks.Error(
          "'pk' is a reserved word that cannot be used as a field name.",
          hint=None,
          obj=self,
          id='fields.E003',
        )
      ]
    else:
      return []

  def _checkChoices(self):
    if self.choices:
      if (isinstance(self.choices, six.stringTypes) or
          not isIterable(self.choices)):
        return [
          checks.Error(
            "'choices' must be an iterable (e.g., a list or tuple).",
            hint=None,
            obj=self,
            id='fields.E004',
          )
        ]
      elif any(isinstance(choice, six.stringTypes) or
           not isIterable(choice) or len(choice) != 2
           for choice in self.choices):
        return [
          checks.Error(
            ("'choices' must be an iterable containing "
             "(actual value, human readable name) tuples."),
            hint=None,
            obj=self,
            id='fields.E005',
          )
        ]
      else:
        return []
    else:
      return []

  def _checkDbIndex(self):
    if self.dbIndex not in (None, True, False):
      return [
        checks.Error(
          "'dbIndex' must be None, True or False.",
          hint=None,
          obj=self,
          id='fields.E006',
        )
      ]
    else:
      return []

  def _checkNullAllowedForPrimaryKeys(self):
    if (self.primaryKey and self.null and
        not connection.features.interpretsEmptyStringsAsNulls):
      # We cannot reliably check this for backends like Oracle which
      # consider NULL and '' to be equal (and thus set up
      # character-based fields a little differently).
      return [
        checks.Error(
          'Primary keys must not have null=True.',
          hint=('Set null=False on the field, or '
             'remove primaryKey=True argument.'),
          obj=self,
          id='fields.E007',
        )
      ]
    else:
      return []

  def _checkBackendSpecificChecks(self, **kwargs):
    return connection.validation.checkField(self, **kwargs)

  def deconstruct(self):
    """
    Returns enough information to recreate the field as a 4-tuple:

     * The name of the field on the modal, if contributeToClass has been run
     * The import path of the field, including the class: theory.db.model.IntegerField
      This should be the most portable version, so less specific may be better.
     * A list of positional arguments
     * A dict of keyword arguments

    Note that the positional or keyword arguments must contain values of the
    following types (including inner values of collection types):

     * None, bool, str, unicode, int, long, float, complex, set, frozenset, list, tuple, dict
     * UUID
     * datetime.datetime (naive), datetime.date
     * top-level classes, top-level functions - will be referenced by their full import path
     * Storage instances - these have their own deconstruct() method

    This is because the values here must be serialized into a text format
    (possibly new Python code, possibly JSON) and these are the only types
    with encoding handlers defined.

    There's no need to return the exact way the field was instantiated this time,
    just ensure that the resulting field is the same - prefer keyword arguments
    over positional ones, and omit parameters with their default values.
    """
    # Short-form way of fetching all the default parameters
    keywords = {}
    possibles = {
      "verboseName": None,
      "primaryKey": False,
      "maxLength": None,
      "unique": False,
      "blank": False,
      "null": False,
      "dbIndex": False,
      "default": NOT_PROVIDED,
      "editable": True,
      "serialize": True,
      "uniqueForDate": None,
      "uniqueForMonth": None,
      "uniqueForYear": None,
      "choices": [],
      "helpText": '',
      "dbColumn": None,
      "dbTablespace": settings.DEFAULT_INDEX_TABLESPACE,
      "autoCreated": False,
      "validators": [],
      "errorMessages": None,
    }
    attrOverrides = {
      "unique": "_unique",
      "choices": "_choices",
      "errorMessages": "_errorMessages",
      "validators": "_validators",
      "verboseName": "_verboseName",
    }
    equalsComparison = set(["choices", "validators", "dbTablespace"])
    for name, default in possibles.items():
      value = getattr(self, attrOverrides.get(name, name))
      # Unroll anything iterable for choices into a concrete list
      if name == "choices" and isinstance(value, collections.Iterable):
        value = list(value)
      # Do correct kind of comparison
      if name in equalsComparison:
        if value != default:
          keywords[name] = value
      else:
        if value is not default:
          keywords[name] = value
    # Work out path - we shorten it for known Theory core fields
    path = "%s.%s" % (self.__class__.__module__, self.__class__.__name__)
    if path.startswith("theory.db.model.fields.related"):
      path = path.replace("theory.db.model.fields.related", "theory.db.model")
    if path.startswith("theory.db.model.fields.files"):
      path = path.replace("theory.db.model.fields.files", "theory.db.model")
    if path.startswith("theory.db.model.fields.proxy"):
      path = path.replace("theory.db.model.fields.proxy", "theory.db.model")
    if path.startswith("theory.db.model.fields"):
      path = path.replace("theory.db.model.fields", "theory.db.model")
    # Return basic info - other fields should override this.
    return (
      forceText(self.name, stringsOnly=True),
      path,
      [],
      keywords,
    )

  def clone(self):
    """
    Uses deconstruct() to clone a new copy of this Field.
    Will not preserve any class attachments/attribute names.
    """
    name, path, args, kwargs = self.deconstruct()
    return self.__class__(*args, **kwargs)

  def __eq__(self, other):
    # Needed for @totalOrdering
    if isinstance(other, Field):
      return self.creationCounter == other.creationCounter
    return NotImplemented

  def __lt__(self, other):
    # This is needed because bisect does not take a comparison function.
    if isinstance(other, Field):
      return self.creationCounter < other.creationCounter
    return NotImplemented

  def __hash__(self):
    return hash(self.creationCounter)

  def __deepcopy__(self, memodict):
    # We don't have to deepcopy very much here, since most things are not
    # intended to be altered after initData creation.
    obj = copy.copy(self)
    if self.rel:
      obj.rel = copy.copy(self.rel)
      if hasattr(self.rel, 'field') and self.rel.field is self:
        obj.rel.field = obj
    memodict[id(self)] = obj
    return obj

  def __copy__(self):
    # We need to avoid hitting __reduce__, so define this
    # slightly weird copy construct.
    obj = Empty()
    obj.__class__ = self.__class__
    obj.__dict__ = self.__dict__.copy()
    return obj

  def __reduce__(self):
    """
    Pickling should return the modal._meta.fields instance of the field,
    not a new copy of that field. So, we use the app registry to load the
    modal and then the field back.
    """
    if not hasattr(self, 'modal'):
      # Fields are sometimes used without attaching them to model (for
      # example in aggregation). In this case give back a plain field
      # instance. The code below will create a new empty instance of
      # class self.__class__, then update its dict with self.__dict__
      # values - so, this is very close to normal pickle.
      return _empty, (self.__class__,), self.__dict__
    if self.modal._deferred:
      # Deferred modal will not be found from the app registry. This
      # could be fixed by reconstructing the deferred modal on unpickle.
      raise RuntimeError("Fields of deferred model can't be reduced")
    return _loadField, (self.modal._meta.appLabel, self.modal._meta.objectName,
               self.name)

  def toPython(self, value):
    """
    Converts the input value into the expected Python data type, raising
    theory.core.exceptions.ValidationError if the data can't be converted.
    Returns the converted value. Subclasses should override this.
    """
    return value

  @cachedProperty
  def validators(self):
    # Some validators can't be created at field initialization time.
    # This method provides a way to delay their creation until required.
    return self.defaultValidators + self._validators

  def runValidators(self, value):
    if value in self.emptyValues:
      return

    errors = []
    for v in self.validators:
      try:
        v(value)
      except exceptions.ValidationError as e:
        if hasattr(e, 'code') and e.code in self.errorMessages:
          e.message = self.errorMessages[e.code]
        errors.extend(e.errorList)

    if errors:
      raise exceptions.ValidationError(errors)

  def validate(self, value, modalInstance):
    """
    Validates value and throws ValidationError. Subclasses should override
    this to provide validation logic.
    """
    if not self.editable:
      # Skip validation for non-editable fields.
      return

    if self._choices and value not in self.emptyValues:
      for optionKey, optionValue in self.choices:
        if isinstance(optionValue, (list, tuple)):
          # This is an optgroup, so look inside the group for
          # options.
          for optgroupKey, optgroupValue in optionValue:
            if value == optgroupKey:
              return
        elif value == optionKey:
          return
      raise exceptions.ValidationError(
        self.errorMessages['invalidChoice'],
        code='invalidChoice',
        params={'value': value},
      )

    if value is None and not self.null:
      raise exceptions.ValidationError(self.errorMessages['null'], code='null')

    if not self.blank and value in self.emptyValues:
      raise exceptions.ValidationError(self.errorMessages['blank'], code='blank')

  def clean(self, value, modalInstance):
    """
    Convert the value's type and run validation. Validation errors
    from toPython and validate are propagated. The correct value is
    returned if no error is raised.
    """
    value = self.toPython(value)
    self.validate(value, modalInstance)
    self.runValidators(value)
    return value

  def dbType(self, connection):
    """
    Returns the database column data type for this field, for the provided
    connection.
    """
    # The default implementation of this method looks at the
    # backend-specific dataTypes dictionary, looking up the field by its
    # "internal type".
    #
    # A Field class can implement the getInternalType() method to specify
    # which *preexisting* Theory Field class it's most similar to -- i.e.,
    # a custom field might be represented by a TEXT column type, which is
    # the same as the TextField Theory field type, which means the custom
    # field's getInternalType() returns 'TextField'.
    #
    # But the limitation of the getInternalType() / dataTypes approach
    # is that it cannot handle database column types that aren't already
    # mapped to one of the built-in Theory field types. In this case, you
    # can implement dbType() instead of getInternalType() to specify
    # exactly which wacky database column type you want to use.
    data = DictWrapper(self.__dict__, connection.ops.quoteName, "qn_")
    try:
      return connection.creation.dataTypes[self.getInternalType()] % data
    except KeyError:
      return None

  def dbParameters(self, connection):
    """
    Extension of dbType(), providing a range of different return
    values (type, checks).
    This will look at dbType(), allowing custom modal fields to override it.
    """
    data = DictWrapper(self.__dict__, connection.ops.quoteName, "qn_")
    typeString = self.dbType(connection)
    try:
      checkString = connection.creation.dataTypeCheckConstraints[self.getInternalType()] % data
    except KeyError:
      checkString = None
    return {
      "type": typeString,
      "check": checkString,
    }

  def dbTypeSuffix(self, connection):
    return connection.creation.dataTypesSuffix.get(self.getInternalType())

  @property
  def unique(self):
    return self._unique or self.primaryKey

  def setAttributesFromName(self, name):
    if not self.name:
      self.name = name
    self.attname, self.column = self.getAttnameColumn()
    if self.verboseName is None and self.name:
      self.verboseName = self.name.replace('_', ' ')

  def contributeToClass(self, cls, name, virtualOnly=False):
    self.setAttributesFromName(name)
    self.modal = cls
    if virtualOnly:
      cls._meta.addVirtualField(self)
    else:
      cls._meta.addField(self)
    if self.choices:
      setattr(cls, 'get_%sDisplay' % self.name,
          curry(cls._get_FIELD_display, field=self))

  def getAttname(self):
    return self.name

  def getAttnameColumn(self):
    attname = self.getAttname()
    column = self.dbColumn or attname
    return attname, column

  def getCacheName(self):
    return '_%sCache' % self.name

  def getInternalType(self):
    return self.__class__.__name__

  def preSave(self, modalInstance, add):
    """
    Returns field's value just before saving.
    """
    return getattr(modalInstance, self.attname)

  def getPrepValue(self, value):
    """
    Perform preliminary non-db specific value checks and conversions.
    """
    if isinstance(value, Promise):
      value = value._proxy____cast()
    return value

  def getDbPrepValue(self, value, connection, prepared=False):
    """Returns field's value prepared for interacting with the database
    backend.

    Used by the default implementations of ``getDbPrepSave``and
    `getDbPrepLookup```
    """
    if not prepared:
      value = self.getPrepValue(value)
    return value

  def getDbPrepSave(self, value, connection):
    """
    Returns field's value prepared for saving into a database.
    """
    return self.getDbPrepValue(value, connection=connection,
                   prepared=False)

  def getPrepLookup(self, lookupType, value):
    """
    Perform preliminary non-db specific lookup checks and conversions
    """
    if hasattr(value, 'prepare'):
      return value.prepare()
    if hasattr(value, '_prepare'):
      return value._prepare()

    if lookupType in {
      'iexact', 'contains', 'icontains',
      'startswith', 'istartswith', 'endswith', 'iendswith',
      'month', 'day', 'weekDay', 'hour', 'minute', 'second',
      'isnull', 'search', 'regex', 'iregex',
    }:
      return value
    elif lookupType in ('exact', 'gt', 'gte', 'lt', 'lte'):
      return self.getPrepValue(value)
    elif lookupType in ('range', 'in'):
      return [self.getPrepValue(v) for v in value]
    elif lookupType == 'year':
      try:
        return int(value)
      except ValueError:
        raise ValueError("The __year lookup type requires an integer "
                 "argument")
    return self.getPrepValue(value)

  def getDbPrepLookup(self, lookupType, value, connection,
              prepared=False):
    """
    Returns field's value prepared for database lookup.
    """
    if not prepared:
      value = self.getPrepLookup(lookupType, value)
      prepared = True
    if hasattr(value, 'getCompiler'):
      value = value.getCompiler(connection=connection)
    if hasattr(value, 'asSql') or hasattr(value, '_asSql'):
      # If the value has a relabeledClone method it means the
      # value will be handled later on.
      if hasattr(value, 'relabeledClone'):
        return value
      if hasattr(value, 'asSql'):
        sql, params = value.asSql()
      else:
        sql, params = value._asSql(connection=connection)
      return QueryWrapper(('(%s)' % sql), params)

    if lookupType in ('month', 'day', 'weekDay', 'hour', 'minute',
              'second', 'search', 'regex', 'iregex'):
      return [value]
    elif lookupType in ('exact', 'gt', 'gte', 'lt', 'lte'):
      return [self.getDbPrepValue(value, connection=connection,
                      prepared=prepared)]
    elif lookupType in ('range', 'in'):
      return [self.getDbPrepValue(v, connection=connection,
                      prepared=prepared) for v in value]
    elif lookupType in ('contains', 'icontains'):
      return ["%%%s%%" % connection.ops.prepForLikeQuery(value)]
    elif lookupType == 'iexact':
      return [connection.ops.prepForIexactQuery(value)]
    elif lookupType in ('startswith', 'istartswith'):
      return ["%s%%" % connection.ops.prepForLikeQuery(value)]
    elif lookupType in ('endswith', 'iendswith'):
      return ["%%%s" % connection.ops.prepForLikeQuery(value)]
    elif lookupType == 'isnull':
      return []
    elif lookupType == 'year':
      if isinstance(self, DateTimeField):
        return connection.ops.yearLookupBoundsForDatetimeField(value)
      elif isinstance(self, DateField):
        return connection.ops.yearLookupBoundsForDateField(value)
      else:
        return [value]          # this isn't supposed to happen
    else:
      return [value]

  def hasDefault(self):
    """
    Returns a boolean of whether this field has a default value.
    """
    return self.default is not NOT_PROVIDED

  def getDefault(self):
    """
    Returns the default value for this field.
    """
    if self.hasDefault():
      if callable(self.default):
        return self.default()
      return forceText(self.default, stringsOnly=True)
    if (not self.emptyStringsAllowed or (self.null and
          not connection.features.interpretsEmptyStringsAsNulls)):
      return None
    return ""

  def getValidatorUniqueLookupType(self):
    return '%s__exact' % self.name

  def getChoices(self, includeBlank=True, blankChoice=BLANK_CHOICE_DASH):
    """Returns choices with a default blank choices included, for use
    as SelectField choices for this field."""
    blankDefined = False
    choices = list(self.choices) if self.choices else []
    namedGroups = choices and isinstance(choices[0][1], (list, tuple))
    if not namedGroups:
      for choice, __ in choices:
        if choice in ('', None):
          blankDefined = True
          break

    firstChoice = (blankChoice if includeBlank and
            not blankDefined else [])
    if self.choices:
      return firstChoice + choices
    relModel = self.rel.to
    if hasattr(self.rel, 'getRelatedField'):
      lst = [(getattr(x, self.rel.getRelatedField().attname),
          smartText(x))
          for x in relModel._defaultManager.complexFilter(
            self.getLimitChoicesTo())]
    else:
      lst = [(x._getPkVal(), smartText(x))
          for x in relModel._defaultManager.complexFilter(
            self.getLimitChoicesTo())]
    return firstChoice + lst

  def getChoicesDefault(self):
    return self.getChoices()

  def getFlatchoices(self, includeBlank=True,
            blankChoice=BLANK_CHOICE_DASH):
    """
    Returns flattened choices with a default blank choice included.
    """
    firstChoice = blankChoice if includeBlank else []
    return firstChoice + list(self.flatchoices)

  def _getValFromObj(self, obj):
    if obj is not None:
      return getattr(obj, self.attname)
    else:
      return self.getDefault()

  def valueToString(self, obj):
    """
    Returns a string value of this field from the passed obj.
    This is used by the serialization framework.
    """
    return smartText(self._getValFromObj(obj))

  def bind(self, fieldmapping, original, boundFieldClass):
    return boundFieldClass(self, fieldmapping, original)

  def _getChoices(self):
    if isinstance(self._choices, collections.Iterator):
      choices, self._choices = tee(self._choices)
      return choices
    else:
      return self._choices
  choices = property(_getChoices)

  def _getFlatchoices(self):
    """Flattened version of choices tuple."""
    flat = []
    for choice, value in self.choices:
      if isinstance(value, (list, tuple)):
        flat.extend(value)
      else:
        flat.append((choice, value))
    return flat
  flatchoices = property(_getFlatchoices)

  def saveFormData(self, instance, data):
    setattr(instance, self.name, data)

  def formfield(self, formClass=None, choicesFormClass=None, **kwargs):
    """
    Returns a theory.forms.Field instance for this database Field.
    """
    defaults = {'required': not self.blank,
          'label': capfirst(self.verboseName),
          'helpText': self.helpText}
    if self.hasDefault():
      if callable(self.default):
        defaults['initData'] = self.default
        defaults['showHiddenInitial'] = True
      else:
        defaults['initData'] = self.getDefault()
    if self.choices:
      # Fields with choices get special treatment.
      includeBlank = (self.blank or
               not (self.hasDefault() or 'initData' in kwargs))
      defaults['choices'] = self.getChoices(includeBlank=includeBlank)
      defaults['coerce'] = self.toPython
      if self.null:
        defaults['emptyValue'] = None
      if choicesFormClass is not None:
        formClass = choicesFormClass
      else:
        formClass = field.TypedChoiceField
      # Many of the subclass-specific formfield arguments (minValue,
      # maxValue) don't apply for choice fields, so be sure to only pass
      # the values that TypedChoiceField will understand.
      for k in list(kwargs):
        if k not in ('coerce', 'emptyValue', 'choices', 'required',
               'widget', 'label', 'initData', 'helpText',
               'errorMessages', 'showHiddenInitial'):
          del kwargs[k]
    defaults.update(kwargs)
    if formClass is None:
      formClass = field.TextField
    return formClass(**defaults)

  def valueFromObject(self, obj):
    """
    Returns the value of this field in the given modal instance.
    """
    return getattr(obj, self.attname)


class AutoField(Field):
  description = _("Integer")

  emptyStringsAllowed = False
  defaultErrorMessages = {
    'invalid': _("'%(value)s' value must be an integer."),
  }

  def __init__(self, *args, **kwargs):
    kwargs['blank'] = True
    super(AutoField, self).__init__(*args, **kwargs)

  def check(self, **kwargs):
    errors = super(AutoField, self).check(**kwargs)
    errors.extend(self._checkPrimaryKey())
    return errors

  def _checkPrimaryKey(self):
    if not self.primaryKey:
      return [
        checks.Error(
          'AutoFields must set primaryKey=True.',
          hint=None,
          obj=self,
          id='fields.E100',
        ),
      ]
    else:
      return []

  def deconstruct(self):
    name, path, args, kwargs = super(AutoField, self).deconstruct()
    del kwargs['blank']
    kwargs['primaryKey'] = True
    return name, path, args, kwargs

  def getInternalType(self):
    return "AutoField"

  def toPython(self, value):
    if value is None:
      return value
    try:
      return int(value)
    except (TypeError, ValueError):
      raise exceptions.ValidationError(
        self.errorMessages['invalid'],
        code='invalid',
        params={'value': value},
      )

  def validate(self, value, modalInstance):
    pass

  def getDbPrepValue(self, value, connection, prepared=False):
    if not prepared:
      value = self.getPrepValue(value)
      value = connection.ops.validateAutopkValue(value)
    return value

  def getPrepValue(self, value):
    value = super(AutoField, self).getPrepValue(value)
    if value is None:
      return None
    return int(value)

  def contributeToClass(self, cls, name):
    assert not cls._meta.hasAutoField, \
      "A modal can't have more than one AutoField."
    super(AutoField, self).contributeToClass(cls, name)
    cls._meta.hasAutoField = True
    cls._meta.autoField = self

  def formfield(self, **kwargs):
    return None


class BooleanField(Field):
  emptyStringsAllowed = False
  defaultErrorMessages = {
    'invalid': _("'%(value)s' value must be either True or False."),
  }
  description = _("Boolean (Either True or False)")

  def __init__(self, *args, **kwargs):
    kwargs['blank'] = True
    super(BooleanField, self).__init__(*args, **kwargs)

  def check(self, **kwargs):
    errors = super(BooleanField, self).check(**kwargs)
    errors.extend(self._checkNull(**kwargs))
    return errors

  def _checkNull(self, **kwargs):
    if getattr(self, 'null', False):
      return [
        checks.Error(
          'BooleanFields do not accept null values.',
          hint='Use a NullBooleanField instead.',
          obj=self,
          id='fields.E110',
        )
      ]
    else:
      return []

  def deconstruct(self):
    name, path, args, kwargs = super(BooleanField, self).deconstruct()
    del kwargs['blank']
    return name, path, args, kwargs

  def getInternalType(self):
    return "BooleanField"

  def toPython(self, value):
    if value in (True, False):
      # if value is 1 or 0 than it's equal to True or False, but we want
      # to return a true bool for semantic reasons.
      return bool(value)
    if value in ('t', 'True', '1'):
      return True
    if value in ('f', 'False', '0'):
      return False
    raise exceptions.ValidationError(
      self.errorMessages['invalid'],
      code='invalid',
      params={'value': value},
    )

  def getPrepLookup(self, lookupType, value):
    # Special-case handling for filters coming from a Web request (e.g. the
    # admin interface). Only works for scalar values (not lists). If you're
    # passing in a list, you might as well make things the right type when
    # constructing the list.
    if value in ('1', '0'):
      value = bool(int(value))
    return super(BooleanField, self).getPrepLookup(lookupType, value)

  def getPrepValue(self, value):
    value = super(BooleanField, self).getPrepValue(value)
    if value is None:
      return None
    return bool(value)

  def formfield(self, **kwargs):
    # Unlike most fields, BooleanField figures out includeBlank from
    # self.null instead of self.blank.
    if self.choices:
      includeBlank = (self.null or
               not (self.hasDefault() or 'initData' in kwargs))
      defaults = {'choices': self.getChoices(includeBlank=includeBlank)}
    else:
      defaults = {'formClass': field.BooleanField}
    defaults.update(kwargs)
    return super(BooleanField, self).formfield(**defaults)


class CharField(Field):
  description = _("String (up to %(maxLength)s)")

  def __init__(self, *args, **kwargs):
    super(CharField, self).__init__(*args, **kwargs)
    self.validators.append(validators.MaxLengthValidator(self.maxLength))

  def check(self, **kwargs):
    errors = super(CharField, self).check(**kwargs)
    errors.extend(self._checkMaxLengthAttribute(**kwargs))
    return errors

  def _checkMaxLengthAttribute(self, **kwargs):
    try:
      maxLength = int(self.maxLength)
      if maxLength <= 0:
        raise ValueError()
    except TypeError:
      return [
        checks.Error(
          "CharFields must define a 'maxLength' attribute.",
          hint=None,
          obj=self,
          id='fields.E120',
        )
      ]
    except ValueError:
      return [
        checks.Error(
          "'maxLength' must be a positive integer.",
          hint=None,
          obj=self,
          id='fields.E121',
        )
      ]
    else:
      return []

  def getInternalType(self):
    return "CharField"

  def toPython(self, value):
    if isinstance(value, six.stringTypes) or value is None:
      return value
    return smartText(value)

  def getPrepValue(self, value):
    value = super(CharField, self).getPrepValue(value)
    return self.toPython(value)

  def formfield(self, **kwargs):
    # Passing maxLength to field.CharField means that the value's length
    # will be validated twice. This is considered acceptable since we want
    # the value in the form field (to pass into widget for example).
    defaults = {'maxLength': self.maxLength}
    defaults.update(kwargs)
    return super(CharField, self).formfield(**defaults)


# TODO: Maybe move this into contrib, because it's specialized.
class CommaSeparatedIntegerField(CharField):
  defaultValidators = [validators.validateCommaSeparatedIntegerList]
  description = _("Comma-separated integers")

  def formfield(self, **kwargs):
    defaults = {
      'errorMessages': {
        'invalid': _('Enter only digits separated by commas.'),
      }
    }
    defaults.update(kwargs)
    return super(CommaSeparatedIntegerField, self).formfield(**defaults)


class DateField(Field):
  emptyStringsAllowed = False
  defaultErrorMessages = {
    'invalid': _("'%(value)s' value has an invalid date format. It must be "
           "in YYYY-MM-DD format."),
    'invalidDate': _("'%(value)s' value has the correct format (YYYY-MM-DD) "
             "but it is an invalid date."),
  }
  description = _("Date (without time)")

  def __init__(self, verboseName=None, name=None, autoNow=False,
         autoNowAdd=False, **kwargs):
    self.autoNow, self.autoNowAdd = autoNow, autoNowAdd
    if autoNow or autoNowAdd:
      kwargs['editable'] = False
      kwargs['blank'] = True
    super(DateField, self).__init__(verboseName, name, **kwargs)

  def deconstruct(self):
    name, path, args, kwargs = super(DateField, self).deconstruct()
    if self.autoNow:
      kwargs['autoNow'] = True
    if self.autoNowAdd:
      kwargs['autoNowAdd'] = True
    if self.autoNow or self.autoNowAdd:
      del kwargs['editable']
      del kwargs['blank']
    return name, path, args, kwargs

  def getInternalType(self):
    return "DateField"

  def toPython(self, value):
    if value is None:
      return value
    if isinstance(value, datetime.datetime):
      if settings.USE_TZ and timezone.isAware(value):
        # Convert aware datetimes to the default time zone
        # before casting them to dates (#17742).
        defaultTimezone = timezone.getDefaultTimezone()
        value = timezone.makeNaive(value, defaultTimezone)
      return value.date()
    if isinstance(value, datetime.date):
      return value

    try:
      parsed = parseDate(value)
      if parsed is not None:
        return parsed
    except ValueError:
      raise exceptions.ValidationError(
        self.errorMessages['invalidDate'],
        code='invalidDate',
        params={'value': value},
      )

    raise exceptions.ValidationError(
      self.errorMessages['invalid'],
      code='invalid',
      params={'value': value},
    )

  def preSave(self, modalInstance, add):
    if self.autoNow or (self.autoNowAdd and add):
      value = datetime.date.today()
      setattr(modalInstance, self.attname, value)
      return value
    else:
      return super(DateField, self).preSave(modalInstance, add)

  def contributeToClass(self, cls, name):
    super(DateField, self).contributeToClass(cls, name)
    if not self.null:
      setattr(cls, 'getNextBy_%s' % self.name,
        curry(cls._getNextOrPreviousBy_FIELD, field=self,
           isNext=True))
      setattr(cls, 'getPreviousBy_%s' % self.name,
        curry(cls._getNextOrPreviousBy_FIELD, field=self,
           isNext=False))

  def getPrepLookup(self, lookupType, value):
    # For dates lookups, convert the value to an int
    # so the database backend always sees a consistent type.
    if lookupType in ('month', 'day', 'weekDay', 'hour', 'minute', 'second'):
      return int(value)
    return super(DateField, self).getPrepLookup(lookupType, value)

  def getPrepValue(self, value):
    value = super(DateField, self).getPrepValue(value)
    return self.toPython(value)

  def getDbPrepValue(self, value, connection, prepared=False):
    # Casts dates into the format expected by the backend
    if not prepared:
      value = self.getPrepValue(value)
    return connection.ops.valueToDbDate(value)

  def valueToString(self, obj):
    val = self._getValFromObj(obj)
    return '' if val is None else val.isoformat()

  def formfield(self, **kwargs):
    defaults = {'formClass': field.DateField}
    defaults.update(kwargs)
    return super(DateField, self).formfield(**defaults)


class DateTimeField(DateField):
  emptyStringsAllowed = False
  defaultErrorMessages = {
    'invalid': _("'%(value)s' value has an invalid format. It must be in "
           "YYYY-MM-DD HH:MM[:ss[.uuuuuu]][TZ] format."),
    'invalidDate': _("'%(value)s' value has the correct format "
             "(YYYY-MM-DD) but it is an invalid date."),
    'invalidDatetime': _("'%(value)s' value has the correct format "
               "(YYYY-MM-DD HH:MM[:ss[.uuuuuu]][TZ]) "
               "but it is an invalid date/time."),
  }
  description = _("Date (with time)")

  # __init__ is inherited from DateField

  def getInternalType(self):
    return "DateTimeField"

  def toPython(self, value):
    if value is None:
      return value
    if isinstance(value, datetime.datetime):
      return value
    if isinstance(value, datetime.date):
      value = datetime.datetime(value.year, value.month, value.day)
      if settings.USE_TZ:
        # For backwards compatibility, interpret naive datetimes in
        # local time. This won't work during DST change, but we can't
        # do much about it, so we let the exceptions percolate up the
        # call stack.
        warnings.warn("DateTimeField %s.%s received a naive datetime "
               "(%s) while time zone support is active." %
               (self.modal.__name__, self.name, value),
               RuntimeWarning)
        defaultTimezone = timezone.getDefaultTimezone()
        value = timezone.makeAware(value, defaultTimezone)
      return value

    try:
      parsed = parseDatetime(value)
      if parsed is not None:
        return parsed
    except ValueError:
      raise exceptions.ValidationError(
        self.errorMessages['invalidDatetime'],
        code='invalidDatetime',
        params={'value': value},
      )

    try:
      parsed = parseDate(value)
      if parsed is not None:
        return datetime.datetime(parsed.year, parsed.month, parsed.day)
    except ValueError:
      raise exceptions.ValidationError(
        self.errorMessages['invalidDate'],
        code='invalidDate',
        params={'value': value},
      )

    raise exceptions.ValidationError(
      self.errorMessages['invalid'],
      code='invalid',
      params={'value': value},
    )

  def preSave(self, modalInstance, add):
    if self.autoNow or (self.autoNowAdd and add):
      value = timezone.now()
      setattr(modalInstance, self.attname, value)
      return value
    else:
      return super(DateTimeField, self).preSave(modalInstance, add)

  # contributeToClass is inherited from DateField, it registers
  # getNextBy_FOO and getPrevBy_FOO

  # getPrepLookup is inherited from DateField

  def getPrepValue(self, value):
    value = super(DateTimeField, self).getPrepValue(value)
    value = self.toPython(value)
    if value is not None and settings.USE_TZ and timezone.isNaive(value):
      # For backwards compatibility, interpret naive datetimes in local
      # time. This won't work during DST change, but we can't do much
      # about it, so we let the exceptions percolate up the call stack.
      warnings.warn("DateTimeField %s.%s received a naive datetime (%s)"
             " while time zone support is active." %
             (self.modal.__name__, self.name, value),
             RuntimeWarning)
      defaultTimezone = timezone.getDefaultTimezone()
      value = timezone.makeAware(value, defaultTimezone)
    return value

  def getDbPrepValue(self, value, connection, prepared=False):
    # Casts datetimes into the format expected by the backend
    if not prepared:
      value = self.getPrepValue(value)
    return connection.ops.valueToDbDatetime(value)

  def valueToString(self, obj):
    val = self._getValFromObj(obj)
    return '' if val is None else val.isoformat()

  def formfield(self, **kwargs):
    defaults = {'formClass': field.DateTimeField}
    defaults.update(kwargs)
    return super(DateTimeField, self).formfield(**defaults)


class DecimalField(Field):
  emptyStringsAllowed = False
  defaultErrorMessages = {
    'invalid': _("'%(value)s' value must be a decimal number."),
  }
  description = _("Decimal number")

  def __init__(self, verboseName=None, name=None, maxDigits=None,
         decimalPlaces=None, **kwargs):
    self.maxDigits, self.decimalPlaces = maxDigits, decimalPlaces
    super(DecimalField, self).__init__(verboseName, name, **kwargs)

  def check(self, **kwargs):
    errors = super(DecimalField, self).check(**kwargs)

    digitsErrors = self._checkDecimalPlaces()
    digitsErrors.extend(self._checkMaxDigits())
    if not digitsErrors:
      errors.extend(self._checkDecimalPlacesAndMaxDigits(**kwargs))
    else:
      errors.extend(digitsErrors)
    return errors

  def _checkDecimalPlaces(self):
    try:
      decimalPlaces = int(self.decimalPlaces)
      if decimalPlaces < 0:
        raise ValueError()
    except TypeError:
      return [
        checks.Error(
          "DecimalFields must define a 'decimalPlaces' attribute.",
          hint=None,
          obj=self,
          id='fields.E130',
        )
      ]
    except ValueError:
      return [
        checks.Error(
          "'decimalPlaces' must be a non-negative integer.",
          hint=None,
          obj=self,
          id='fields.E131',
        )
      ]
    else:
      return []

  def _checkMaxDigits(self):
    try:
      maxDigits = int(self.maxDigits)
      if maxDigits <= 0:
        raise ValueError()
    except TypeError:
      return [
        checks.Error(
          "DecimalFields must define a 'maxDigits' attribute.",
          hint=None,
          obj=self,
          id='fields.E132',
        )
      ]
    except ValueError:
      return [
        checks.Error(
          "'maxDigits' must be a positive integer.",
          hint=None,
          obj=self,
          id='fields.E133',
        )
      ]
    else:
      return []

  def _checkDecimalPlacesAndMaxDigits(self, **kwargs):
    if int(self.decimalPlaces) > int(self.maxDigits):
      return [
        checks.Error(
          "'maxDigits' must be greater or equal to 'decimalPlaces'.",
          hint=None,
          obj=self,
          id='fields.E134',
        )
      ]
    return []

  def deconstruct(self):
    name, path, args, kwargs = super(DecimalField, self).deconstruct()
    if self.maxDigits is not None:
      kwargs['maxDigits'] = self.maxDigits
    if self.decimalPlaces is not None:
      kwargs['decimalPlaces'] = self.decimalPlaces
    return name, path, args, kwargs

  def getInternalType(self):
    return "DecimalField"

  def toPython(self, value):
    if value is None:
      return value
    try:
      return decimal.Decimal(value)
    except decimal.InvalidOperation:
      raise exceptions.ValidationError(
        self.errorMessages['invalid'],
        code='invalid',
        params={'value': value},
      )

  def _format(self, value):
    if isinstance(value, six.stringTypes) or value is None:
      return value
    else:
      return self.formatNumber(value)

  def formatNumber(self, value):
    """
    Formats a number into a string with the requisite number of digits and
    decimal places.
    """
    # Method moved to theory.db.backends.utils.
    #
    # It is preserved because it is used by the oracle backend
    # (theory.db.backends.oracle.query), and also for
    # backwards-compatibility with any external code which may have used
    # this method.
    from theory.db.backends import utils
    return utils.formatNumber(value, self.maxDigits, self.decimalPlaces)

  def getDbPrepSave(self, value, connection):
    return connection.ops.valueToDbDecimal(self.toPython(value),
        self.maxDigits, self.decimalPlaces)

  def getPrepValue(self, value):
    value = super(DecimalField, self).getPrepValue(value)
    return self.toPython(value)

  def formfield(self, **kwargs):
    defaults = {
      'maxDigits': self.maxDigits,
      'decimalPlaces': self.decimalPlaces,
      'formClass': field.DecimalField,
    }
    defaults.update(kwargs)
    return super(DecimalField, self).formfield(**defaults)


class EmailField(CharField):
  defaultValidators = [validators.validateEmail]
  description = _("Email address")

  def __init__(self, *args, **kwargs):
    # maxLength should be overridden to 254 characters to be fully
    # compliant with RFCs 3696 and 5321

    kwargs['maxLength'] = kwargs.get('maxLength', 75)
    super(EmailField, self).__init__(*args, **kwargs)

  def deconstruct(self):
    name, path, args, kwargs = super(EmailField, self).deconstruct()
    # We do not exclude maxLength if it matches default as we want to change
    # the default in future.
    return name, path, args, kwargs

  def formfield(self, **kwargs):
    # As with CharField, this will cause email validation to be performed
    # twice.
    defaults = {
      'formClass': field.EmailField,
    }
    defaults.update(kwargs)
    return super(EmailField, self).formfield(**defaults)


class FilePathField(Field):
  description = _("File path")

  def __init__(self, verboseName=None, name=None, path='', match=None,
         recursive=False, allowFiles=True, allowFolders=False, **kwargs):
    self.path, self.match, self.recursive = path, match, recursive
    self.allowFiles, self.allowFolders = allowFiles, allowFolders
    kwargs['maxLength'] = kwargs.get('maxLength', 100)
    super(FilePathField, self).__init__(verboseName, name, **kwargs)

  def check(self, **kwargs):
    errors = super(FilePathField, self).check(**kwargs)
    errors.extend(self._checkAllowingFilesOrFolders(**kwargs))
    return errors

  def _checkAllowingFilesOrFolders(self, **kwargs):
    if not self.allowFiles and not self.allowFolders:
      return [
        checks.Error(
          "FilePathFields must have either 'allowFiles' or 'allowFolders' set to True.",
          hint=None,
          obj=self,
          id='fields.E140',
        )
      ]
    return []

  def deconstruct(self):
    name, path, args, kwargs = super(FilePathField, self).deconstruct()
    if self.path != '':
      kwargs['path'] = self.path
    if self.match is not None:
      kwargs['match'] = self.match
    if self.recursive is not False:
      kwargs['recursive'] = self.recursive
    if self.allowFiles is not True:
      kwargs['allowFiles'] = self.allowFiles
    if self.allowFolders is not False:
      kwargs['allowFolders'] = self.allowFolders
    if kwargs.get("maxLength", None) == 100:
      del kwargs["maxLength"]
    return name, path, args, kwargs

  def getPrepValue(self, value):
    value = super(FilePathField, self).getPrepValue(value)
    if value is None:
      return None
    return six.textType(value)

  def formfield(self, **kwargs):
    defaults = {
      'path': self.path,
      'match': self.match,
      'recursive': self.recursive,
      'formClass': field.FilePathField,
      'allowFiles': self.allowFiles,
      'allowFolders': self.allowFolders,
    }
    defaults.update(kwargs)
    return super(FilePathField, self).formfield(**defaults)

  def getInternalType(self):
    return "FilePathField"


class FloatField(Field):
  emptyStringsAllowed = False
  defaultErrorMessages = {
    'invalid': _("'%(value)s' value must be a float."),
  }
  description = _("Floating point number")

  def getPrepValue(self, value):
    value = super(FloatField, self).getPrepValue(value)
    if value is None:
      return None
    return float(value)

  def getInternalType(self):
    return "FloatField"

  def toPython(self, value):
    if value is None:
      return value
    try:
      return float(value)
    except (TypeError, ValueError):
      raise exceptions.ValidationError(
        self.errorMessages['invalid'],
        code='invalid',
        params={'value': value},
      )

  def formfield(self, **kwargs):
    defaults = {'formClass': field.FloatField}
    defaults.update(kwargs)
    return super(FloatField, self).formfield(**defaults)


class IntegerField(Field):
  emptyStringsAllowed = False
  defaultErrorMessages = {
    'invalid': _("'%(value)s' value must be an integer."),
  }
  description = _("Integer")

  @cachedProperty
  def validators(self):
    # These validators can't be added at field initialization time since
    # they're based on values retrieved from `connection`.
    rangeValidators = []
    internalType = self.getInternalType()
    minValue, maxValue = connection.ops.integerFieldRange(internalType)
    if minValue is not None:
      rangeValidators.append(validators.MinValueValidator(minValue))
    if maxValue is not None:
      rangeValidators.append(validators.MaxValueValidator(maxValue))
    return super(IntegerField, self).validators + rangeValidators

  def getPrepValue(self, value):
    value = super(IntegerField, self).getPrepValue(value)
    if value is None:
      return None
    return int(value)

  def getPrepLookup(self, lookupType, value):
    if ((lookupType == 'gte' or lookupType == 'lt')
        and isinstance(value, float)):
      value = math.ceil(value)
    return super(IntegerField, self).getPrepLookup(lookupType, value)

  def getInternalType(self):
    return "IntegerField"

  def toPython(self, value):
    if value is None:
      return value
    try:
      return int(value)
    except (TypeError, ValueError):
      raise exceptions.ValidationError(
        self.errorMessages['invalid'],
        code='invalid',
        params={'value': value},
      )

  def formfield(self, **kwargs):
    defaults = {'formClass': field.IntegerField}
    defaults.update(kwargs)
    return super(IntegerField, self).formfield(**defaults)


class BigIntegerField(IntegerField):
  emptyStringsAllowed = False
  description = _("Big (8 byte) integer")
  MAX_BIGINT = 9223372036854775807

  def getInternalType(self):
    return "BigIntegerField"

  def formfield(self, **kwargs):
    defaults = {'minValue': -BigIntegerField.MAX_BIGINT - 1,
          'maxValue': BigIntegerField.MAX_BIGINT}
    defaults.update(kwargs)
    return super(BigIntegerField, self).formfield(**defaults)


class IPAddressField(Field):
  emptyStringsAllowed = False
  description = _("IPv4 address")

  def __init__(self, *args, **kwargs):
    warnings.warn("IPAddressField has been deprecated. Use GenericIPAddressField instead.",
           RemovedInTheory19Warning)
    kwargs['maxLength'] = 15
    super(IPAddressField, self).__init__(*args, **kwargs)

  def deconstruct(self):
    name, path, args, kwargs = super(IPAddressField, self).deconstruct()
    del kwargs['maxLength']
    return name, path, args, kwargs

  def getPrepValue(self, value):
    value = super(IPAddressField, self).getPrepValue(value)
    if value is None:
      return None
    return six.textType(value)

  def getInternalType(self):
    return "IPAddressField"

  def formfield(self, **kwargs):
    defaults = {'formClass': field.IPAddressField}
    defaults.update(kwargs)
    return super(IPAddressField, self).formfield(**defaults)


class GenericIPAddressField(Field):
  emptyStringsAllowed = True
  description = _("IP address")
  defaultErrorMessages = {}

  def __init__(self, verboseName=None, name=None, protocol='both',
         unpackIpv4=False, *args, **kwargs):
    self.unpackIpv4 = unpackIpv4
    self.protocol = protocol
    self.defaultValidators, invalidErrorMessage = \
      validators.ipAddressValidators(protocol, unpackIpv4)
    self.defaultErrorMessages['invalid'] = invalidErrorMessage
    kwargs['maxLength'] = 39
    super(GenericIPAddressField, self).__init__(verboseName, name, *args,
                          **kwargs)

  def check(self, **kwargs):
    errors = super(GenericIPAddressField, self).check(**kwargs)
    errors.extend(self._checkBlankAndNullValues(**kwargs))
    return errors

  def _checkBlankAndNullValues(self, **kwargs):
    if not getattr(self, 'null', False) and getattr(self, 'blank', False):
      return [
        checks.Error(
          ('GenericIPAddressFields cannot have blank=True if null=False, '
           'as blank values are stored as nulls.'),
          hint=None,
          obj=self,
          id='fields.E150',
        )
      ]
    return []

  def deconstruct(self):
    name, path, args, kwargs = super(GenericIPAddressField, self).deconstruct()
    if self.unpackIpv4 is not False:
      kwargs['unpackIpv4'] = self.unpackIpv4
    if self.protocol != "both":
      kwargs['protocol'] = self.protocol
    if kwargs.get("maxLength", None) == 39:
      del kwargs['maxLength']
    return name, path, args, kwargs

  def getInternalType(self):
    return "GenericIPAddressField"

  def toPython(self, value):
    if value and ':' in value:
      return cleanIpv6Address(value,
        self.unpackIpv4, self.errorMessages['invalid'])
    return value

  def getDbPrepValue(self, value, connection, prepared=False):
    if not prepared:
      value = self.getPrepValue(value)
    return value or None

  def getPrepValue(self, value):
    value = super(GenericIPAddressField, self).getPrepValue(value)
    if value is None:
      return None
    if value and ':' in value:
      try:
        return cleanIpv6Address(value, self.unpackIpv4)
      except exceptions.ValidationError:
        pass
    return six.textType(value)

  def formfield(self, **kwargs):
    defaults = {
      'protocol': self.protocol,
      'formClass': field.GenericIPAddressField,
    }
    defaults.update(kwargs)
    return super(GenericIPAddressField, self).formfield(**defaults)


class NullBooleanField(Field):
  emptyStringsAllowed = False
  defaultErrorMessages = {
    'invalid': _("'%(value)s' value must be either None, True or False."),
  }
  description = _("Boolean (Either True, False or None)")

  def __init__(self, *args, **kwargs):
    kwargs['null'] = True
    kwargs['blank'] = True
    super(NullBooleanField, self).__init__(*args, **kwargs)

  def deconstruct(self):
    name, path, args, kwargs = super(NullBooleanField, self).deconstruct()
    del kwargs['null']
    del kwargs['blank']
    return name, path, args, kwargs

  def getInternalType(self):
    return "NullBooleanField"

  def toPython(self, value):
    if value is None:
      return None
    if value in (True, False):
      return bool(value)
    if value in ('None',):
      return None
    if value in ('t', 'True', '1'):
      return True
    if value in ('f', 'False', '0'):
      return False
    raise exceptions.ValidationError(
      self.errorMessages['invalid'],
      code='invalid',
      params={'value': value},
    )

  def getPrepLookup(self, lookupType, value):
    # Special-case handling for filters coming from a Web request (e.g. the
    # admin interface). Only works for scalar values (not lists). If you're
    # passing in a list, you might as well make things the right type when
    # constructing the list.
    if value in ('1', '0'):
      value = bool(int(value))
    return super(NullBooleanField, self).getPrepLookup(lookupType,
                               value)

  def getPrepValue(self, value):
    value = super(NullBooleanField, self).getPrepValue(value)
    if value is None:
      return None
    return bool(value)

  def formfield(self, **kwargs):
    defaults = {
      'formClass': field.NullBooleanField,
      'required': not self.blank,
      'label': capfirst(self.verboseName),
      'helpText': self.helpText}
    defaults.update(kwargs)
    return super(NullBooleanField, self).formfield(**defaults)


class PositiveIntegerField(IntegerField):
  description = _("Positive integer")

  def getInternalType(self):
    return "PositiveIntegerField"

  def formfield(self, **kwargs):
    defaults = {'minValue': 0}
    defaults.update(kwargs)
    return super(PositiveIntegerField, self).formfield(**defaults)


class PositiveSmallIntegerField(IntegerField):
  description = _("Positive small integer")

  def getInternalType(self):
    return "PositiveSmallIntegerField"

  def formfield(self, **kwargs):
    defaults = {'minValue': 0}
    defaults.update(kwargs)
    return super(PositiveSmallIntegerField, self).formfield(**defaults)


class SlugField(CharField):
  defaultValidators = [validators.validateSlug]
  description = _("Slug (up to %(maxLength)s)")

  def __init__(self, *args, **kwargs):
    kwargs['maxLength'] = kwargs.get('maxLength', 50)
    # Set dbIndex=True unless it's been set manually.
    if 'dbIndex' not in kwargs:
      kwargs['dbIndex'] = True
    super(SlugField, self).__init__(*args, **kwargs)

  def deconstruct(self):
    name, path, args, kwargs = super(SlugField, self).deconstruct()
    if kwargs.get("maxLength", None) == 50:
      del kwargs['maxLength']
    if self.dbIndex is False:
      kwargs['dbIndex'] = False
    else:
      del kwargs['dbIndex']
    return name, path, args, kwargs

  def getInternalType(self):
    return "SlugField"

  def formfield(self, **kwargs):
    defaults = {'formClass': field.SlugField}
    defaults.update(kwargs)
    return super(SlugField, self).formfield(**defaults)


class SmallIntegerField(IntegerField):
  description = _("Small integer")

  def getInternalType(self):
    return "SmallIntegerField"


class TextField(Field):
  description = _("Text")

  def getInternalType(self):
    return "TextField"

  def getPrepValue(self, value):
    value = super(TextField, self).getPrepValue(value)
    if isinstance(value, six.stringTypes) or value is None:
      return value
    return smartText(value)

  def formfield(self, **kwargs):
    # Passing maxLength to field.CharField means that the value's length
    # will be validated twice. This is considered acceptable since we want
    # the value in the form field (to pass into widget for example).
    defaults = {'maxLength': self.maxLength}
    defaults.update(kwargs)
    return super(TextField, self).formfield(**defaults)


class TimeField(Field):
  emptyStringsAllowed = False
  defaultErrorMessages = {
    'invalid': _("'%(value)s' value has an invalid format. It must be in "
           "HH:MM[:ss[.uuuuuu]] format."),
    'invalidTime': _("'%(value)s' value has the correct format "
             "(HH:MM[:ss[.uuuuuu]]) but it is an invalid time."),
  }
  description = _("Time")

  def __init__(self, verboseName=None, name=None, autoNow=False,
         autoNowAdd=False, **kwargs):
    self.autoNow, self.autoNowAdd = autoNow, autoNowAdd
    if autoNow or autoNowAdd:
      kwargs['editable'] = False
      kwargs['blank'] = True
    super(TimeField, self).__init__(verboseName, name, **kwargs)

  def deconstruct(self):
    name, path, args, kwargs = super(TimeField, self).deconstruct()
    if self.autoNow is not False:
      kwargs["autoNow"] = self.autoNow
    if self.autoNowAdd is not False:
      kwargs["autoNowAdd"] = self.autoNowAdd
    if self.autoNow or self.autoNowAdd:
      del kwargs['blank']
      del kwargs['editable']
    return name, path, args, kwargs

  def getInternalType(self):
    return "TimeField"

  def toPython(self, value):
    if value is None:
      return None
    if isinstance(value, datetime.time):
      return value
    if isinstance(value, datetime.datetime):
      # Not usually a good idea to pass in a datetime here (it loses
      # information), but this can be a side-effect of interacting with a
      # database backend (e.g. Oracle), so we'll be accommodating.
      return value.time()

    try:
      parsed = parseTime(value)
      if parsed is not None:
        return parsed
    except ValueError:
      raise exceptions.ValidationError(
        self.errorMessages['invalidTime'],
        code='invalidTime',
        params={'value': value},
      )

    raise exceptions.ValidationError(
      self.errorMessages['invalid'],
      code='invalid',
      params={'value': value},
    )

  def preSave(self, modalInstance, add):
    if self.autoNow or (self.autoNowAdd and add):
      value = datetime.datetime.now().time()
      setattr(modalInstance, self.attname, value)
      return value
    else:
      return super(TimeField, self).preSave(modalInstance, add)

  def getPrepValue(self, value):
    value = super(TimeField, self).getPrepValue(value)
    return self.toPython(value)

  def getDbPrepValue(self, value, connection, prepared=False):
    # Casts times into the format expected by the backend
    if not prepared:
      value = self.getPrepValue(value)
    return connection.ops.valueToDbTime(value)

  def valueToString(self, obj):
    val = self._getValFromObj(obj)
    return '' if val is None else val.isoformat()

  def formfield(self, **kwargs):
    defaults = {'formClass': field.TimeField}
    defaults.update(kwargs)
    return super(TimeField, self).formfield(**defaults)


class URLField(CharField):
  defaultValidators = [validators.URLValidator()]
  description = _("URL")

  def __init__(self, verboseName=None, name=None, **kwargs):
    kwargs['maxLength'] = kwargs.get('maxLength', 200)
    super(URLField, self).__init__(verboseName, name, **kwargs)

  def deconstruct(self):
    name, path, args, kwargs = super(URLField, self).deconstruct()
    if kwargs.get("maxLength", None) == 200:
      del kwargs['maxLength']
    return name, path, args, kwargs

  def formfield(self, **kwargs):
    # As with CharField, this will cause URL validation to be performed
    # twice.
    defaults = {
      'formClass': field.URLField,
    }
    defaults.update(kwargs)
    return super(URLField, self).formfield(**defaults)


class BinaryField(Field):
  description = _("Raw binary data")
  emptyValues = [None, b'']

  def __init__(self, *args, **kwargs):
    kwargs['editable'] = False
    super(BinaryField, self).__init__(*args, **kwargs)
    if self.maxLength is not None:
      self.validators.append(validators.MaxLengthValidator(self.maxLength))

  def deconstruct(self):
    name, path, args, kwargs = super(BinaryField, self).deconstruct()
    del kwargs['editable']
    return name, path, args, kwargs

  def getInternalType(self):
    return "BinaryField"

  def getDefault(self):
    if self.hasDefault() and not callable(self.default):
      return self.default
    default = super(BinaryField, self).getDefault()
    if default == '':
      return b''
    return default

  def getDbPrepValue(self, value, connection, prepared=False):
    value = super(BinaryField, self).getDbPrepValue(value, connection, prepared)
    if value is not None:
      return connection.Database.Binary(value)
    return value

  def valueToString(self, obj):
    """Binary data is serialized as base64"""
    return b64encode(forceBytes(self._getValFromObj(obj))).decode('ascii')

  def toPython(self, value):
    # If it's a string, it should be base64-encoded data
    if isinstance(value, six.textType):
      return six.memoryview(b64decode(forceBytes(value)))
    return value
