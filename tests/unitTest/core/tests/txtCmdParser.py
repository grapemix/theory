# -*- coding: utf-8 -*-
##### System wide lib #####

##### Theory lib #####
from theory.core.cmdParser.txtCmdParser import TxtCmdParser
from theory.utils import unittest

##### Theory third-party lib #####

##### Local app #####

##### Theory app #####

##### Misc #####

__all__ = ('CmdParserTestCase',)

class CmdParserTestCase(unittest.TestCase):
  def setUp(self):
    self.o = TxtCmdParser()

  def testGettCmdName(self):
    self.o.cmdInTxt = "probeModule()"
    self.o.run()
    self.assertEqual(self.o.cmdName, "probeModule")

  def testGettCmdNameAndArgs(self):

    self.o.cmdInTxt = "probeModule()"
    self.o.run()
    self.assertEqual(self.o.cmdName, "probeModule")
    self.assertEqual(self.o.args, [])
    self.o.initVar()

    self.o.cmdInTxt = "probeModule('a')"
    self.o.run()
    self.assertEqual(self.o.cmdName, "probeModule")
    self.assertEqual(self.o.args, ['a'])
    self.o.initVar()


    self.o.cmdInTxt = "probeModule(1,2,3)"
    self.o.run()
    self.assertEqual(self.o.cmdName, "probeModule")
    self.assertEqual(self.o.args, ['1', '2', '3'])
    self.o.initVar()

    self.o.cmdInTxt = "probeModule( 1, 2 , 3 )"
    self.o.run()
    self.assertEqual(self.o.cmdName, "probeModule")
    self.assertEqual(self.o.args, ['1', '2', '3'])
    self.o.initVar()

    self.o.cmdInTxt = "probeModule( 1 , '2' ,  3 )"
    self.o.run()
    self.assertEqual(self.o.cmdName, "probeModule")
    self.assertEqual(self.o.args, ['1', '2', '3'])
    self.o.initVar()

    self.o.cmdInTxt = """probeModule('alpha', 'beta' , 'gamma' )"""
    self.o.run()
    self.assertEqual(self.o.cmdName, "probeModule")
    self.assertEqual(self.o.args, ['alpha', 'beta', 'gamma'])
    self.o.initVar()

    self.o.cmdInTxt = '''probeModule("alpha", "beta" , "gamma" )'''
    self.o.run()
    self.assertEqual(self.o.cmdName, "probeModule")
    self.assertEqual(self.o.args, ['alpha', 'beta', 'gamma'])
    self.o.initVar()

  def testGettCmdNameAndKwargs(self):
    self.o.cmdInTxt = "probeModule(a=1, b=2, c=3)"
    self.o.run()
    self.assertEqual(self.o.cmdName, "probeModule")
    self.assertEqual(self.o._kwargs, {'a': '1', 'c': '3', 'b': '2'})

    self.o.initVar()

    self.o.cmdInTxt = '''probeModule(a=1,b=2,c=3)'''
    self.o.run()
    self.assertEqual(self.o.cmdName, "probeModule")
    self.assertEqual(self.o._kwargs, {'a': '1', 'c': '3', 'b': '2'})

    self.o.initVar()

    self.o.cmdInTxt = '''probeModule(  a = 1, b =2, c  =3)'''
    self.o.run()
    self.assertEqual(self.o.cmdName, "probeModule")
    self.assertEqual(self.o._kwargs, {'a': '1', 'c': '3', 'b': '2'})

    self.o.initVar()

    self.o.cmdInTxt = '''probeModule(a="alpha", b="beta" , c="gamma")'''
    self.o.run()
    self.assertEqual(self.o.cmdName, "probeModule")
    self.assertEqual(self.o._kwargs, {'a': 'alpha', 'c': 'gamma', 'b': 'beta'})

    self.o.initVar()

    self.o.cmdInTxt = """probeModule(a='alpha', b='beta' , c='gamma' )"""
    self.o.run()
    self.assertEqual(self.o.cmdName, "probeModule")
    self.assertEqual(self.o._kwargs, {'a': 'alpha', 'c': 'gamma', 'b': 'beta'})

  def testSingleChar(self):
    self.o.cmdInTxt = "a"
    self.o.run()
    self.assertEqual(self.o.mode, self.o.MODE_COMMAND)

  def testEmptyMode(self):
    self.o.cmdInTxt = ""
    self.o.run()
    self.assertEqual(self.o.mode, self.o.MODE_EMPTY)

  def testCmdMode(self):
    self.o.cmdInTxt = "probeM"
    self.o.run()
    self.assertEqual(self.o.mode, self.o.MODE_COMMAND)

  def testParamMode(self):
    self.o.cmdInTxt = "probeModule(1"
    self.o.run()
    self.assertEqual(self.o.mode, self.o.MODE_ARGS)
    self.o.initVar()

    self.o.cmdInTxt = "probeModule(1, "
    self.o.run()
    self.assertEqual(self.o.mode, self.o.MODE_ARGS)
    self.o.initVar()

    self.o.cmdInTxt = "probeModule(1, "
    self.o.run()
    self.assertEqual(self.o.mode, self.o.MODE_ARGS)
    self.o.initVar()

    """
    self.o.cmdInTxt = "probeModule( a ="
    self.o.run()
    self.assertEqual(self.o.mode, self.o.MODE_KWARGS)
    self.o.initVar()

    self.o.cmdInTxt = "probeModule( a = 1, b ="
    self.o.run()
    self.assertEqual(self.o.mode, self.o.MODE_KWARGS)
    self.o.initVar()

    self.o.cmdInTxt = "probeModule( a = "
    self.o.run()
    self.assertEqual(self.o.mode, self.o.MODE_KWARGS)
    self.o.initVar()
    """

    self.o.cmdInTxt = "probeModule( a = 1"
    self.o.run()
    self.assertEqual(self.o.mode, self.o.MODE_ARGS)
    self.o.initVar()

    self.o.cmdInTxt = """probe'Module( a = 1'"""
    self.o.run()
    self.assertEqual(self.o.mode, self.o.MODE_ERROR)
    self.o.initVar()

    self.o.cmdInTxt = """probeModule( '"""
    self.o.run()
    self.assertEqual(self.o.mode, self.o.MODE_SINGLE_QUOTE)
    self.o.initVar()

    self.o.cmdInTxt = '''probeModule( "'''
    self.o.run()
    self.assertEqual(self.o.mode, self.o.MODE_DOUBLE_QUOTE)
    self.o.initVar()

