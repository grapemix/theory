# -*- coding: utf-8 -*-
##### System wide lib #####

##### Theory lib #####
from theory.apps.command.baseCommand import SimpleCommand
# Just want to make ArrayField and gevent are compatible
from theory.contrib.postgres.fields import ArrayField

##### Theory third-party lib #####

##### Local app #####

##### Theory app #####

##### Misc #####

class GeventCmd(SimpleCommand):
  name = "geventCmd"
  verboseName = "geventCmd"

  def run(self, uiParam={}):
    from theory.thevent import gevent
    r = gevent.subprocess.check_output(["ls",])
    self._stdOut = "geventCmd"
    return r
