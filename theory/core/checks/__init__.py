# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from .messages import (CheckMessage,
    Debug, Info, Warning, Error, Critical,
    DEBUG, INFO, WARNING, ERROR, CRITICAL)
from .registry import register, runChecks, tagExists, Tags

# Import these to force registration of checks
import theory.core.checks.compatibility.theory_0_1  # NOQA
import theory.core.checks.compatibility.theory_0_2  # NOQA
import theory.core.checks.modelChecks  # NOQA

__all__ = [
  'CheckMessage',
  'Debug', 'Info', 'Warning', 'Error', 'Critical',
  'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL',
  'register', 'runChecks', 'tagExists', 'Tags',
]
