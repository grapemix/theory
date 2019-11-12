# -*- coding: utf-8 -*-
#!/usr/bin/env python
##### System wide lib #####
import warnings
from collections import OrderedDict

##### Theory lib #####
from theory.conf import settings
from theory.gui import field

from theory.apps import apps
from theory.apps.util import sortDependencies
#from theory.core.management.base import BaseCommand, CommandError
from theory.core import serializers
from theory.core.exceptions import CommandError
from theory.db import router, DEFAULT_DB_ALIAS
from theory.utils.deprecation import RemovedInTheory19Warning

##### Theory third-party lib #####

##### Local app #####
from .baseCommand import SimpleCommand

##### Theory app #####

##### Misc #####

class Dumpdata(SimpleCommand):
  """
  Output the contents of the database as a fixture of the given
  format (using each model's default manager unless --all is
  specified).
  """
  name = "dumpdata"
  verboseName = "dumpdata"
  _notations = ["Command",]
  _drums = {"Terminal": 1,}

  class ParamForm(SimpleCommand.ParamForm):
    appLabelLst = field.ListField(
        field.TextField(maxLen=64),
        label="app label list",
        helpText='Restricts dumped data to the specified appLabel or appLabel.ModelName.',
        initData=[],
        )
    format = field.ChoiceField(
        label="format",
        helpText="Specifies the output serialization format for fixtures.",
        choices=(
          ("json", "json"),
          ),
        initData="json",
        )
    indent = field.IntegerField(
        label="indent",
        helpText='Specifies the indent level to use when pretty-printing output.',
        initData=2,
        )
    database = field.TextField(
        label="database",
        helpText=(
          'Nominates a specific database to dump fixtures from.',
          'Defaults to the "default" database.'
          ),
        initData=DEFAULT_DB_ALIAS,
        )
    excludeLst = field.ListField(
        field.TextField(maxLen=64),
        label="exclude list",
        helpText='appLabel or appLabel.ModelName to exclude ',
        initData=[],
        )
    isNature = field.BooleanField(
        label="is nature",
        helpText='Use natural keys if they are available',
        required=False,
        initData=False,
        )
    isNatureForeign = field.BooleanField(
        label="is nature foreign",
        helpText='Use natural foreign keys if they are available.',
        required=False,
        initData=False,
        )
    isNaturePrimary = field.BooleanField(
        label="is nature primary",
        helpText='Use natural primary keys if they are available.',
        required=False,
        initData=False,
        )
    isUseBaseManager = field.BooleanField(
        label="is use base manager",
        helpText=(
          "Use Theory's base manager to dump all models stored in the database, ",
          "including those that would otherwise be filtered or modified by ",
          "a custom manager."
          ),
        required=False,
        initData=False,
        )
    primaryKeyLst = field.ListField(
        field.IntegerField(),
        label="primary key list",
        helpText=(
          "Only dump objects with given primary keys. ",
          "Accepts a comma separated list of keys. ",
          "This option will only work when you specify one model."
          ),
        required=False,
        initData=[],
        )
    output = field.TextField(
        label="output",
        helpText='Specifies file to which the output is written.',
        initData="",
        required=False,
        )
    isShowTraceback = field.BooleanField(
        label="is show traceback",
        helpText='Show traceback if they are available.',
        required=False,
        initData=False,
        )

  def run(self):
    data = self.paramForm.clean()
    format = data["format"]
    indent = data["indent"]
    database = data["database"]
    excludeLst = data["excludeLst"]
    output = data["output"]
    isShowTraceback = data["isShowTraceback"]
    isNatureForeign = data['isNatureForeign'] or data["isNature"]
    isNaturePrimary = data["isNaturePrimary"]
    isUseBaseManager = data['isUseBaseManager']
    primaryKeyLst = data["primaryKeyLst"]
    appLabelLst = data["appLabelLst"]

    excludedApps = set()
    excludedModels = set()
    for exclude in excludeLst:
      if '.' in exclude:
        try:
          model = apps.getModel(exclude)
        except LookupError:
          raise CommandError('Unknown model in excludes: %s' % exclude)
        excludedModels.add(model)
      else:
        try:
          appConfig = apps.getAppConfig(exclude)
        except LookupError:
          raise CommandError('Unknown app in excludes: %s' % exclude)
        excludedApps.add(appConfig)

    if len(appLabelLst) == 0:
      if primaryKeyLst:
        raise CommandError("You can only use --pks option with one model")
      appList = OrderedDict((appConfig, None)
        for appConfig in apps.getAppConfigs()
        if appConfig.modelModule is not None and appConfig not in excludedApps)
    else:
      if len(appLabelLst) > 1 and primaryKeyLst:
        raise CommandError("You can only use --pks option with one model")
      appList = OrderedDict()
      for label in appLabelLst:
        try:
          if not label.startswith("theory.apps"):
            appLabel, modelLabel = label.split('.')
          else:
            dummy, appLabel, modelLabel = label.split('.')
          try:
            appConfig = apps.getAppConfig(appLabel)
          except LookupError:
            raise CommandError("Unknown application: %s" % appLabel)
          if appConfig.modelModule is None or appConfig in excludedApps:
            continue
          try:
            model = appConfig.getModel(modelLabel)
          except LookupError:
            raise CommandError("Unknown model: %s.%s" % (appLabel, modelLabel))

          appListValue = appList.setdefault(appConfig, [])

          # We may have previously seen a "all-models" request for
          # this app (no model qualifier was given). In this case
          # there is no need adding specific models to the list.
          if appListValue is not None:
            if model not in appListValue:
              appListValue.append(model)
        except ValueError:
          if primaryKeyLst:
            raise CommandError("You can only use --pks option with one model")
          # This is just an app - no model qualifier
          if not label.startswith("theory.apps"):
            appLabel = label
          else:
            appLabel = "apps"
          try:
            appConfig = apps.getAppConfig(appLabel)
          except LookupError:
            raise CommandError("Unknown application: %s" % appLabel)
          if appConfig.modelModule is None or appConfig in excludedApps:
            continue
          appList[appConfig] = None

    # Check that the serialization format exists; this is a shortcut to
    # avoid collating all the objects and _then_ failing.
    if format not in serializers.getPublicSerializerFormats():
      try:
        serializers.getSerializer(format)
      except serializers.SerializerDoesNotExist:
        pass

      raise CommandError("Unknown serialization format: %s" % format)

    def getObjects():
      # Collate the objects to be serialized.
      for model in sortDependencies(appList.items()):
        if model in excludedModels:
          continue
        if not model._meta.proxy and router.allowMigrate(database, model):
          if isUseBaseManager:
            objects = model._baseManager
          else:
            objects = model._defaultManager

          queryset = objects.using(database).orderBy(model._meta.pk.name)
          if primaryKeyLst:
            queryset = queryset.filter(pk__in=primaryKeyLst)
          for obj in queryset.iterator():
            yield obj

    try:
      if output:
        stream = open(output, 'w')
      else:
        from cStringIO import StringIO
        stream = StringIO()
        None
      try:
        serializers.serialize(format, getObjects(), indent=indent,
            useNaturalForeignKeys=isNatureForeign,
            useNaturalPrimaryKeys=isNaturePrimary,
            stream=stream or self.stdOut)
      finally:
        if stream:
          if not output:
            self._stdOut = stream.getvalue()
          stream.close()
    except Exception as e:
      if isShowTraceback:
        raise
      raise CommandError("Unable to serialize database: %s" % e)

