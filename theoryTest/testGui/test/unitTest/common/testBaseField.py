# -*- coding: utf-8 -*-
##### System wide lib #####
from collections import OrderedDict

##### Theory lib #####
from theory.apps.model import Adapter, Command
from theory.core.exceptions import ValidationError
from theory.gui.common.baseField import *
from theory.test.testcases import TestCase

##### Theory third-party lib #####

##### Local app #####

##### Theory app #####

##### Misc #####
from testGui.test.integrationTest.etk.testDummyEnv import getDummyEnv

__all__ = (
    'ListFieldTestCase',
    'QuerysetFieldTestCase'
    )

class ListFieldTestCase(TestCase):
  fixtures = ["adapter",]

  def __init__(self, *args, **kwargs):
    super(ListFieldTestCase, self).__init__(*args, **kwargs)
    (dummyWin, self.dummyBx) = getDummyEnv()
    self.uiParam=OrderedDict([
        ("win", dummyWin),
        ("bx", self.dummyBx.obj),
        ("unFocusFxn", lambda: True)
        ])

  def setUp(self):
    pass

  def testWithBinaryField(self):
    f = ListField(BinaryField(),initData=(b"11", b"10"))
    self.dummyBx.generate()
    self.dummyBx.postGenerate()
    self.assertEqual(f.clean(f.finalData), [b"11", b"10"])

"""
Have to rewrite the QuerysetField
class QuerysetFieldTestCase(TestCase):
  def __init__(self, *args, **kwargs):
    super(QuerysetFieldTestCase, self).__init__(*args, **kwargs)
    (dummyWin, self.dummyBx) = getDummyEnv()
    self.uiParam=OrderedDict([
        ("win", dummyWin),
        ("bx", self.dummyBx.obj),
        ("unFocusFxn", lambda: True)
        ])

  def testFinalDataWithWidgetWithImport(self):
    queryset = Adapter.objects.all()
    f = QuerysetField(
        autoImport=True,
        app="theory.apps",
        model="Adapter",
        initData=queryset
        )
    self.dummyBx.generate()
    self.dummyBx.postGenerate()
    self.assertEqual(f.clean(f.finalData), queryset)

    queryset = ["invalidId", "invalidId2"]
    f = QuerysetField(
        autoImport=True,
        app="theory.apps",
        model="Adapter",
        initData=queryset
        )
    self.dummyBx.generate()
    self.dummyBx.postGenerate()
    self.assertRaises(ValidationError, f.clean, f.finalData)

  def testFinalDataWithWidgetWithoutImport(self):
    queryset = ["invalidId", "invalidId2"]
    f = QuerysetField(
        app="theory.apps",
        model="Adapter",
        initData=queryset
        )
    self.dummyBx.generate()
    self.dummyBx.postGenerate()
    self.assertEqual(f.clean(f.finalData), queryset)

  def testFinalDataWithoutWidgetWithImport(self):
    # This is wrong
    queryset = Adapter.objects.all()

    f = QuerysetField(
        autoImport=True,
        app="theory.apps",
        model="Adapter",
        initData=queryset
        )
    self.assertEqual(f.clean(f.finalData), queryset)


    queryset = ["invalidId", "invalidId2"]
    f = QuerysetField(
        autoImport=True,
        app="theory.apps",
        model="Adapter",
        initData=queryset
        )
    self.assertRaises(ValidationError, f.clean, f.finalData)

  def testFinalDataWithoutWidgetWithoutImport(self):
    queryset = ["invalidId", "invalidId2"]

    f = QuerysetField(
        app="theory.apps",
        model="Adapter",
        initData=queryset
        )
    self.assertEqual(f.clean(f.finalData), queryset)

  #def testFinalDataWithWidgetWithImport(self):
  #  idLst = [str(i.id) for i in Command.objects.all()]
  #  f = QuerysetField(
  #      autoImport=True,
  #      app="theory",
  #      model="Adapter",
  #      initData=idLst
  #      )
  #  self.dummyBx.generate()
  #  self.dummyBx.postGenerate()
  #  self.assertEqual(f.finalData, Command.objects.all())
"""
