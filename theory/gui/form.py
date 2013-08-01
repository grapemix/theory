# -*- coding: utf-8 -*-
#!/usr/bin/env python

##### System wide lib #####
from abc import ABCMeta, abstractmethod
import copy

##### Theory lib #####
from theory.core.exceptions import ValidationError
from theory.gui.field import *
from theory.gui.widget import *
from theory.gui.widget import BasePacker
from theory.gui.e17.widget import *
from theory.utils.datastructures import SortedDict

##### Theory third-party lib #####

##### Local app #####

##### Theory app #####

##### Misc #####

__all__ = ("Form", "GuiForm", "StepForm", )

def pretty_name(name):
  """Converts 'first_name' to 'First name'"""
  if not name:
    return u''
  return name.replace('_', ' ').capitalize()

def get_declared_fields(bases, attrs, with_base_fields=True):
  """
  Create a list of form field instances from the passed in 'attrs', plus any
  similar fields on the base classes (in 'bases'). This is used by both the
  Form and ModelForm metclasses.

  If 'with_base_fields' is True, all fields from the bases are used.
  Otherwise, only fields in the 'declared_fields' attribute on the bases are
  used. The distinction is useful in ModelForm subclassing.
  Also integrates any additional media definitions
  """
  fields = [(field_name, attrs.pop(field_name)) for field_name, obj in attrs.items() if isinstance(obj, Field)]
  fields.sort(key=lambda x: x[1].creation_counter)

  # If this class is subclassing another Form, add that Form's fields.
  # Note that we loop over the bases in *reverse*. This is necessary in
  # order to preserve the correct order of fields.
  if with_base_fields:
    for base in bases[::-1]:
      if(hasattr(base, 'base_fields') and base.base_fields!=None):
        fields = base.base_fields.items() + fields
  else:
    for base in bases[::-1]:
      if(hasattr(base, 'declared_fields') and base.declared_fields!=None):
        fields = base.declared_fields.items() + fields

  return SortedDict(fields)

class DeclarativeFieldsMetaclass(type):
  """
  Metaclass that converts Field attributes to a dictionary called
  'base_fields', taking into account parent class 'base_fields' as well.
  """
  def __new__(cls, name, bases, attrs):
    attrs['base_fields'] = get_declared_fields(bases, attrs)
    new_class = super(DeclarativeFieldsMetaclass,
                 cls).__new__(cls, name, bases, attrs)
    return new_class

class FormBase(object):
  """This class should be stateful and picklable. The function being provided
  by this class include the logic to decide which field should be shown."""
  def __init__(self, *args, **kwargs):
    # The base_fields class attribute is the *class-wide* definition of
    # fields. Because a particular *instance* of the class might want to
    # alter self.fields, we create self.fields here by copying base_fields.
    # Instances should always modify self.fields; they should not modify
    # self.base_fields.
    self.is_bound = True # should be hash the initDate in the future
    self.fields = copy.deepcopy(self.base_fields)
    self.data = {}       # only used if fields are not singular
    self.files = {}      # might be removed in the future
    self.error_class = {}
    self._errors = None  # Stores the errors after clean() has been

  def __iter__(self):
    for name in self.fields:
      yield self[name]

  def __getitem__(self, name):
    "Returns a BoundField with the given name."
    try:
      field = self.fields[name]
    except KeyError:
      raise KeyError('Key %r not found in Form' % name)
    return BoundField(self, field, name)

  def _get_errors(self):
    "Returns an ErrorDict for the data provided for the form"
    if self._errors is None:
      self.full_clean()
    return self._errors
  errors = property(_get_errors)

  def is_valid(self):
    """
    Returns True if the form has no errors. Otherwise, False. If errors are
    being ignored, returns False.
    """
    return self.is_bound and not bool(self.errors)

  def full_clean(self):
    """
    Cleans all of self.data and populates self._errors and
    self.cleaned_data.
    """
    self._errors = {}
    #!!!!!!!! Do we want errors transparent or add one more layer
    #self._errors = ErrorDict()
    if not self.is_bound: # Stop further processing.
      return
    self.cleaned_data = {}
    # If the form is permitted to be empty, and none of the form data has
    # changed from the initial data, short circuit any validation.
    #if self.empty_permitted and not self.has_changed():
    #  return
    self._clean_fields()
    self._clean_form()
    self._post_clean()
    if self._errors:
      del self.cleaned_data

  # TODO: support fields required interactaction with other fields to get
  # final data
  def _clean_fields(self):
    for name, field in self.fields.items():
      # value_from_datadict() gets the data from the data dictionaries.
      # Each widget type knows how to retrieve its own data, because some
      # widgets split data over several HTML fields.
      if(field.isSingular):
        value = field.finalData
      #value = field.widget.value_from_datadict(self.data, self.files, name)
      try:
        if isinstance(field, FileField):
          initial = self.initial.get(name, field.initial)
          value = field.clean(value, initial)
        else:
          value = field.clean(value)
        self.cleaned_data[name] = value
        if hasattr(self, 'clean_%s' % name):
          value = getattr(self, 'clean_%s' % name)()
          self.cleaned_data[name] = value
      except ValidationError, e:
        self._errors[name] = e.messages
        if name in self.cleaned_data:
          del self.cleaned_data[name]

  def _clean_form(self):
    try:
      self.cleaned_data = self.clean()
    except ValidationError, e:
      self._errors[NON_FIELD_ERRORS] = self.error_class(e.messages)

  def _post_clean(self):
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
    return self.cleaned_data

  def has_changed(self):
    """
    Returns True if data differs from initial.
    """
    return bool(self.changed_data)

  def _get_changed_data(self):
    if self._changed_data is None:
      self._changed_data = []
      # XXX: For now we're asking the individual widgets whether or not the
      # data has changed. It would probably be more efficient to hash the
      # initial data, store it in a hidden field, and compare a hash of the
      # submitted data, but we'd need a way to easily get the string value
      # for a given field. Right now, that logic is embedded in the render
      # method of each widget.
      for name, field in self.fields.items():
        prefixed_name = self.add_prefix(name)
        data_value = field.widget.value_from_datadict(self.data, self.files, prefixed_name)
        if not field.show_hidden_initial:
          initial_value = self.initial.get(name, field.initial)
        else:
          initial_prefixed_name = self.add_initial_prefix(name)
          hidden_widget = field.hidden_widget()
          initial_value = hidden_widget.value_from_datadict(
            self.data, self.files, initial_prefixed_name)
        if field.widget._has_changed(initial_value, data_value):
          self._changed_data.append(name)
    return self._changed_data
  changed_data = property(_get_changed_data)

class GuiFormBase(FormBase, BasePacker):
  def __init__(self, *args, **kwargs):
    super(GuiFormBase, self).__init__(*args, **kwargs)
    # We have to call the initialize fxn explicitly because the
    # BasePacker initialize fxn won't be executed if we only called
    # super().__init__(). We temporary set win and bx as None because
    # form in a Command does not always need to render.
    BasePacker.__init__(self, None, None, *args, **kwargs)

  def _changeFormWindowHeight(self, maxHeight):
    # TODO: fix this super ugly hack
    size = self.win.size
    fieldHeight = len(self.fields) * 200
    preferHeight = fieldHeight if(fieldHeight<maxHeight) else maxHeight

    if(size[0]<640 or size[1]<preferHeight):
      self.win.resize(640, preferHeight)

  def _createFormSkeleton(self, win, bx):
    self.win = win
    self.bx = bx
    self.formBx = self._createContainer()
    self.formBx.bx = self.bx
    self.formBx.generate()

  def generateForm(self, win, bx):
    self._createFormSkeleton(win, bx)

    for name, field in self.fields.items():
      field.renderWidget(self.win, self.formBx.obj)
      self.formBx.addInput(field.widget)

    self.formBx.postGenerate()
    self._changeFormWindowHeight(720)

  def generateFilterForm(self, win, bx):
    self._createFormSkeleton(win, bx)
    optionalMenu = FilterFormLayout(self.win, self.formBx)
    for name, field in self.fields.items():
      if(field.required):
        field.renderWidget(self.win, self.formBx.obj)
        self.formBx.addInput(field.widget)
      else:
        field.renderWidget(self.win, self.formBx.obj)
        optionalMenu.addInput(name, field.widget)

    self.formBx.postGenerate()
    optionalMenu.generate()
    optionalMenu.postGenerate()
    self._changeFormWindowHeight(960)

class StepFormBase(GuiFormBase):
  def _nextBtnClick(self):
    pass

  def generateStepControl(self, *args, **kwargs):
    self.stepControlBox = self._createContainer({"isHorizontal": True, "isWeightExpand": False})
    self.stepControlBox.bx = self.bx
    self.stepControlBox.generate()

    btn = Button()
    btn.win = self.win
    btn.bx = self.stepControlBox.obj
    btn.label = "Cancel"
    self.stepControlBox.addWidget(btn)

    if(hasattr(self, "_backBtnClick")):
      btn = Button()
      btn.win = self.win
      btn.bx = self.stepControlBox.obj
      btn.label = "Back"
      btn._clicked = self._backBtnClick
      self.stepControlBox.addWidget(btn)

    btn = Button()
    btn.win = self.win
    btn.bx = self.stepControlBox.obj
    btn.label = "Next"
    btn._clicked = self._nextBtnClick
    self.stepControlBox.addWidget(btn)

    self.stepControlBox.postGenerate()

class CommandFormBase(StepFormBase):
  def _nextBtnClick(self):
    self._run()

  def _run(self):
    pass

  def fillFields(self, cmdModel, args, kwargs):
    cmdArgs = [i for i in cmdModel.param if(not i.isOptional)]
    if(args!=[]):
      for i in range(len(cmdArgs)):
        try:
          self.fields[cmdArgs[i].name].initData = args[i]
        except IndexError:
          # This means the number of param given unmatch the number of param register in *.command
          raise CommandSyntaxError
    for k,v in kwargs.iteritems():
      self.fields[k].initData = v

class Form(FormBase):
  """A collection of Fields, plus their associated data."""
  # This is a separate class from BaseForm in order to abstract the way
  # self.fields is specified. This class (Form) is the one that does the
  # fancy metaclass stuff purely for the semantic sugar -- it allows one
  # to define a form using declarative syntax.
  # BaseForm itself has no way of designating self.fields.
  __metaclass__ = DeclarativeFieldsMetaclass

class GuiForm(GuiFormBase):
  __metaclass__ = DeclarativeFieldsMetaclass

class StepForm(StepFormBase):
  __metaclass__ = DeclarativeFieldsMetaclass

class CommandForm(CommandFormBase):
  __metaclass__ = DeclarativeFieldsMetaclass
