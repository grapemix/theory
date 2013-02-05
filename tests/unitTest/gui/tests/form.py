# -*- coding: utf-8 -*-
##### System wide lib #####
from ludibrio import Stub

##### Theory lib #####
from theory.gui.form import *
from theory.gui.form import FormBase
from theory.utils import unittest

##### Theory third-party lib #####

##### Local app #####

##### Theory app #####

##### Misc #####

__all__ = ('FormBaseTestCase', 'GuiFormBaseTestCase', \
    'StepFormBaseTestCase', )

class FormBaseTestCase(unittest.TestCase):
  def setUp(self):
    pass

  #def testPlainForm(self):
  #  FormBase()

  #def testPlainFormIsValid(self):
  #  form = FormBase()
  #  form.is_valid()

  #def testPlainFormHasChanged(self):
  #  form = FormBase()
  #  self.assertFalse(form.has_changed())

  #def testPlainFormClean(self):
  #  form = FormBase()
  #  print form.clean()

class GuiFormBaseTestCase(unittest.TestCase):
  pass

class StepFormBaseTestCase(unittest.TestCase):
  pass

