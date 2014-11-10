"""
Sets up the terminal color scheme.
"""

import os
import sys

from theory.utils import termcolors


def supportsColor():
  """
  Returns True if the running system's terminal supports color, and False
  otherwise.
  """
  plat = sys.platform
  supportedPlatform = plat != 'Pocket PC' and (plat != 'win32' or
                         'ANSICON' in os.environ)
  # isatty is not always implemented, #6223.
  isA_tty = hasattr(sys.stdout, 'isatty') and sys.stdout.isatty()
  if not supportedPlatform or not isA_tty:
    return False
  return True


def colorStyle():
  """Returns a Style object with the Theory color scheme."""
  if not supportsColor():
    style = noStyle()
  else:
    THEORY_COLORS = os.environ.get('THEORY_COLORS', '')
    colorSettings = termcolors.parseColorSetting(THEORY_COLORS)
    if colorSettings:
      class dummy:
        pass
      style = dummy()
      # The nocolor palette has all available roles.
      # Use that palette as the basis for populating
      # the palette as defined in the environment.
      for role in termcolors.PALETTES[termcolors.NOCOLOR_PALETTE]:
        format = colorSettings.get(role, {})
        setattr(style, role, termcolors.makeStyle(**format))
      # For backwards compatibility,
      # set style for ERROR_OUTPUT == ERROR
      style.ERROR_OUTPUT = style.ERROR
    else:
      style = noStyle()
  return style


def noStyle():
  """Returns a Style object that has no colors."""
  class dummy:
    def __getattr__(self, attr):
      return lambda x: x
  return dummy()
