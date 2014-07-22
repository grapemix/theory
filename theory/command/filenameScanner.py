# -*- coding: utf-8 -*-
#!/usr/bin/env python
##### System wide lib #####
import os

##### Theory lib #####
from theory.gui import field

##### Theory third-party lib #####

##### Local app #####
from .baseCommand import SimpleCommand

##### Theory app #####

##### Misc #####

class FilenameScanner(SimpleCommand):
  """
  Allowing user to select list of files. This command is not emphasized on the speed,
  but the flexiblity.
  """
  name = "filenameScanner"
  verboseName = "filenameScanner"

  _notations = ["Command",]
  _gongs = ["FilenameList", "FileObjectList", ]
  _drums = {"Terminal": 1, }

  class ParamForm(SimpleCommand.ParamForm):
    YIELD_MODE_ALL = 1
    YIELD_MODE_FILE = 2
    YIELD_MODE_LINE = 3
    YIELD_MODE_CHUNK = 4

    YIELD_METHOD_CHOICES = (
        (YIELD_MODE_ALL, 'All'),
        (YIELD_MODE_FILE, 'File'),
        (YIELD_MODE_LINE, 'Line'),
        (YIELD_MODE_CHUNK, 'Chunk'),
    )

    rootLst = field.ListField(
        field.TextField(max_length=512),
        label="Root Directory List"
    )
    yieldMethod = field.ChoiceField(
        label="Yield Method",
        help_text="how to send the filename in each iteration",
        choices=YIELD_METHOD_CHOICES,
        initData=YIELD_MODE_ALL,
        required=False
    )
    depth = field.IntegerField(
        label="Depth",
        initData=0,
        required=False,
        help_text="The recursion level. (0 = not recursive, -1 = recursive infinitely)"
    )
    includeFileExtLst = field.ListField(
        field.TextField(max_length=10),
        label="The list of file extension being included",
        help_text="File extenstion being included",
        required=False
    )
    excludeFileExtLst = field.ListField(
        field.TextField(max_length=10),
        label="The list of file extension being excluded",
        help_text="File extenstion being excluded",
        required=False
    )
    includeDirLst = field.ListField(
        field.TextField(max_length=512),
        label="The list of directory being included",
        help_text="Directory being included",
        required=False
    )
    excludeDirLst = field.ListField(
        field.TextField(max_length=512),
        label="The list of directory being excluded",
        help_text="Directory being excluded",
        required=False
    )

    _excludeFileFxnLst = [lambda x: False, ]
    _excludeDirFxnLst = [lambda x: False, ]
    _includeFileFxnLst = [ lambda x: False, ]
    _includeDirFxnLst = [lambda x: False, ]

    @property
    def includeFileFxnLst(self):
      return self._includeFileFxnLst

    @includeFileFxnLst.setter
    def includeFileFxnLst(self, includeFileFxnLst):
      self._includeFileFxnLst = self._includeFileFxnLst[:1]
      self._includeFileFxnLst.extend(includeFileFxnLst)

    @property
    def includeDirFxnLst(self):
      return self._includeDirFxnLst

    @includeDirFxnLst.setter
    def includeDirFxnLst(self, includeDirFxnLst):
      self._includeDirFxnLst = self.includeDirFxnLst[:1]
      self._includeDirFxnLst.extend(includeDirFxnLst)

    @property
    def excludeFileFxnLst(self):
      return self._excludeFileFxnLst

    @excludeFileFxnLst.setter
    def excludeFileFxnLst(self, excludeFileFxnLst):
      self._excludeFileFxnLst = self._excludeFileFxnLst[:1]
      self._excludeFileFxnLst.extend(excludeFileFxnLst)

    @property
    def excludeDirFxnLst(self):
      return self._excludeDirFxnLst

    @excludeDirFxnLst.setter
    def excludeDirFxnLst(self, excludeDirFxnLst):
      self._excludeDirFxnLst = self._excludeDirFxnLst[:1]
      self._excludeDirFxnLst.extend(excludeDirFxnLst)

    def full_clean(self):
      super(SimpleCommand.ParamForm, self).full_clean()
      if(not self._errors):
        if(self.cleaned_data["includeFileExtLst"]!=[]):
          self._includeFileFxnLst[0] = lambda x: \
            os.path.splitext(x)[1] in self.cleaned_data["includeFileExtLst"]
        else:
          self._includeFileFxnLst[0] = lambda x: True

        if(self.cleaned_data["includeDirLst"]!=[]):
          self._includeDirFxnLst[0] = lambda x: \
              x in self.cleaned_data["includeDirLst"]
        else:
          self._includeDirFxnLst[0] = lambda x: True

        if self.cleaned_data["excludeFileExtLst"] == ["*"]:
          self._excludeFileFxnLst[0] = lambda x: True
        elif self.cleaned_data["excludeFileExtLst"] != []:
          self._excludeFileFxnLst[0] = lambda x: \
                os.path.splitext(x)[1] in self.cleaned_data["excludeFileExtLst"]
        else:
          self._excludeFileFxnLst[0] = lambda x: False

        if(self.cleaned_data["excludeDirLst"]!=[]):
          self._excludeDirFxnLst[0] = lambda x: \
              x in self.cleaned_data["excludeDirLst"]
        else:
          self._excludeDirFxnLst[0] = lambda x: False

  # Watch out when implementing YIELD_MODE_LINE and YIELD_MODE_CHUNK
  @property
  def stdout(self):
    return "File Being Selected:\n" + "\n".join(self._filenameLst)

  def _filterByFileFxns(self, fileFullPath):
    """
    In case the filter rules involved both in file and dir level, rules should
    still goto file level.(kind of obvious)
    """
    isAllow = True

    for fxn in self.paramForm.excludeFileFxnLst:
      if(fxn(fileFullPath)):
        isAllow=False
        break

    for fxn in self.paramForm.includeFileFxnLst:
      if(fxn(fileFullPath)):
        isAllow = True
        break

    return isAllow

  def _filterByDirFxns(self, lvlRoot, dirPathLst):
    """
    The mechanism of this fxn is by removing unwanted dir
    """

    newDirPath = []
    for dirPath in dirPathLst:
      isAllow = True
      dirFullPath = os.path.join(lvlRoot, dirPath)
      for fxn in self.paramForm.excludeDirFxnLst:
        if(fxn(dirFullPath)):
          isAllow=False
          break

      for fxn in self.paramForm.includeDirFxnLst:
        if(fxn(dirFullPath)):
          isAllow = True
          break

      if(isAllow):
        newDirPath.append(dirPath)

    return newDirPath

  def generateFileLst(self):
    yieldMethod = int(self.paramForm.cleaned_data["yieldMethod"])
    for root in self.paramForm.cleaned_data["rootLst"]:
      for lvlRoot, dirs, files in self._walk(root):
        for file in files:
          if(yieldMethod==self.paramForm.YIELD_MODE_FILE \
              or yieldMethod==self.paramForm.YIELD_MODE_ALL):
            fullPath = os.path.join(lvlRoot, file)
            if(self._filterByFileFxns(fullPath)):
              yield fullPath
          else:
            raise Error

  def generateDirLst(self):
    for root in self.paramForm.cleaned_data["rootLst"]:
      for lvlRoot, dirs, files in self._walk(root):
        yield dirs

  def run(self):
    self._filenameLst = []
    self._dirnameLst = []

    for i in self.generateFileLst():
      self._filenameLst.append(i)

    for i in self.generateDirLst():
      self._dirnameLst.extend(i)

    self._extractResultToStdOut()

  def _extractResultToStdOut(self):
    self._stdOut = "Filename List:\n"
    self._stdOut += "\n".join(self._filenameLst)
    self._stdOut += "\nDirname List:\n"
    self._stdOut += "\n".join(self._dirnameLst)

  def _walk(self, root, *args, **kwargs):
    root = root.rstrip(os.path.sep)
    #assert os.path.isdir(root)
    numSep = root.count(os.path.sep)
    for lvlRoot, dirs, files in os.walk(root):
      dirs[:] = self._filterByDirFxns(lvlRoot, dirs)
      yield lvlRoot, dirs, files
      thisLvl = lvlRoot.count(os.path.sep)
      if(self.paramForm.cleaned_data["depth"]!=-1 \
          and numSep + self.paramForm.cleaned_data["depth"] <= thisLvl):
        del dirs[:]

  @property
  def filenameLst(self):
    return self._filenameLst

  @property
  def dirnameLst(self):
    return self._dirnameLst
