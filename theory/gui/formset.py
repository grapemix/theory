# -*- coding: utf-8 -*-
#!/usr/bin/env python
##### System wide lib #####
#from __future__ import unicodeLiterals

##### Theory lib #####
from theory.core.exceptions import ValidationError
from theory.gui.form import Form
from theory.gui.field import IntegerField, BooleanField
from theory.gui.util import ErrorList
from theory.gui.widget import HiddenInput
from theory.utils.encoding import python2UnicodeCompatible
from theory.utils.functional import cachedProperty
from theory.utils.safestring import markSafe
from theory.utils import six
from theory.utils.six.moves import xrange
from theory.utils.translation import ungettext, ugettext as _

##### Theory third-party lib #####

##### Local app #####

##### Theory app #####

##### Misc #####

__all__ = ('BaseFormSet', 'formsetFactory', 'allValid')

# special field names
TOTAL_FORM_COUNT = 'TOTAL_FORMS'
INITIAL_FORM_COUNT = 'INITIAL_FORMS'
MIN_NUM_FORM_COUNT = 'MIN_NUM_FORMS'
MAX_NUM_FORM_COUNT = 'MAX_NUM_FORMS'
ORDERING_FIELD_NAME = 'ORDER'
DELETION_FIELD_NAME = 'DELETE'

# default minimum number of forms in a formset
DEFAULT_MIN_NUM = 0

# default maximum number of forms in a formset, to prevent memory exhaustion
DEFAULT_MAX_NUM = 1000


class ManagementForm(Form):
  """
  ``ManagementForm`` is used to keep track of how many form instances
  are displayed on the page. If adding new forms via javascript, you should
  increment the count field of this form as well.
  """
  def __init__(self, *args, **kwargs):
    self.baseFields[TOTAL_FORM_COUNT] = IntegerField(widget=HiddenInput)
    self.baseFields[INITIAL_FORM_COUNT] = IntegerField(widget=HiddenInput)
    # MIN_NUM_FORM_COUNT and MAX_NUM_FORM_COUNT are output with the rest of
    # the management form, but only for the convenience of client-side
    # code. The POST value of them returned from the client is not checked.
    self.baseFields[MIN_NUM_FORM_COUNT] = IntegerField(
        required=False,
        widget=HiddenInput
        )
    self.baseFields[MAX_NUM_FORM_COUNT] = IntegerField(
        required=False,
        widget=HiddenInput
        )
    super(ManagementForm, self).__init__(*args, **kwargs)


@python2UnicodeCompatible
class BaseFormSet(object):
  """
  A collection of instances of the same Form class.
  """
  def __init__(self, data=None, files=None, autoId='id_%s', prefix=None,
         initial=None, errorClass=ErrorList):
    self.isBound = data is not None or files is not None
    self.prefix = prefix or self.getDefaultPrefix()
    self.autoId = autoId
    self.data = data or {}
    self.files = files or {}
    self.initial = initial
    self.errorClass = errorClass
    self._errors = None
    self._nonFormErrors = None

  def __str__(self):
    return self.asTable()

  def __iter__(self):
    """Yields the formLst in the order they should be rendered"""
    return iter(self.formLst)

  def __getitem__(self, index):
    """Returns the form at the given index, based on the rendering order"""
    return self.formLst[index]

  def __len__(self):
    return len(self.formLst)

  def __bool__(self):
    """
    All formLstets have a management form which is not included in the length
    """
    return True

  def __nonzero__(self):      # Python 2 compatibility
    return type(self).__bool__(self)

  @property
  def managementForm(self):
    """Returns the ManagementForm instance for this FormSet."""
    if self.isBound:
      form = ManagementForm(self.data, autoId=self.autoId, prefix=self.prefix)
      if not form.isValid():
        raise ValidationError(
          _('ManagementForm data is missing or has been tampered with'),
          code='missingManagementForm',
        )
    else:
      form = ManagementForm(autoId=self.autoId, prefix=self.prefix, initial={
        TOTAL_FORM_COUNT: self.totalFormCount(),
        INITIAL_FORM_COUNT: self.initialFormCount(),
        MIN_NUM_FORM_COUNT: self.minNum,
        MAX_NUM_FORM_COUNT: self.maxNum
      })
    return form

  def totalFormCount(self):
    """Returns the total number of formLst in this FormSet."""
    if self.isBound:
      # return absoluteMax if it is lower than the actual total form
      # count in the data; this is DoS protection to prevent clients
      # from forcing the server to instantiate arbitrary numbers of
      # formLst
      return min(
          self.managementForm.cleanedData[TOTAL_FORM_COUNT],
          self.absoluteMax
          )
    else:
      initialFormLst = self.initialFormCount()
      totalFormLst = initialFormLst + self.extra
      # Allow all existing related objects/inlines to be displayed,
      # but don't allow extra beyond maxNum.
      if initialFormLst > self.maxNum >= 0:
        totalFormLst = initialFormLst
      elif totalFormLst > self.maxNum >= 0:
        totalFormLst = self.maxNum
    return totalFormLst

  def initialFormCount(self):
    """Returns the number of formLst that are required in this FormSet."""
    if self.isBound:
      return self.managementForm.cleanedData[INITIAL_FORM_COUNT]
    else:
      # Use the length of the initial data if it's there, 0 otherwise.
      initialFormLst = len(self.initial) if self.initial else 0
    return initialFormLst

  @cachedProperty
  def formLst(self):
    """
    Instantiate formLst at first property access.
    """
    # DoS protection is included in totalFormCount()
    formLst = [self._constructForm(i) for i in xrange(self.totalFormCount())]
    return formLst

  def _constructForm(self, i, **kwargs):
    """
    Instantiates and returns the i-th form instance in a formLstet.
    """
    defaults = {
      'autoId': self.autoId,
      'prefix': self.addPrefix(i),
      'errorClass': self.errorClass,
    }
    if self.isBound:
      defaults['data'] = self.data
      defaults['files'] = self.files
    if self.initial and not 'initial' in kwargs:
      try:
        defaults['initial'] = self.initial[i]
      except IndexError:
        pass
    # Allow extra formLst to be empty.
    if i >= self.initialFormCount():
      defaults['emptyPermitted'] = True
    defaults.update(kwargs)
    form = self.form(**defaults)
    self.addFields(form, i)
    return form

  @property
  def initialFormLst(self):
    """Return a list of all the initial formLst in this formLstet."""
    return self.formLst[:self.initialFormCount()]

  @property
  def extraFormLst(self):
    """Return a list of all the extra formLst in this formLstet."""
    return self.formLst[self.initialFormCount():]

  @property
  def emptyForm(self):
    form = self.form(
      autoId=self.autoId,
      prefix=self.addPrefix('__prefix__'),
      emptyPermitted=True,
    )
    self.addFields(form, None)
    return form

  @property
  def cleanedData(self):
    """
    Returns a list of form.cleanedData dicts for every form in self.formLst.
    """
    if not self.isValid():
      raise AttributeError(
          "'%s' object has no attribute 'cleanedData'" % self.__class__.__name__
          )
    return [form.cleanedData for form in self.formLst]

  @property
  def deletedFormLst(self):
    """
    Returns a list of formLst that have been marked for deletion.
    """
    if not self.isValid() or not self.canDelete:
      return []
    # construct _deletedFormIndexes which is just a list of form indexes
    # that have had their deletion widget set to True
    if not hasattr(self, '_deletedFormIndexes'):
      self._deletedFormIndexes = []
      for i in range(0, self.totalFormCount()):
        form = self.formLst[i]
        # if this is an extra form and hasn't changed, don't consider it
        if i >= self.initialFormCount() and not form.hasChanged():
          continue
        if self._shouldDeleteForm(form):
          self._deletedFormIndexes.append(i)
    return [self.formLst[i] for i in self._deletedFormIndexes]

  @property
  def orderedFormLst(self):
    """
    Returns a list of form in the order specified by the incoming data.
    Raises an AttributeError if ordering is not allowed.
    """
    if not self.isValid() or not self.canOrder:
      raise AttributeError(
          "'%s' object has no attribute 'orderedFormLst'" \
              % self.__class__.__name__
          )
    # Construct _ordering, which is a list of (formIndex, orderFieldValue)
    # tuples. After constructing this list, we'll sort it by orderFieldValue
    # so we have a way to get to the form indexes in the order specified
    # by the form data.
    if not hasattr(self, '_ordering'):
      self._ordering = []
      for i in range(0, self.totalFormCount()):
        form = self.formLst[i]
        # if this is an extra form and hasn't changed, don't consider it
        if i >= self.initialFormCount() and not form.hasChanged():
          continue
        # don't add data marked for deletion to self.orderedData
        if self.canDelete and self._shouldDeleteForm(form):
          continue
        self._ordering.append((i, form.cleanedData[ORDERING_FIELD_NAME]))
      # After we're done populating self._ordering, sort it.
      # A sort function to order things numerically ascending, but
      # None should be sorted below anything else. Allowing None as
      # a comparison value makes it so we can leave ordering fields
      # blank.

      def compareOrderingKey(k):
        if k[1] is None:
          return (1, 0)  # +infinity, larger than any number
        return (0, k[1])
      self._ordering.sort(key=compareOrderingKey)
    # Return a list of form.cleanedData dicts in the order specified by
    # the form data.
    return [self.formLst[i[0]] for i in self._ordering]

  @classmethod
  def getDefaultPrefix(cls):
    return 'form'

  def nonFormErrors(self):
    """
    Returns an ErrorList of errors that aren't associated with a particular
    form -- i.e., from formLstet.clean(). Returns an empty ErrorList if there
    are none.
    """
    if self._nonFormErrors is None:
      self.fullClean()
    return self._nonFormErrors

  @property
  def errors(self):
    """
    Returns a list of form.errors for every form in self.formLst.
    """
    if self._errors is None:
      self.fullClean()
    return self._errors

  def totalErrorCount(self):
    """
    Returns the number of errors across all formLst in the formLstet.
    """
    return len(self.nonFormErrors()) +\
      sum(len(formErrors) for formErrors in self.errors)

  def _shouldDeleteForm(self, form):
    """
    Returns whether or not the form was marked for deletion.
    """
    return form.cleanedData.get(DELETION_FIELD_NAME, False)

  def isValid(self):
    """
    Returns True if every form in self.formLst is valid.
    """
    if not self.isBound:
      return False
    # We loop over every form.errors here rather than short circuiting on the
    # first failure to make sure validation gets triggered for every form.
    formLstValid = True
    # This triggers a full clean.
    self.errors
    for i in range(0, self.totalFormCount()):
      form = self.formLst[i]
      if self.canDelete:
        if self._shouldDeleteForm(form):
          # This form is going to be deleted so any of its errors
          # should not cause the entire formLstet to be invalid.
          continue
      formLstValid &= form.isValid()
    return formLstValid and not bool(self.nonFormErrors())

  def fullClean(self):
    """
    Cleans all of self.data and populates self._errors and
    self._nonFormErrors.
    """
    self._errors = []
    self._nonFormErrors = self.errorClass()

    if not self.isBound:  # Stop further processing.
      return
    for i in range(0, self.totalFormCount()):
      form = self.formLst[i]
      self._errors.append(form.errors)
    try:
      if (self.validateMax and
          self.totalFormCount() - len(self.deletedFormLst) > self.maxNum) or \
          self.managementForm.cleanedData[TOTAL_FORM_COUNT] > self.absoluteMax:
        raise ValidationError(ungettext(
          "Please submit %d or fewer formLst.",
          "Please submit %d or fewer formLst.", self.maxNum) % self.maxNum,
          code='tooManyFormLst',
        )
      if (self.validateMin and
          self.totalFormCount() - len(self.deletedFormLst) < self.minNum):
        raise ValidationError(ungettext(
          "Please submit %d or more formLst.",
          "Please submit %d or more formLst.", self.minNum) % self.minNum,
          code='tooFewFormLst')
      # Give self.clean() a chance to do cross-form validation.
      self.clean()
    except ValidationError as e:
      self._nonFormErrors = self.errorClass(e.messages)

  def clean(self):
    """
    Hook for doing any extra formLstet-wide cleaning after Form.clean() has
    been called on every form. Any ValidationError raised by this method
    will not be associated with a particular form; it will be accesible
    via formLstet.nonFormErrors()
    """
    pass

  def hasChanged(self):
    """
    Returns true if data in any form differs from initial.
    """
    return any(form.hasChanged() for form in self)

  def addFields(self, form, index):
    """A hook for adding extra fields on to each form instance."""
    if self.canOrder:
      # Only pre-fill the ordering field for initial formLst.
      if index is not None and index < self.initialFormCount():
        form.fields[ORDERING_FIELD_NAME] = IntegerField(
            label=_('Order'),
            initial=index + 1,
            required=False
            )
      else:
        form.fields[ORDERING_FIELD_NAME] = IntegerField(
            label=_('Order'),
            required=False
            )
    if self.canDelete:
      form.fields[DELETION_FIELD_NAME] = BooleanField(
          label=_('Delete'),
          required=False
          )

  def addPrefix(self, index):
    return '%s-%s' % (self.prefix, index)

  def isMultipart(self):
    """
    Returns True if the formLstet needs to be multipart, i.e. it
    has FileInput. Otherwise, False.
    """
    if self.formLst:
      return self.formLst[0].isMultipart()
    else:
      return self.emptyForm.isMultipart()

  @property
  def media(self):
    # All the formLst on a FormSet are the same, so you only need to
    # interrogate the first form for media.
    if self.formLst:
      return self.formLst[0].media
    else:
      return self.emptyForm.media

def formsetFactory(form, formset=BaseFormSet, extra=1, canOrder=False,
          canDelete=False, maxNum=None, validateMax=False,
          minNum=None, validateMin=False):
  """Return a FormSet for the given form class."""
  if minNum is None:
    minNum = DEFAULT_MIN_NUM
  if maxNum is None:
    maxNum = DEFAULT_MAX_NUM
  # hard limit on forms instantiated, to prevent memory-exhaustion attacks
  # limit is simply maxNum + DEFAULT_MAX_NUM (which is 2*DEFAULT_MAX_NUM
  # if maxNum is None in the first place)
  absoluteMax = maxNum + DEFAULT_MAX_NUM
  extra += minNum
  attrs = {'form': form, 'extra': extra,
       'canOrder': canOrder, 'canDelete': canDelete,
       'minNum': minNum, 'maxNum': maxNum,
       'absoluteMax': absoluteMax, 'validateMin': validateMin,
       'validateMax': validateMax}
  return type(form.__name__ + str('FormSet'), (formset,), attrs)


def allValid(formsets):
  """Returns true if every formset in formsets is valid."""
  valid = True
  for formset in formsets:
    if not formset.isValid():
      valid = False
  return valid

