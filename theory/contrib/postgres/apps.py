from theory.apps import AppConfig
from theory.db.backends.signals import connectionCreated
from theory.db.model import CharField, TextField
from theory.utils.translation import ugettextLazy as _

from .lookup import Unaccent
from .signal import registerHstoreHandler


class PostgresConfig(AppConfig):
  name = 'theory.contrib.postgres'
  verbose_name = _('PostgreSQL extensions')

  def ready(self):
    connectionCreated.connect(registerHstoreHandler)
    CharField.registerLookup(Unaccent)
    TextField.registerLookup(Unaccent)
