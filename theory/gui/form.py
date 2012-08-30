# -*- coding: utf-8 -*-
#!/usr/bin/env python

##### System wide lib #####
from abc import ABCMeta, abstractmethod
import copy

##### Theory lib #####
from theory.gui.field import *
from theory.utils.datastructures import SortedDict
from theory.gui.widget import *
from theory.gui.widget import BasePacker
from theory.gui.e17.widget import *

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
  def __init__(self, *args, **kwargs):
    super(FormBase, self).__init__(*args, **kwargs)
    # The base_fields class attribute is the *class-wide* definition of
    # fields. Because a particular *instance* of the class might want to
    # alter self.fields, we create self.fields here by copying base_fields.
    # Instances should always modify self.fields; they should not modify
    # self.base_fields.
    self.fields = copy.deepcopy(self.base_fields)

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

class GuiFormBase(FormBase, BasePacker):
  def __init__(self, win, bx, *args, **kwargs):
    super(GuiFormBase, self).__init__(win, bx,*args, **kwargs)
    self.isContainerAFrame = False
    self.formBx = self._createContainer()
    self.formBx.bx = bx
    self.formBx.generate()

  def generateForm(self, *args, **kwargs):
    for name, field in self.fields.items():
      field.renderWidget(self.win, self.formBx.obj)
      self.formBx.addInput(field.widget)

    self.formBx.postGenerate()

class StepFormBase(GuiFormBase):
  def _nextBtnClick(self):
    pass

  def generateStepControl(self, *args, **kwargs):
    self.stepControlBox = self._createContainer({"isHorizontal": True, "isWeightExpand": False})
    self.stepControlBox.bx = self.bx
    #self.stepControlBox.attrs["isHorizontal"] = True
    #self.stepControlBox.attrs["isWeightExpand"] = False
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

class Form(FormBase):
  "A collection of Fields, plus their associated data."
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
