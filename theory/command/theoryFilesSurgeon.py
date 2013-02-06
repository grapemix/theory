# -*- coding: utf-8 -*-
#!/usr/bin/env python
##### System wide lib #####
from abc import ABCMeta, abstractmethod
import codecs
import os
from shutil import move

##### Theory lib #####
from theory.gui import field

##### Theory third-party lib #####

##### Local app #####
from .baseCommand import SimpleCommand
from .filenameScanner import FilenameScanner

##### Theory app #####

##### Misc #####

class TheoryFilesSurgeon(SimpleCommand):
  """
  An abstract class served as an wrapper file for commands which modify the
  filenameLst within the theory project.
  """
  __metaclass__ = ABCMeta
  name = "theory Files Surgeon"
  verboseName = "theory Files' Surgeon"
  params = []
  _filenameLst = []

  class ParamForm(SimpleCommand.ParamForm):
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

    writtenMode = field.ChoiceField(label="Written Mood", \
        help_text="The way to write the changes", \
        choices=WRITTEN_MODE_CHOICES, \
        initData=WRITTEN_MODE_COPY,\
        )

  #def __init__(self, *args, **kwargs):
  #  super(TheoryFilesSurgeon, self).__init__(*args, **kwargs)

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
    self.filenameScanner = FilenameScanner()
    self.filenameScanner.rootLst=[os.path.dirname(os.path.dirname(__file__)),]
    self.filenameScanner.includeFileExtLst = [".py",]
    self.filenameScanner.excludeFileFxnLst = [lambda x: True,]
    self.filenameScanner.depth = -1
    self.filenameScanner.run()
    self.filenameLst = self.filenameScanner.filenameLst

  def postGetFiles(self, *args, **kwargs):
    pass

  def run(self, *args, **kwargs):
    self.preGetFiles()
    self.getFiles()
    self.postGetFiles()
    for filename in self.filenameLst:
      lines = self.preAction(filename)
      newLines = self.action(lines)
      self.postAction(newLines, filename)

  def _writeToFile(self, lines, oldFilename):
    writtenMode = int(self.paramForm.clean_data["writtenMode"])
    if(writtenMode==self.paramForm.WRITTEN_MODE_COPY):
      move(oldFilename, oldFilename + ".orig")
    elif(writtenMode==self.paramForm.WRITTEN_MODE_DRY_RUN):
      return
    elif(writtenMode==self.paramForm.WRITTEN_MODE_DRY_RUN_PRINT):
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
  def filenameLst(self):
    return self._filenameLst

  @filenameLst.setter
  def filenameLst(self, filenameLst):
    self._filenameLst = filenameLst
