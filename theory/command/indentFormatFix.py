# -*- coding: utf-8 -*-
#!/usr/bin/env python
##### System wide lib #####
import codecs
import re
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

    filenameLst = field.ListField(
        field.FilePathField(initData="/home/kingston/formset.py"),
        label="The list of filenames being fixed"
    )
    writtenMode = field.ChoiceField(label="Written Mood",
        help_text="The way to write the changes",
        choices=WRITTEN_MODE_CHOICES,
        initData=WRITTEN_MODE_DRY_RUN_PRINT,
    )
    isReplaceCamalCase = field.BooleanField(
        label="Is replace camal case",
        initData=True,
    )

  def run(self):
    self.formData = self.paramForm.clean()
    for fileObj in self.formData["filenameLst"]:
      lines = self._readFileLine(fileObj.filepath)
      lines = self._forceHalfIndent(lines)
      lines = self._convertDjango(lines)
      lines = self._convertCamelCase(lines)
      self._writeToFile(lines, fileObj.filepath)

  def _writeToFile(self, lines, oldFilename):
    writtenMode = int(self.formData["writtenMode"])
    self._drums = {}
    lines = "\n".join(lines)
    if(writtenMode==self.paramForm.WRITTEN_MODE_COPY):
      move(oldFilename, oldFilename + ".orig")
    elif(writtenMode==self.paramForm.WRITTEN_MODE_DRY_RUN):
      return
    elif(writtenMode==self.paramForm.WRITTEN_MODE_DRY_RUN_PRINT):
      self._stdOut = lines
      self._drums = {"Terminal": 1, }
      return
    fileObj = open(oldFilename,"w")
    #fileObj.writelines(lines)
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

  def _convertCamelCase(self, lines):
    if(not self.formData["isReplaceCamalCase"]):
      return lines
    underscorePattern = re.compile("[a-z0-9]_([a-z0-9])")
    newLines = []
    for i in lines:
      lastIdx = 0
      s = ""
      for m in underscorePattern.finditer(i):
        s += m.string[lastIdx:m.start(0)+1] + m.string[m.start(0)+2].upper()
        lastIdx = m.start(0) + 3
      if(lastIdx!=0):
        newLines.append(s + i[lastIdx:])
      else:
        newLines.append(i)
    return newLines

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

