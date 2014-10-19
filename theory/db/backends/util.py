import warnings

from theory.utils.deprecation import RemovedInTheory19Warning

warnings.warn(
  "The theory.db.backends.util module has been renamed. "
  "Use theory.db.backends.utils instead.", RemovedInTheory19Warning,
  stacklevel=2)

from theory.db.backends.utils import *  # NOQA
