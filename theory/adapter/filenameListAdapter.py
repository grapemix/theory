# -*- coding: utf-8 -*-
##### System wide lib #####

##### Theory lib #####

##### Theory third-party lib #####

##### Local app #####
from .terminalAdapter import TerminalAdapter

##### Theory app #####

##### Misc #####


class FilenameListAdapter(TerminalAdapter):
  """
  def stdOutPacker(self):
    return self._files

  def postStdOutPacker(self, files):
    return self._stdOutLineBreak.join(files)
  """

  def stdRowOutPacker(self):
    return self._files

  @property
  def files(self):
    return self._files

  @files.setter
  def files(self, files):
    self._files = files


