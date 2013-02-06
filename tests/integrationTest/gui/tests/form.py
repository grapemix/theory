# -*- coding: utf-8 -*-
##### System wide lib #####
import copy
from ludibrio import Stub

##### Theory lib #####
from theory.conf import settings
from theory.gui import field
from theory.gui import widget
from theory.gui.form import *
from theory.utils import unittest

##### Theory third-party lib #####

##### Local app #####

##### Theory app #####

##### Misc #####

__all__ = ('StepFormTestCase',)

class FormCombinator(object):
  def __init__(self, formKlass):
    self.formKlass = formKlass

  def dummyField(self):
    return field.ListField(field.TextField(label="a", widget=widget.StringInput), initData=["1", "2", "tt"])

  def genOneFieldForm(self):
    formKlass = copy.deepcopy(self.formKlass)
    setattr(formKlass, "field1", self.dummyField())
    return formKlass

class StepFormTestCase(unittest.TestCase):
  class TestFormTemplate(StepForm):
    pass

  def __init__(self, *args, **kwargs):
    super(StepFormTestCase, self).__init__(*args, **kwargs)
    self.formCombinator = FormCombinator(self.TestFormTemplate)
    self.uiParam={"win": settings.CRTWIN, "bx": settings.CRT}

  def setUp(self):
    self.uiParam["bx"].clear()

  def btnCallback(self, btn):
    if(self.testForm.is_valid()):
      print self.testForm.clean()["d"]

  def _renderForm(self, *args, **kwargs):
    win = self.uiParam["win"]
    bx = self.uiParam["bx"]
    o = self.formCombinator.genOneFieldForm()()
    o._nextBtnClick = self.btnCallback
    #o.generateFilterForm(win, bx)
    o.generateForm(win, bx)
    o.generateStepControl()

  def _getMockCommandObject(self, cmd, classImportPath):
    with Stub(proxy=cmd) as cmd:
      cmd.classImportPath >> "%s.%s" % (self.__module__, classImportPath)
    return cmd

  def testRenderForm(self):
    self.testForm = self._renderForm()
