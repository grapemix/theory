# -*- coding: utf-8 -*-
##### System wide lib #####

##### Theory lib #####
from theory.gui.form import *
from theory.test.testcases import TestCase

##### Theory third-party lib #####

##### Local app #####

##### Theory app #####

##### Misc #####
from testBase.form.combinatoryFormFactory import CombinatoryFormFactory

__all__ = (
    'FormBaseTestCase',
    'CombinatoryFormTestCase',
    )

class FormBaseTestCase(TestCase):
  def setUp(self):
    pass

  #def testPlainForm(self):
  #  FormBase()

  #def testPlainFormIsValid(self):
  #  form = FormBase()
  #  form.isValid()

  #def testPlainFormHasChanged(self):
  #  form = FormBase()
  #  self.assertFalse(form.has_changed())

  #def testPlainFormClean(self):
  #  form = FormBase()
  #  print form.clean()

class CombinatoryFormTestCase(TestCase):
  fixtures = ["theory",]

  def setUp(self):
    self.factory = CombinatoryFormFactory()
    self.form = self.factory.getCombinatoryFormWithDefaultValue()

  def testFormValidateWithDefaultValue(self):
    self.assertTrue(self.form.isValid(), self.form._errors)

  def testFormToJson(self):
    self.form.isValid()
    # Just to see if toJson throw errors, should compare the result in the
    # future
    self.form.toJson()

