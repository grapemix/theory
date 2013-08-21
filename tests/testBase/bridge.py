# -*- coding: utf-8 -*-
##### System wide lib #####
import simplejson as json

##### Theory lib #####
from theory.core.bridge import Bridge as TheoryBridge

##### Theory third-party lib #####

##### Local app #####

##### Theory app #####

##### Misc #####

class Bridge(TheoryBridge):
  """It is just a mock object. This fxn must be synced with the original bridge.
  Instead of delay(), the AsyncCommand is run as run() to skip the celery setup.
  """
  def _execeuteCommand(self, cmd, cmdModel, uiParam={}):
    if(cmdModel.runMode==cmdModel.RUN_MODE_ASYNC):
      paramFormData = json.loads(cmd.paramForm.toJson())
      cmd.run(paramFormData=paramFormData)
    else:
      if(not cmd.paramForm.is_valid()):
        return False
      cmd._uiParam = uiParam
      cmd.run(uiParam)
    return True


