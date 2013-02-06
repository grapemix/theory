# -*- coding: utf-8 -*-
#!/usr/bin/env python
##### System wide lib #####
import codecs
from shutil import move

##### Theory lib #####
from theory.gui import field

##### Theory third-party lib #####

##### Local app #####
from .baseCommand import SimpleCommand

##### Theory app #####

##### Misc #####

class IndentFormatFix(SimpleCommand):
  """
  Fixing the indent of python source fileLst, but this command
  can only convert the 4 space into 2 space or vice versa in this version
  """
  name = "indentFormatFix"
  verboseName = "Indent Format Fix"
  _indentSpace = 2

  class ParamForm(SimpleCommand.ParamForm):
    filenameLst = field.ListField(field.TextField(), label="The list of filenames being fixed")
    #fileLst = field.ListField(field.FileField(), label="The list of files being fixed")

  #def __init__(self, *args, **kwargs):
  #  super(IndentFormatFix, self).__init__(*args, **kwargs)

  def run(self, *args, **kwargs):
    for filename in self.paramForm.cleaned_data["filenameLst"]:
      lines = self._readFileLine(filename)
      lines = self._forceHalfIndent(lines)
      lines = self._convertDjango(lines)
      self._writeToFile(lines, filename)

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
  def indentSpace(self):
    return self._indentSpace

  @indentSpace.setter
  def indentSpace(self, indentSpace):
    """
    :param indentSpace: The space of indent in front of every line.
    :type indentSpace: integer
    """
    self._indentSpace = indentSpace

