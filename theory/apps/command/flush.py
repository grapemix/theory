# -*- coding: utf-8 -*-
#!/usr/bin/env python
##### System wide lib #####
import sys

##### Theory lib #####
from theory.apps.command.baseCommand import SimpleCommand
from theory.gui import field

from theory.apps import apps
from theory.db import connections, router, transaction, DEFAULT_DB_ALIAS
from theory.core.bridge import Bridge
from theory.gui.color import noStyle
from theory.core.sql import sqlFlush, emitPostMigrateSignal
from theory.utils.six.moves import input
from theory.utils.importlib import importModule
from theory.utils import six

##### Theory third-party lib #####

##### Local app #####

##### Theory app #####

##### Misc #####

class Flush(SimpleCommand):
  """
  Removes ALL DATA from the database, including data added during
  migrations. Unmigrated apps will also have their initialData
  fixture reloaded. Does not achieve a "fresh install" state.
  """
  name = "flush"
  verboseName = "flush"
  _notations = ["Command",]
  _drums = {"Terminal": 1, }

  class ParamForm(SimpleCommand.ParamForm):
    database = field.TextField(
        label="database",
        helpText=(
          'Nominates a specific database to load fixtures into.',
          'Defaults to the "default" database.'
          ),
        initData=DEFAULT_DB_ALIAS,
        )
    isLoadInitData = field.BooleanField(
        label="is loading initial data",
        helpText=(
          'Tells Theory not to load any initial data after database ',
          'synchronization.'
          ),
        required=False,
        initData=False,
        )
    isResetSequence = field.BooleanField(
        label="is reseting sequence",
        helpText="is reseting sequence",
        required=False,
        initData=True,
        )
    isAllowCascade = field.BooleanField(
        label="is allowing cascade",
        helpText="is allowing cascade",
        required=False,
        initData=False,
        )
    isInhibitPostMigrate = field.BooleanField(
        label="is inhibiting post-migrate",
        helpText="is inhibiting post-migrate",
        required=False,
        initData=False,
        )

  def run(self):
    options = self.paramForm.clean()
    database = options.get('database')
    connection = connections[database]
    verbosity = options.get('verbosity')
    interactive = False
    # The following are stealth options used by Theory's internals.
    resetSequences = options.get('isResetSequences')
    allowCascade = options.get('isAllowCascade')
    inhibitPostMigrate = options.get('isInhibitPostMigrate')

    self.style = noStyle()
    bridge = Bridge()

    # Import the 'management' module within each installed app, to register
    # dispatcher events.
    #for appConfig in apps.getAppConfigs():
    #  try:
    #    importModule('.management', appConfig.name)
    #  except ImportError:
    #    pass

    sqlList = sqlFlush(self.style, connection, onlyTheory=True,
               resetSequences=resetSequences,
               allowCascade=allowCascade)

    if interactive:
      confirm = input("""You have requested a flush of the database.
This will IRREVERSIBLY DESTROY all data currently in the %r database,
and return each table to an empty state.
Are you sure you want to do this?

  Type 'yes' to continue, or 'no' to cancel: """ % connection.settingsDict['NAME'])
    else:
      confirm = 'yes'

    if confirm == 'yes':
      try:
        with transaction.atomic(using=database,
                    savepoint=connection.features.canRollbackDdl):
          with connection.cursor() as cursor:
            for sql in sqlList:
              cursor.execute(sql)
      except Exception as e:
        newMsg = (
          "Database %s couldn't be flushed. Possible reasons:\n"
          "  * The database isn't running or isn't configured correctly.\n"
          "  * At least one of the expected database tables doesn't exist.\n"
          "  * The SQL was invalid.\n"
          "Hint: Look at the output of 'theory-admin.py sqlflush'. That's the SQL this command wasn't able to run.\n"
          "The full error: %s") % (connection.settingsDict['NAME'], e)
        six.reraise(CommandError, CommandError(newMsg), sys.excInfo()[2])

      if not inhibitPostMigrate:
        self.emitPostMigrate(verbosity, interactive, database)

      # Reinstall the initialData fixture.
      if options.get('isLoadInitialData'):
        # Reinstall the initialData fixture.
        options["fixtureLabel"] = "initialData"
        bridge.execeuteEzCommand(
            'theory',
            'loaddata',
            [],
            options
            )

    else:
      self.stdout.write("Flush cancelled.\n")

  @staticmethod
  def emitPostMigrate(verbosity, interactive, database):
    # Emit the post migrate signal. This allows individual applications to
    # respond as if the database had been migrated from scratch.
    allModels = []
    for appConfig in apps.getAppConfigs():
      allModels.extend(router.getMigratableModels(appConfig, database, includeAutoCreated=True))
    emitPostMigrateSignal(set(allModels), verbosity, interactive, database)
