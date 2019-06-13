# -*- coding: utf-8 -*-
#!/usr/bin/env python
##### System wide lib #####
import datetime
import json

##### Theory lib #####
from theory.apps.model import (
    Command,
    History,
    Mood,
    )
#from theory.core.exceptions import ValidationError
from theory.db.model import Q

##### Theory third-party lib #####

##### Local app #####

##### Theory app #####

##### Misc #####

__all__ = ('HistoryMixin',)


class HistoryMixin(object):
  historyIndex = -1  # It should be working reversely
  historyLen = 0

  def __init__(self, *args, **kwargs):
    self.historyModel = History.objects.all()
    self.historyLen = len(self.historyModel)
    super(HistoryMixin, self).__init__()

  def _showPreviousCmdRequest(self):
    if self.historyIndex >= self.historyLen or self.historyLen == 0:
      self.actionQ.append({
          "action": "setAndSelectCmdLine",
          "val": "",
          })
    elif self.historyIndex + 1 < self.historyLen:
      self.historyIndex += 1
      self.actionQ.append({
          "action": "cleanUpCrt",
          })
      commandName = self.historyModel[self.historyIndex].commandName
      self.actionQ.append({
          "action": "setAndSelectCmdLine",
          "val": commandName,
          })
      self.parser.cmdInTxt = commandName

      try:
        self.cmdModel = Command.objects.get(
            Q(name=commandName)
            & (Q(moodSet__name=self.moodName) | Q(moodSet__name="norm"))
            )

        finalDataDict = json.loads(
            self.historyModel[self.historyIndex].jsonData
            )
        val = self._buildCmdForm(finalDataDict)

        self.actionQ.append({
            "action": "buildParamForm",
            "val": val,
            })
      except Command.DoesNotExist as errMsg:
        self.actionQ.append({
            "action": "getNotify",
            "val": "Command not found: {0} ({1})".format(errMsg, commandName)
            })
      except Exception as e:
        self.logger.error(e, exc_info=True)
        raise ValidationError(str(e))

  def _showNextCmdRequest(self):
    if self.historyIndex == -1:
      self.actionQ.append({
          "action": "setAndSelectCmdLine",
          "val": "",
          })
    elif self.historyIndex - 1 >= 0:
      self.historyIndex -= 1
      self.actionQ.append({
          "action": "cleanUpCrt",
          })
      commandName = self.historyModel[self.historyIndex].commandName
      self.actionQ.append({
          "action": "setAndSelectCmdLine",
          "val": commandName,
          })
      self.parser.cmdInTxt = commandName
      try:
        self.cmdModel = Command.objects.get(
            Q(name=commandName)
            & (Q(moodSet__name=self.moodName) | Q(moodSet__name="norm"))
            )

        finalDataDict = json.loads(
            self.historyModel[self.historyIndex].jsonData
            )
        self.actionQ.append({
            "action": "buildParamForm",
            "val": self._buildCmdForm(finalDataDict),
            })
      except Command.DoesNotExist as errMsg:
        self.actionQ.append({
            "action": "getNotify",
            "val": "Command not found: {0} ({1})".format(errMsg, commandName)
            })
      except Exception as e:
        self.logger.error(e, exc_info=True)
        raise ValidationError(str(e))



  def _escapeRequest(self):
    self.historyIndex = -1
    self.actionQ.append({
        "action": "restoreCmdLine",
        })
    self.actionQ.append({
        "action": "cleanUpCrt",
        })

  def _updateHistory(self, jsonData):
    # Temp disable. During the development stage, reprobeAllModule is run almost
    # everytime which delete all command module. However, since the
    # reverse_delete_rule of the command field is cascade, all history record
    # will be lost. This field should re-enable in the future.
    #History(commandName=self.parser.cmdInTxt, command=self.cmdModel,
    #from theory.db.model import F

    #History.objects(
    #    commandName=self.parser.cmdInTxt,
    #    moodSet=self.moodName,
    #    jsonData=jsonData,
    #    ).update_one(
    #        inc__repeated=1,
    #        set__touched=datetime.datetime.utcnow(),
    #        upsert=True
    #        )
    #History.objects.updateOrCreate(
    #    commandName=self.parser.cmdInTxt,
    #    #moodSet=Mood.objects.get(name=self.moodName),
    #    jsonData=jsonData,
    #    defaults={
    #      "touched": datetime.datetime.utcnow(),
    #      "repeated": F("repeated") + 1,
    #      }
    #    )
    historyQuery = History.objects.filter(
        commandName=self.parser.cmdInTxt,
        jsonData=jsonData,
        )
    if len(historyQuery) > 0:
      historyQuery[0].touched = datetime.datetime.utcnow()
      historyQuery[0].repeated += 1
      historyQuery[0].save(updateFields=["touched", "repeated"])
    else:
      h = History(
          commandName=self.parser.cmdInTxt,
          #moodSet=Mood.objects.filter(name=self.moodName),
          jsonData=jsonData,
          )
      h.save()
      h.moodSet.add(Mood.objects.get(name=self.moodName))

    self.historyModel = History.objects.all()
    self.historyLen = len(self.historyModel)
