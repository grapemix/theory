# -*- coding: utf-8 -*-
#!/usr/bin/env python
##### System wide lib #####

##### Theory lib #####
from theory.conf import settings
from theory.core.reactor.reactor import Reactor
from theory.gui import field
from theory.utils.mood import loadMoodData

##### Theory third-party lib #####

##### Local app #####
from .baseCommand import SimpleCommand

##### Theory app #####

##### Misc #####

class SwitchMood(SimpleCommand):
  """
  To switch Theory mood
  """
  name = "switchMood"
  verboseName = "switchMood"
  _notations = ["Command",]
  _drums = {"Terminal": 1,}

  class ParamForm(SimpleCommand.ParamForm):
    moodName = field.ChoiceField(
        label="Mood Name",
        helpText="The name of mood being used",
        dynamicChoiceLst=(
          set([(moodName, moodName) for moodName in settings.INSTALLED_MOODS])
        ),
        )

  def run(self):
    moodName = self.paramForm.fields["moodName"].finalData
    config = loadMoodData(moodName)
    for i in dir(config):
      if i == i.upper():
        settings.MOOD[i] = getattr(config, i)

    reactor = Reactor()
    reactor.moodName = moodName

    self._stdOut += (
      "Successfully switch to {0} mood\n\n"
      "The following config is applied:\n"
    ).format(moodName)

    for k,v in settings.MOOD.items():
      self._stdOut += "    %s: %s\n" % (k, v)
