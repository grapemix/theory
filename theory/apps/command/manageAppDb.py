# -*- coding: utf-8 -*-
#!/usr/bin/env python
##### System wide lib #####
import os
import re
from subprocess import check_call
import time

##### Theory lib #####
from theory.apps import apps
from theory.apps.command.baseCommand import SimpleCommand
from theory.conf import settings
from theory.db import connection
from theory.gui import field

##### Theory third-party lib #####

##### Local app #####

##### Theory app #####

##### Misc #####

class ManageAppDb(SimpleCommand):
  """
  Manage all postgres' table related to an app
  """
  name = "manageAppDb"
  verboseName = "manageAppDb"
  _notations = ["Command",]
  _drums = {"Terminal": 1, }

  class ParamForm(SimpleCommand.ParamForm):
    appNameLst = field.MultipleChoiceField(label="Application Name",
        helpText="The name of applications to be managed",
        choices=(set([("apps", "apps")] +
          [(settings.INSTALLED_APPS[i], settings.INSTALLED_APPS[i])
            for i in range(len(settings.INSTALLED_APPS))])),
        )
    action = field.ChoiceField(
        label="Action",
        initData="backup",
        helpText="Backup is only available for third-party apps",
        choices=(
          ("backup", "backup"),
          ("drop", "drop"),
          )
        )

  def _dropTbl(self, c, allTblLst, allSeqLst):
    p = re.compile("^({0})_[A-z_]+".format(
      "|".join(self.paramForm.clean()["appNameLst"]
        )))

    tblLst = []
    seqLst = []
    for i in allTblLst:
      if p.match(i):
        tblLst.append(i)
    for i in allSeqLst:
      if p.match(i):
        seqLst.append(i)

    if "apps" in self.paramForm.clean()["appNameLst"]:
      tblLst.append("theoryMigrations")
      seqLst.append("theoryMigrations_id_seq")

    if len(tblLst) > 0:
      c.execute('DROP TABLE IF EXISTS "{0}" CASCADE'.format('","'.join(tblLst)))
    if len(seqLst) > 0:
      c.execute(
          'DROP SEQUENCE IF EXISTS "{0}" CASCADE'.format('","'.join(seqLst))
          )

  def _backupTbl(self, allTblLst, allSeqLst):
    dirName = time.strftime("%y%m%d%H%M")
    for appName in self.paramForm.clean()["appNameLst"]:
      tblLst = []
      for i in allTblLst:
        if i.startswith(appName):
          tblLst.append(i)
      for i in allSeqLst:
        if i.startswith(appName):
          tblLst.append(i)
      dirPath = os.path.join(
          apps.getAppPath(appName),
          "fixture",
          dirName,
          )
      if not os.path.exists(dirPath):
        os.makedirs(dirPath)

      cmd = [
          "pg_dump",
          "-f",
          "{0}/bk.sql".format(dirPath),
          "-d",
          settings.DATABASES["default"]["NAME"],
          "-U",
          settings.DATABASES["default"]["USER"],
          "-h",
          settings.DATABASES["default"]["HOST"],
          "-p",
          settings.DATABASES["default"]["PORT"],
          ]
      for i in tblLst:
        cmd.append("-t")
        cmd.append(i)


      check_call(cmd,
          env={"PGPASSWORD": settings.DATABASES["default"]["PASSWORD"]}
          )
      cmd = [
          "pg_dump",
          "-Fc",
          "-f",
          "{0}/bk.dump".format(dirPath),
          "-d",
          settings.DATABASES["default"]["NAME"],
          "-U",
          settings.DATABASES["default"]["USER"],
          "-h",
          settings.DATABASES["default"]["HOST"],
          "-p",
          settings.DATABASES["default"]["PORT"],
          ]
      for i in tblLst:
        cmd.append("-t")
        cmd.append(i)

      check_call(cmd,
          env={"PGPASSWORD": settings.DATABASES["default"]["PASSWORD"]}
          )

  def run(self):
    action = self.paramForm.clean()["action"]
    with connection.cursor() as c:
      c.execute("SELECT sequence_name FROM information_schema.sequences")
      r = c.fetchall()
      allSeqLst = []
      for i in r:
        allSeqLst.append(i[0])
      c.execute((
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema = 'public'"
        ))
      r = c.fetchall()
      allTblLst = []
      for i in r:
        allTblLst.append(i[0])
      if action == "drop":
        self._dropTbl(c, allTblLst, allSeqLst)
      if action == "backup":
        self._backupTbl(allTblLst, allSeqLst)
