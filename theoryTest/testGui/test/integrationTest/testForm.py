# -*- coding: utf-8 -*-
##### System wide lib #####
from collections import OrderedDict
import copy

##### Theory lib #####
from theory.gui import field
from theory.gui import widget
from theory.gui.etk.form import StepForm
from theory.test.testcases import TestCase

##### Theory third-party lib #####

##### Local app #####

##### Theory app #####

##### Misc #####
from testGui.test.integrationTest.etk.testDummyEnv import getDummyEnv

__all__ = ('FormBaseTestCase', 'StepFormTestCase',)

class FormCombinator(object):
  def __init__(self, formKlass):
    self.formKlass = formKlass

  def dummyField(self):
    return field.ListField(field.TextField(label="a", widget=widget.StringInput), initData=["1", "2", "tt"])

  def genOneFieldForm(self):
    formKlass = copy.deepcopy(self.formKlass)
    setattr(formKlass, "field1", self.dummyField())
    return formKlass

class FormBaseTestCase(TestCase):
  """
  To test the FormBase.
  """
  class TestForm(StepForm):
    initField = field.TextField(initData="test", maxLen=5)
    emptyField = field.TextField()


  def __init__(self, *args, **kwargs):
    super(FormBaseTestCase, self).__init__(*args, **kwargs)
    (dummyWin, dummyBx) = getDummyEnv()
    self.uiParam=OrderedDict([
        ("win", dummyWin),
        ("bx", dummyBx.obj),
        ("unFocusFxn", lambda: True)
        ])

  def setUp(self):
    self.form = self.TestForm()

  def testFullCleanInLazyMode(self):
    self.form.generateForm(*self.uiParam.values())
    self.assertFalse(self.form.isValid())
    self.assertEqual(
        self.form.errors,
        {"emptyField": ["This field is required."]}
    )
    self.assertEqual(self.form.fields["emptyField"]._finalData, None)
    self.form.fields["emptyField"].widget.reset(finalData="test")
    self.form.fields["initField"].widget.reset(finalData="test2")
    self.form.fullClean()
    self.assertTrue(self.form.isValid())
    self.assertEqual(self.form.clean()["emptyField"], "test")
    self.assertEqual(self.form.clean()["initField"], "test")

  def testFullCleanInNonLazyMode(self):
    self.form.generateForm(*self.uiParam.values())
    self.form.isLazy = False
    self.assertFalse(self.form.isValid())
    self.assertEqual(
        self.form.errors,
        {"emptyField": ["This field is required."]}
    )
    self.assertEqual(self.form.fields["emptyField"]._finalData, "")
    self.form.fields["emptyField"].widget.reset(finalData="test")
    self.form.fields["initField"].widget.reset(finalData="test2")
    self.form.fullClean()
    self.assertTrue(self.form.isValid())
    self.assertEqual(self.form.clean()["emptyField"], "test")
    self.assertEqual(self.form.clean()["initField"], "test2")

  def testFullCleanInLazyModeWithInitData(self):
    self.form.generateForm(*self.uiParam.values())
    self.form.fields["initField"].widget.reset(finalData="test22")
    self.form.fields["emptyField"].widget.reset(finalData="test")
    self.form.fullClean()
    self.assertFalse(self.form.isValid())
    self.assertEqual(self.form.fields["initField"]._finalData, None)
    self.form.fields["initField"].widget.reset(finalData="test2")
    self.form.fullClean()
    self.assertTrue(self.form.isValid())

  def testFullCleanInLazyModeWithoutWidget(self):
    self.assertFalse(self.form.isValid())
    self.assertEqual(
        self.form.errors,
        {"emptyField": ["This field is required."]}
    )
    self.assertEqual(self.form.fields["emptyField"].finalData, None)
    self.form.fields["emptyField"].finalData = "test"
    with self.assertRaises(AttributeError):
      self.form.fields["initField"].widget.finalData = "test2"
    self.form.fullClean()
    self.assertTrue(self.form.isValid())
    self.assertEqual(self.form.clean()["emptyField"], "test")
    self.assertEqual(self.form.clean()["initField"], "test")

class StepFormTestCase(TestCase):
  class TestFormTemplate(StepForm):
    pass

  def __init__(self, *args, **kwargs):
    super(StepFormTestCase, self).__init__(*args, **kwargs)
    self.formCombinator = FormCombinator(self.TestFormTemplate)
    (dummyWin, dummyBx) = getDummyEnv()
    dummyBx.generate()
    self.uiParam=OrderedDict([
        ("win", dummyWin),
        ("bx", dummyBx.obj),
        ("unFocusFxn", lambda: True)
        ])


  def setUp(self):
    self.uiParam["bx"].clear()

  def btnCallback(self, btn):
    if(self.testForm.isValid()):
      pass

  def _renderForm(self, *args, **kwargs):
    o = self.formCombinator.genOneFieldForm()()
    o._nextBtnClick = self.btnCallback
    #o.generateFilterForm(win, bx)
    o.generateForm(*self.uiParam.values())
    o.generateStepControl()

  def _getMockCommandObject(self, cmd, classImportPath):
    with Stub(proxy=cmd) as cmd:
      cmd.classImportPath >> "%s.%s" % (self.__module__, classImportPath)
    return cmd

  def testRenderForm(self):
    self.testForm = self._renderForm()
