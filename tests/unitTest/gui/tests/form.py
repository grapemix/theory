# -*- coding: utf-8 -*-
##### System wide lib #####
from ludibrio import Stub

##### Theory lib #####
from theory.gui.form import *
from theory.utils import unittest

##### Theory third-party lib #####

##### Local app #####

##### Theory app #####

##### Misc #####
from tests.testBase.form.combinatoryFormFactory import CombinatoryFormFactory

__all__ = (
    'FormBaseTestCase',
    'CombinatoryFormTestCase',
    )

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

class CombinatoryFormTestCase(unittest.TestCase):
  def setUp(self):
    self.factory = CombinatoryFormFactory()
    self.form = self.factory.getCombinatoryFormWithDefaultValue()

  def testFormValidateWithDefaultValue(self):
    self.assertTrue(self.form.is_valid())


