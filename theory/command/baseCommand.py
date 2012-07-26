# -*- coding: utf-8 -*-
#!/usr/bin/env python
##### System wide lib #####
from abc import ABCMeta, abstractmethod
from celery.task import Task

##### Theory lib #####

##### Theory third-party lib #####

##### Local app #####

##### Theory app #####

##### Misc #####

__all__ = ("SimpleCommand", "AsyncCommand", )

class _BaseCommand(object):
  """
  All commands should directly/indirectly derive from this class.
  Please try to design with the bridge pattern and test oriented pattern.

  All property with setters will be treated as an optional keyword parameter
  for the command(**kwargs). If the properties are set in params property, the
  properties will be treated as mandatory parameters (*args) in order. The type
  and description should also be reflected in the tooltip/autocomplete feature.

  """
  #abstract = True
  name = None
  verboseName = None
  params = []

  # Make sure there has no attribute's name is the same as the notations
  # and gongs' class because theory will initialize the class and assign
  # the available notations and gongs as attribute of the command in the camel
  # case with the first lower char. e.x.: FilenameList -> filenameList;
  # FilefileObjectList -> fileObjectList

  _verbosity = 1
  _gongs = []
  _notations = []
  # stderr should be seen in lig file

  def __init__(self, *args, **kwargs):
    pass
  #  super(_BaseCommand, self).__init__(*args, **kwargs)

  @property
  def verbosity(self):
    return self._verbosity

  @verbosity.setter
  def verbosity(self, verbosity):
    self._verbosity = verbosity

  @property
  def notations(self):
    return self._notations

  @notations.setter
  def notations(self, notations):
    """
    :param notations: The choice order of input adapter
    :type notations: List(Adapter)
    """
    self._notations = notations

  @property
  def gongs(self):
    return self._gongs

  @gongs.setter
  def gongs(self, gongs):
    """
    :param notations: The choice order of output adapter
    :type notations: List(Adapter)
    """
    self._gongs = gongs

  def validate(self, *args, **kwargs):
    for i in ["name", "verboseName",]:
      if(getattr(self, i)==None):
        return False
    return True

class SimpleCommand(_BaseCommand):
  __metaclass__ = ABCMeta

  _status = ""
  _stdOut = ""
  _stdRowOut = []

  @property
  def stdOut(self):
    return self._stdOut

  @property
  def stdRowOut(self):
    return self._stdRowOut

  @property
  def status(self):
    return self._status

  @abstractmethod
  def run(self, *args, **kwargs):
    pass

'''
class SeqCommand(_BaseCommand):
  _step = 0

  @property
  def formLst(self):
    return self._formLst

  @formLst.setter
  def formLst(self, formLst):
    """
    :param notations: The list of form being called in sequence
    :type notations: List(Form)
    """
    self._formLst = formLst

  @property
  def cmdLst(self):
    return self._cmdLst

  @cmdLst.setter
  def cmdLst(self, cmdLst):
    """
    :param notations: The list of command being called in sequence
    :type notations: List(Command)
    """
    self._cmdLst = cmdLst

  def run(self, *args, **kwargs):
    pass
'''

class AsyncCommand(Task, _BaseCommand):
  """
  We have to program differently. All input can be only retrieved from the
  dictionary of **kwargs and all states have to store in DB. In other words,
  no class variable should be read and written before and after the run().
  """
  abstract = True

class AsyncContainer(Task):
  """
  Normal users should not used this class.
  """

  # Warning: Try not to override this fxn
  def extractResult(self, inst, adapterInput):
    result = {}
    for property in adapterInput:
      result[property] = getattr(inst, property)
    return result

  def run(self, inst, adapterInput):
    inst.run()
    return self.extractResult(inst, adapterInput)
