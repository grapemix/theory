# -*- coding: utf-8 -*-
#!/usr/bin/env python
##### System wide lib #####
import os

##### Theory lib #####

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
  params = ["rootLst",]
  _rootLst = []
  _excludeDirLst = []
  _excludeFileExtLst = []
  _excludeFileFxnLst = [\
      lambda x: False,\
  ]
  _excludeDirFxnLst = [\
      lambda x: False,\
      ]
  _includeDirLst = []
  _includeFileExtLst = []
  _includeFileFxnLst = [\
      lambda x: False,\
      ]
  _includeDirFxnLst = [\
      lambda x: False,\
      ]

  YIELD_MODE_ALL = 1
  YIELD_MODE_FILE = 2
  YIELD_MODE_LINE = 3
  YIELD_MODE_CHUNK = 4

  # 0 means not recursive, -1 means recursive infinitely
  _depth = 0
  _fileLst = []
  _yieldMethod = YIELD_MODE_ALL
  _notations = ["Command",]
  _gongs = ["FilenameList", "FileObjectList", ]

  YIELD_METHOD_CHOICES = (
      (YIELD_MODE_ALL, 'all'),
      (YIELD_MODE_FILE, 'file'),
      (YIELD_MODE_LINE, 'line'),
      (YIELD_MODE_CHUNK, 'chunk'),
  )

  #def __init__(self, *args, **kwargs):
  #  super(FilenameScanner, self).__init__(*args, **kwargs)

  # Watch out when implementing YIELD_MODE_LINE and YIELD_MODE_CHUNK
  @property
  def stdout(self):
    return "File Being Selected:\n" + "\n".join(self._fileLst)

  def _filterByFileFxns(self, fileFullPath):
    """
    In case the filter rules involved both in file and dir level, rules should
    still goto file level.(kind of obvious)
    """
    isAllow = True

    for fxn in self.excludeFileFxnLst:
      if(fxn(fileFullPath)):
        isAllow=False
        break

    for fxn in self.includeFileFxnLst:
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
      for fxn in self.excludeDirFxnLst:
        if(fxn(dirFullPath)):
          isAllow=False
          break

      for fxn in self.includeDirFxnLst:
        if(fxn(dirFullPath)):
          isAllow = True
          break

      if(isAllow):
        newDirPath.append(dirPath)

    return newDirPath

  def generate(self, *args, **kwargs):
    for root in self.rootLst:
      for lvlRoot, dirs, files in self._walk(root):
        for file in files:
          if(self.yieldMethod==self.YIELD_MODE_FILE or self.yieldMethod==self.YIELD_MODE_ALL):
            fullPath = os.path.join(lvlRoot, file)
            if(self._filterByFileFxns(fullPath)):
              yield fullPath
          else:
            raise Error

  def run(self, *args, **kwargs):
    for i in self.generate(*args, **kwargs):
      self._fileLst.append(i)

  def _walk(self, root, *args, **kwargs):
    root = root.rstrip(os.path.sep)
    #assert os.path.isdir(root)
    numSep = root.count(os.path.sep)
    for lvlRoot, dirs, files in os.walk(root):
      dirs[:] = self._filterByDirFxns(lvlRoot, dirs)
      yield lvlRoot, dirs, files
      thisLvl = lvlRoot.count(os.path.sep)
      if(self.depth!=-1 and numSep + self.depth <= thisLvl):
        del dirs[:]

  @property
  def fileLst(self):
    """
    :type: List(file)
    """
    return self._fileLst

  @property
  def yieldMethod(self):
    return self._yieldMethod

  @yieldMethod.setter
  def yieldMethod(self, yieldMethod):
    self._yieldMethod = yieldMethod

  @property
  def depth(self):
    return self._depth

  @depth.setter
  def depth(self, depth):
    """
    :param depth: The recursion level. (0 = not recursive, -1 = recursive infinitely)
    :type depth: integer
    """
    self._depth = depth

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

  #def _updateFxns(self):
  #    self._includeFxnLst[0] = lambda x: x in self.includeFileExtLst

  @property
  def includeFileExtLst(self):
    return self._includeFileExtLst

  @includeFileExtLst.setter
  def includeFileExtLst(self, includeFileExtLst):
    """
    :param includeFileExtLst: The list of file extension being included
    :type includeFileExtLst: List(string)
    """
    self._includeFileExtLst = includeFileExtLst
    if(includeFileExtLst!=[]):
      self._includeFileFxnLst[0] = lambda x: os.path.splitext(x)[1] in self.includeFileExtLst
    else:
      self._includeFileFxnLst[0] = lambda x: True

  @property
  def includeDirLst(self):
    return self._includeDirLst

  @includeDirLst.setter
  def includeDirLst(self, includeDirLst):
    """
    :param includeDirLst: The list of directory being included
    :type includeDirLst: List(string)
    """
    self._includeDirLst = includeDirLst
    if(includeDirLst!=[]):
      self._includeDirFxnLst[0] = lambda x: x in self.includeDirLst
      #self._includeDirFxnLst[0] = lambda x: os.path.split(x)[0] in self.includeDirLst
    else:
      self._includeDirFxnLst[0] = lambda x: True

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

  @property
  def excludeFileExtLst(self):
    return self._excludeFileExtLst

  @excludeFileExtLst.setter
  def excludeFileExtLst(self, excludeFileExtLst):
    """
    :param excludeFileExtLst: The list of file extension being excluded
    :type excludeFileExtLst: List(string)
    """
    self._excludeFileExtLst = excludeFileExtLst
    if(excludeFileExtLst!=[]):
      self._excludeFileFxnLst[0] = lambda x: os.path.splitext(x)[1] in self.excludeFileExtLst
    else:
      self._excludeFileFxnLst[0] = lambda x: False

  @property
  def excludeDirLst(self):
    return self._excludeDirLst

  @excludeDirLst.setter
  def excludeDirLst(self, excludeDirLst):
    """
    :param excludeDirLst: The list of directory being excluded
    :type excludeDirLst: List(string)
    """
    self._excludeDirLst = excludeDirLst
    if(excludeDirLst!=[]):
      self._excludeDirFxnLst[0] = lambda x: x in self.excludeDirLst
      #self._excludeDirFxnLst[0] = lambda x: os.path.split(x)[0] in self.excludeDirLst
    else:
      self._excludeDirFxnLst[0] = lambda x: False

  @property
  def rootLst(self):
    return self._rootLst

  @rootLst.setter
  def rootLst(self, rootLst):
    """
    :param rootLst: The list of directory being scaned
    :type rootLst: List(string)
    """
    self._rootLst = rootLst

#  @property
#  def notations(self):
#    return self._notations
#
#  @notations.setter
#  def notations(self, notations):
#    self._notations = notations
#
#  @property
#  def gongs(self):
#    return self._gongs
#
#  @gongs.setter
#  def gongs(self, gongs):
#    self._gongs = gongs
#
#  def validate(self, *args, **kwargs):
#    for i in ["name", "verboseName", "description"]:
#      if(getattr(self, i)==None):
#        return False
#    return True
#
#  def stop(self, *args, **kwargs):
#    pass
