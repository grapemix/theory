# -*- coding: utf-8 -*-
##### System wide lib #####
from collections import OrderedDict

##### Theory lib #####
from theory.gui import field
from theory.gui import widget
from theory.gui.formset import *
from theory.test.testcases import TestCase

##### Theory third-party lib #####

##### Local app #####

##### Theory app #####

##### Misc #####
from testGui.test.integrationTest.etk.testDummyEnv import getDummyEnv
from testBase.form.combinatoryFormFactory import CombinatoryFormFactory

__all__ = ('FormsetTestCase',)

class FormsetTestCase(TestCase):
  """
  To test the Formset.
  """
  def __init__(self, *args, **kwargs):
    super(FormsetTestCase, self).__init__(*args, **kwargs)
    (dummyWin, dummyBx) = getDummyEnv()
    self.uiParam=OrderedDict([
        ("win", dummyWin),
        ("bx", dummyBx.obj),
        ("unFocusFxn", lambda: True)
        ])

  def setUp(self):
    self.form = CombinatoryFormFactory().getCombinatoryFormWithDefaultValue()

  def testSetup(self):
    formset = BaseFormSet
    FormSet = formsetFactory(self.form, formset, extra=1, maxNum=1,
                 canOrder=True, canDelete=True,
                 validateMax=1)
