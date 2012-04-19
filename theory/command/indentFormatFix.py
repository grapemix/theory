# -*- coding: utf-8 -*-
#!/usr/bin/env python
##### System wide lib #####
import codecs
from shutil import move

##### Theory lib #####

##### Theory third-party lib #####

##### Local app #####
from .baseCommand import BaseCommand

##### Theory app #####

##### Misc #####

class IndentFormatFix(BaseCommand):
  """
  Fixing the indent of python source files, but this command
  can only convert the 4 space into 2 space or vice versa in this version
  """
  name = "indentFormatFix"
  verboseName = "indent Format Fix"
  params = []
  _indentSpace = 2
  _files = []

  def __init__(self, *args, **kwargs):
    super(IndentFormatFix, self).__init__(*args, **kwargs)

  def run(self, *args, **kwargs):
    for filename in self.files:
      lines = self._readFileLine(filename)
      newLines = self._forceHalfIndent(lines)
      #newLines = self._convertDjango(lines)
      self._writeToFile(newLines, filename)

  def _writeToFile(self, lines, oldFilename):
    move(oldFilename, oldFilename + ".orig")
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

  # Todo: remove this fxn
  def _convertDjango(self, lines):
    newLines = []
    for i in lines:
      j = i.replace("Django", "Theory")
      j = j.replace("django", "theory")
      j = j.replace("DJANGO", "THEORY")
      newLines.append(j)
    return newLines

  def _forceHalfIndent(self, lines):
    newLines = []
    for line in lines:
      i = j = 0
      for j in range(len(line)):
        if(line[j]!=u" "):
          i = j
          break
      newLines.append(line[j/2:])
    return newLines

  @property
  def files(self):
    return self._files

  @files.setter
  def files(self, files):
    self._files = files

  @property
  def indentSpace(self):
    return self._indentSpace

  @indentSpace.setter
  def indentSpace(self, indentSpace):
    self._indentSpace = indentSpace

