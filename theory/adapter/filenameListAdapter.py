# -*- coding: utf-8 -*-
#!/usr/bin/env python
##### System wide lib #####

##### Theory lib #####

##### Theory third-party lib #####

##### Local app #####
from .terminalAdapter import TerminalAdapter

##### Theory app #####

##### Misc #####


class FilenameListAdapter(TerminalAdapter):
  @property
  def files(self):
    return self._files

  @files.setter
  def files(self, files):
    self._files = files


