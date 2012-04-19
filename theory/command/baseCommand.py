# -*- coding: utf-8 -*-
##### System wide lib #####
from abc import ABCMeta, abstractmethod

##### Theory lib #####

##### Theory third-party lib #####

##### Local app #####

##### Theory app #####

##### Misc #####

##
#
# All property with setters will be treated as an optional keyword parameter
# for the command(**kwargs). If the properties are set in params property, the
# properties will be treated as mandatory parameters (*args) in order. The type
# and description should also be reflected in the tooltip/autocomplete feature.
#
class BaseCommand(object):
  """
  All commands should directly/indirectly derive from this class.
  Please try to design with the bridge pattern and test oriented pattern.
  """
  __metaclass__ = ABCMeta
  name = None
  verboseName = None
  params = []

  # Make sure there has no attribute's name is the same as the notations
  # and gongs' class because theory will initialize the class and assign
  # the available notations and gongs as attribute of the command in the camel
  # case with the first lower char. e.x.: FilenameList -> filenameList;
  # FilefileObjectList -> fileObjectList

  _progress = 0.0
  _status = ""
  _stdOut = ""
  _stdRowOut = []
  _verbosity = 1
  _gongs = []
  _notations = []
  # stderr should be seen in lig file

  def __init__(self, *args, **kwargs):
    super(BaseCommand, self).__init__(*args, **kwargs)

  @property
  def stdOut(self):
    return self._stdOut

  @property
  def stdRowOut(self):
    return self._stdRowOut

  @property
  def status(self):
    return self._status

  @property
  def progress(self):
    return self._progress

  @property
  def verbosity(self):
    return self._verbosity

  @verbosity.setter
  def verbosity(self, verbosity):
    self._verbosity = verbosity

  @property
  def notations(self):
    return self._notations

  ##
  # @param notations List[type<Adapter>]
  #
  @notations.setter
  def notations(self, notations):
    self._notations = notations

  @property
  def gongs(self):
    return self._gongs

  ##
  # @param gongs List[type<Adapter>]
  #
  @gongs.setter
  def gongs(self, gongs):
    self._gongs = gongs

  def validate(self, *args, **kwargs):
    for i in ["name", "verboseName",]:
      if(getattr(self, i)==None):
        return False
    return True

  def _run(self, *args, **kwargs):
    # TODO: integrate signal
    #signals.pre_run.send(instance=self)
    self.run(*args, **kwargs)
    #signals.post_run.send(instance=self)

  @abstractmethod
  def run(self, *args, **kwargs):
    pass

  def stop(self, *args, **kwargs):
    pass
