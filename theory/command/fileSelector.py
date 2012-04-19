# -*- coding: utf-8 -*-
##### System wide lib #####
import os

##### Theory lib #####

##### Theory third-party lib #####

##### Local app #####
from .baseCommand import BaseCommand

##### Theory app #####

##### Misc #####

class FileSelector(BaseCommand):
  """
  Allowing user to select files
  """
  name = "fileSelector"
  verboseName = "fileSelector"
  params = ["roots",]
  _roots = []
  _excludeDirs = []
  _excludeFilesExt = []
  _excludeFxns = [\
      lambda x: False,\
      lambda x: False,\
      ]
  _includeDirs = []
  _includeFilesExt = []
  _includeFxns = [\
      lambda x: False,\
      lambda x: False,\
      ]

  YIELD_MODE_ALL = 1
  YIELD_MODE_FILE = 2
  YIELD_MODE_LINE = 3
  YIELD_MODE_CHUNK = 4

  # 0 means not recursive, -1 means recursive infinitely
  _depth = 0
  _files = []
  _yieldMethod = YIELD_MODE_ALL
  _notations = ["Command",]
  _gongs = ["FilenameList", "FileObjectList", ]

  YIELD_METHOD_CHOICES = (
      (YIELD_MODE_ALL, 'all'),
      (YIELD_MODE_FILE, 'file'),
      (YIELD_MODE_LINE, 'line'),
      (YIELD_MODE_CHUNK, 'chunk'),
  )

  def __init__(self, *args, **kwargs):
    super(FileSelector, self).__init__(*args, **kwargs)

  # Watch out when implementing YIELD_MODE_LINE and YIELD_MODE_CHUNK
  @property
  def stdout(self):
    return "File Being Selected:\n" + "\n".join(self._files)

  def _filterFxns(self, fileFullPath):
    isAllow = True

    for fxn in self.excludeFxns:
      if(fxn(fileFullPath)):
        isAllow=False
        break

    for fxn in self.includeFxns:
      if(fxn(fileFullPath)):
        isAllow = True
        break

    return isAllow

  def generate(self, *args, **kwargs):
    for root in self.roots:
      for lvlRoot, dirs, files in self._walk(root):
        for file in files:
          if(self.yieldMethod==self.YIELD_MODE_FILE or self.yieldMethod==self.YIELD_MODE_ALL):
            fullPath = os.path.join(lvlRoot, file)
            if(self._filterFxns(fullPath)):
              yield fullPath
          else:
            raise Error

  def run(self, *args, **kwargs):
    for i in self.generate(*args, **kwargs):
      self._files.append(i)

  def _walk(self, root, *args, **kwargs):
      root = root.rstrip(os.path.sep)
      #assert os.path.isdir(root)
      numSep = root.count(os.path.sep)
      for lvlRoot, dirs, files in os.walk(root):
        yield lvlRoot, dirs, files
        thisLvl = lvlRoot.count(os.path.sep)
        if(self.depth!=-1 and numSep + self.depth <= thisLvl):
          del dirs[:]

  @property
  def files(self):
    return self._files

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
    self._depth = depth

  @property
  def includeFxns(self):
    return self._includeFxns

  @includeFxns.setter
  def includeFxns(self, includeFxns):
    self._includeFxns = self._includeFxns[:2]
    self._includeFxns.extend(includeFxns)

  def _updateFxns(self):
      self._includeFxns[0] = lambda x: x in self.includeFilesExt

  @property
  def includeFilesExt(self):
    return self._includeFilesExt

  @includeFilesExt.setter
  def includeFilesExt(self, includeFilesExt):
    self._includeFilesExt = includeFilesExt
    if(includeFilesExt!=[]):
      self._includeFxns[0] = lambda x: x.split(".")[-1] in self.includeFilesExt
    else:
      self._includeFxns[0] = lambda x: True

  @property
  def includeDirs(self):
    return self._includeDirs

  @includeDirs.setter
  def includeDirs(self, includeDirs):
    self._includeDirs = includeDirs
    if(includeDirs!=[]):
      self._includeFxns[1] = lambda x: x in self.includeDirs
    else:
      self._includeFxns[1] = lambda x: True

  @property
  def excludeFxns(self):
    return self._excludeFxns

  @excludeFxns.setter
  def excludeFxns(self, excludeFxns):
    self._excludeFxns = self._excludeFxns[:2]
    self._excludeFxns.extend(excludeFxns)

  @property
  def excludeFilesExt(self):
    return self._excludeFilesExt

  @excludeFilesExt.setter
  def excludeFilesExt(self, excludeFilesExt):
    self._excludeFilesExt = excludeFilesExt
    if(excludeFilesExt!=[]):
      self._excludeFxns[0] = lambda x: x.split(".")[-1] in self.excludeFilesExt
    else:
      self._excludeFxns[0] = lambda x: False

  @property
  def excludeDirs(self):
    return self._excludeDirs

  @excludeDirs.setter
  def excludeDirs(self, excludeDirs):
    self._excludeDirs = excludeDirs
    if(excludeDirs!=[]):
      self._excludeFxns[1] = lambda x: x in self.excludeDirs
    else:
      self._excludeFxns[1] = lambda x: False

  @property
  def roots(self):
    return self._roots

  @roots.setter
  def roots(self, roots):
    self._roots = roots

  @property
  def isRecursive(self):
    return self._isRecursive

  @isRecursive.setter
  def isRecursive(self, isRecursive):
    self._isRecursive = isRecursive

  """
  @property
  def notations(self):
    return self._notations

  @notations.setter
  def notations(self, notations):
    self._notations = notations

  @property
  def gongs(self):
    return self._gongs

  @gongs.setter
  def gongs(self, gongs):
    self._gongs = gongs

  def validate(self, *args, **kwargs):
    for i in ["name", "verboseName", "description"]:
      if(getattr(self, i)==None):
        return False
    return True

  def stop(self, *args, **kwargs):
    pass
  """
