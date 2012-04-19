# -*- coding: utf-8 -*-
#!/usr/bin/env python
# -*- coding: utf-8 -*-
##### System wide lib #####
from abc import ABCMeta, abstractmethod
import codecs
import os
from shutil import move

##### Theory lib #####

##### Theory third-party lib #####

##### Local app #####
from .baseCommand import BaseCommand
from .fileSelector import FileSelector

##### Theory app #####

##### Misc #####

class TheoryFilesSurgeon(BaseCommand):
  """
  An abstract class served as an wrapper file for commands which modify the
  files within the theory project.
  """
  __metaclass__ = ABCMeta
  name = "theory Files Surgeon"
  verboseName = "theory Files' Surgeon"
  params = []
  _files = []

  WRITTEN_MODE_COPY = 1
  WRITTEN_MODE_REPLACE = 2
  WRITTEN_MODE_DRY_RUN = 3
  WRITTEN_MODE_DRY_RUN_PRINT = 4

  WRITTEN_MODE_CHOICES = (
      (WRITTEN_MODE_COPY, "Copy"),
      (WRITTEN_MODE_REPLACE, "Replace"),
      (WRITTEN_MODE_DRY_RUN, "Dry run"),
      (WRITTEN_MODE_DRY_RUN_PRINT, "Dry run and print"),
  )
  _writtenMode = WRITTEN_MODE_COPY

  def __init__(self, *args, **kwargs):
    super(TheoryFilesSurgeon, self).__init__(*args, **kwargs)

  def preAction(self, filename, *args, **kwargs):
    return self._readFileLine(filename)

  def postAction(self, newLines, filename, *args, **kwargs):
    return self._writeToFile(newLines, filename)

  @abstractmethod
  def action(self, lines, *args, **kwargs):
    pass

  def preGetFiles(self, *args, **kwargs):
    pass

  def getFiles(self, *args, **kwargs):
    self.fileSelector = FileSelector()
    self.fileSelector.roots=[os.path.dirname(os.path.dirname(__file__)),]
    self.fileSelector.includeFilesExt = ["py",]
    self.fileSelector.excludeFxns = [lambda x: True,]
    self.fileSelector.depth = -1
    self.fileSelector.run()
    self.files = self.fileSelector.files

  def postGetFiles(self, *args, **kwargs):
    pass

  def run(self, *args, **kwargs):
    self.preGetFiles()
    self.getFiles()
    self.postGetFiles()
    for filename in self.files:
      lines = self.preAction(filename)
      newLines = self.action(lines)
      self.postAction(newLines, filename)

  def _writeToFile(self, lines, oldFilename):
    if(self.writtenMode==self.WRITTEN_MODE_COPY):
      move(oldFilename, oldFilename + ".orig")
    elif(self.writtenMode==self.WRITTEN_MODE_DRY_RUN):
      return
    elif(self.writtenMode==self.WRITTEN_MODE_DRY_RUN_PRINT):
      self._stdOut += lines + "<br/>"
      return
    fileObj = open(oldFilename,"w")
    #fileObj.writelines(lines)
    lines = "\n".join(lines)
    fileObj.write(lines)
    fileObj.close()

  def _readFileLine(self, loc, type="list", enc="utf-8"):
    if(enc==""):
      fileObj = codecs.open(loc, "r")
    else:
      fileObj = codecs.open(loc, "r", "utf-8")
    if(type=="str"):
      s = fileObj.read()
    else:
      s = fileObj.read().split("\n")
      #if(len(s)>1):
      #  del s[-1]
    fileObj.close()
    return s

  @property
  def files(self):
    return self._files

  @files.setter
  def files(self, files):
    self._files = files

  @property
  def writtenMode(self):
    return self._writtenMode

  @writtenMode.setter
  def writtenMode(self, writtenMode):
    self._writtenMode = writtenMode

