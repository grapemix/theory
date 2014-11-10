import os
import sys

from setuptools import setup, findPackages
from distutils.sysconfig import getPythonLib

# Warn if we are installing over top of an existing installation. This can
# cause issues where files that were deleted from a more recent Theory are
# still present in site-packages. See #18115.
overlayWarning = False
if "install" in sys.argv:
  libPaths = [getPythonLib()]
  if libPaths[0].startswith("/usr/lib/"):
    # We have to try also with an explicit prefix of /usr/local in order to
    # catch Debian's custom user site-packages directory.
    libPaths.append(getPythonLib(prefix="/usr/local"))
  for libPath in libPaths:
    existingPath = os.path.abspath(os.path.join(libPath, "theory"))
    if os.path.exists(existingPath):
      # We note the need for the warning here, but present it after the
      # command is run, so it's more likely to be seen.
      overlayWarning = True
      break


EXCLUDE_FROM_PACKAGES = ['theory.conf.project_template',
             'theory.conf.app_template',
             'theory.bin']


# Dynamically calculate the version based on theory.VERSION.
version = __import__('theory').getVersion()


setup(
  name='Theory',
  version=version,
  url='http://www.theoryproject.com/',
  author='Theory Software Foundation',
  authorEmail='foundation@theoryproject.com',
  description=('A high-level Python Web framework that encourages '
         'rapid development and clean, pragmatic design.'),
  license='BSD',
  packages=findPackages(exclude=EXCLUDE_FROM_PACKAGES),
  includePackageData=True,
  scripts=['theory/bin/theory_start.py'],
  entryPoints={'consoleScripts': [
    'theory-admin = theory.core.management:executeFromCommandLine',
  ]},
  extrasRequire={
    "bcrypt": ["bcrypt"],
  },
  zipSafe=False,
  classifiers=[
    'Development Status :: 3 - Alpha',
    'Environment :: Web Environment',
    'Framework :: Theory',
    'Intended Audience :: Developers',
    'License :: OSI Approved :: BSD License',
    'Operating System :: OS Independent',
    'Programming Language :: Python',
    'Programming Language :: Python :: 2',
    'Programming Language :: Python :: 2.7',
    'Programming Language :: Python :: 3',
    'Programming Language :: Python :: 3.2',
    'Programming Language :: Python :: 3.3',
    'Programming Language :: Python :: 3.4',
    'Topic :: Internet :: WWW/HTTP',
    'Topic :: Internet :: WWW/HTTP :: Dynamic Content',
    'Topic :: Internet :: WWW/HTTP :: WSGI',
    'Topic :: Software Development :: Libraries :: Application Frameworks',
    'Topic :: Software Development :: Libraries :: Python Modules',
  ],
)


if overlayWarning:
  sys.stderr.write("""

========
WARNING!
========

You have just installed Theory over top of an existing
installation, without removing it first. Because of this,
your install may now include extraneous files from a
previous version that have since been removed from
Theory. This is known to cause a variety of problems. You
should manually remove the

%(existingPath)s

directory and re-install Theory.

""" % {"existingPath": existingPath})
