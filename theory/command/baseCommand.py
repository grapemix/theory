# -*- coding: utf-8 -*-
#!/usr/bin/env python
##### System wide lib #####
from abc import ABCMeta, abstractmethod
from celery import Task
from theory.gui import field
from theory.gui.form import CommandForm, Form

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
  params = [] # TODO: del me
  paramForm = None

  # Make sure there has no attribute's name is the same as the notations
  # and gongs' class because theory will initialize the class and assign
  # the available notations and gongs as attribute of the command in the camel
  # case with the first lower char. e.x.: FilenameList -> filenameList;
  # FilefileObjectList -> fileObjectList

  _verbosity = 1
  _gongs = []
  _notations = []
  _drums = {}
  # stderr should be seen in lig file

  def __init__(self, *args, **kwargs):
    pass
  #  super(_BaseCommand, self).__init__(*args, **kwargs)

  # Objective of attribute:
  # 1) Declare the input and the output of commands
  # 2) Store the comment of the attribute
  # 3) Get the type of attribute programatically
  # 4) Allow the attribute inheritance through class inheritance
  # 5) Declare the required field and the sequence of required field
  # 6) Given the initial data even the data is generated dynamically
  # 7) Work with celery
  # 8) For static field, data of field don't have to being accessed when importing class.
  # 9) Work with adapter

  class ParamForm(CommandForm):
    verbosity = field.IntegerField(label="verbosity", required=False)
    notations = field.ListField(field.AdapterField(), label="notations", required=False)
    gongs = field.ListField(field.AdapterField(), label="gongs", required=False)
    drums = field.DictField(field.AdapterField(), label="drums", required=False)
    concatCommand = field.TextField(label="Concatenated command", required=False, help_text="another command being concatenated to this command")

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
    :param gongs: The choice order of output adapter
    :type gongs: List(Adapter)
    """
    self._gongs = gongs

  @property
  def drums(self):
    return self._drums

  @drums.setter
  def drums(self, drums):
    """
    :param drums: The group of UI being called in different debug level
    :type drums: Dict(Adapter)
    """
    self._drums = drums

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
  def status(self):
    return self._status

  @abstractmethod
  def run(self):
    pass

  class ParamForm(_BaseCommand.ParamForm):
    pass

class AsyncCommand(Task, _BaseCommand):
  """
  We have to program differently. All input can be only retrieved from the
  dictionary of **kwargs and all states have to store in DB. In other words,
  no class variable should be read and written before and after the run().
  """
  abstract = True

  @abstractmethod
  def run(self):
    pass

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

  def run(self, cmdObj, adapterInput):
    cmdObj.run()
    return self.extractResult(cmdObj, adapterInput)
