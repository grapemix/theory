# -*- coding: utf-8 -*-
#!/usr/bin/env python
##### System wide lib #####

##### Theory lib #####
from theory.conf import settings
from theory.core.reactor import *
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
    moodName = field.ChoiceField(label="Mood Name", \
        help_text="The name of mood being used", \
        choices=(set([(i, settings.INSTALLED_MOODS[i]) for i in range(len(settings.INSTALLED_MOODS))])), \
        )

  def run(self):
    moodName = self.paramForm.fields["moodName"].finalChoiceLabel
    config = loadMoodData(moodName)
    for i in dir(config):
      if(i==i.upper()):
        settings.MOOD[i] = getattr(config, i)

    reactor.mood = moodName

    self._stdOut += "Successfully switch to %s mood\n\nThe following config is applied:\n" % (moodName)
    for k,v in settings.MOOD.iteritems():
      self._stdOut += "    %s: %s\n" % (k, unicode(v))

