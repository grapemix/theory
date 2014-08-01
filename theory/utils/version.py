# -*- coding: utf-8 -*-
#!/usr/bin/env python
from __future__ import unicode_literals

import datetime
import os
import subprocess


def getVersion(version=None):
  "Returns a PEP 386-compliant version number from VERSION."
  version = getCompleteVersion(version)

  # Now build the two parts of the version number:
  # major = X.Y[.Z]
  # sub = .devN - for pre-alpha releases
  #     | {a|b|c}N - for alpha, beta and rc releases

  major = getMajorVersion(version)

  sub = ''
  if version[3] == 'alpha' and version[4] == 0:
    gitChangeset = getGitChangeset()
    if gitChangeset:
      sub = '.dev%s' % gitChangeset

  elif version[3] != 'final':
    mapping = {'alpha': 'a', 'beta': 'b', 'rc': 'c'}
    sub = mapping[version[3]] + str(version[4])

  return str(major + sub)


def getMajorVersion(version=None):
  "Returns major version from VERSION."
  version = getCompleteVersion(version)
  parts = 2 if version[2] == 0 else 3
  major = '.'.join(str(x) for x in version[:parts])
  return major


def getCompleteVersion(version=None):
  """Returns a tuple of the theory version. If version argument is non-empy,
  then checks for correctness of the tuple provided.
  """
  if version is None:
    from theory import VERSION as version
  else:
    assert len(version) == 5
    assert version[3] in ('alpha', 'beta', 'rc', 'final')

  return version


def getGitChangeset():
  """Returns a numeric identifier of the latest git changeset.

  The result is the UTC timestamp of the changeset in YYYYMMDDHHMMSS format.
  This value isn't guaranteed to be unique, but collisions are very unlikely,
  so it's sufficient for generating the development version numbers.
  """
  # FIXME: Replace with @lruCache when we upgrade the docs server to PY2.7+.
  if hasattr(getGitChangeset, 'cache'):
    return getGitChangeset.cache

  repoDir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
  gitLog = subprocess.Popen('git log --pretty=format:%ct --quiet -1 HEAD',
      stdout=subprocess.PIPE, stderr=subprocess.PIPE,
      shell=True, cwd=repoDir, universal_newlines=True)
  timestamp = gitLog.communicate()[0]
  try:
    timestamp = datetime.datetime.utcfromtimestamp(int(timestamp))
  except ValueError:
    changeset = None
  else:
    changeset = timestamp.strftime('%Y%m%d%H%M%S')

  getGitChangeset.cache = changeset
  return changeset
