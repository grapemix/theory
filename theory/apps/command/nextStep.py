# -*- coding: utf-8 -*-
#!/usr/bin/env python
##### System wide lib #####

##### Theory lib #####
from theory.apps.command.baseCommand import SimpleCommand
from theory.apps.model import AdapterBuffer, Command
from theory.conf import settings
from theory.core.bridge import Bridge
from theory.gui import field

##### Theory third-party lib #####

##### Local app #####

##### Theory app #####

##### Misc #####

__all__ = ("NextStep", )

class ParamForm(SimpleCommand.ParamForm):
  # This form can move to somewhere else if we like
  commandReady = field.ChoiceField(
      choices=(),
      label="Command Ready",
      helpText="Select a command ready to be continued"
      )

  def __init__(self, *args, **kwargs):
    super(ParamForm, self).__init__(*args, **kwargs)
    self.fields["commandReady"].choices = self.getCommandChoiceLst()

  def getCommandChoiceLst(self):
    # example return value:  ((1, "command1"), (2, "command2"))
    return [(i.pk, str(i)) for i in AdapterBuffer.objects.all()]

class NextStep(SimpleCommand):
  """
  List all command which is ready for next step. In the first version,
  users are not allowed to pipe up command which has been just executed.
  """
  name = "nextStep"
  verboseName = "nextStep"
  _notations = ["Command",]
  ParamForm = ParamForm
  _drums = {"Dummy": 1}

  def __init__(self, *args, **kwargs):
    super(NextStep, self).__init__(*args, **kwargs)
    self.bridge = Bridge()

  def _executeCommand(self, cmd):
    cmdModel = self.adapterBufferModel.toCmd

    # Copied from core/reactor.py, should update this part if the original is
    # modified.
    if(not cmd.paramForm.is_valid()):
      # TODO: integrate with std reactor error system
      print cmd.paramForm.errors
      return

    # Copied from reactor, should be refactor to bridge in the futher
    self.bridge._executeCommand(cmd, cmdModel)

    debugLvl = settings.DEBUG_LEVEL
    bridge = Bridge()
    for adapterName, leastDebugLvl in cmd._drums.iteritems():
      if(leastDebugLvl<=debugLvl):
        (adapterModel, drum) = bridge.adaptFromCmd(adapterName, cmd)
        drum.render(uiParam=self._uiParam)
    self.adapterBufferModel.delete()

  def run(self):
    if(self.bridge == None):
      self.bridge = Bridge()
    cmdId = self.paramForm.clean()["commandReady"]
    self.adapterBufferModel = AdapterBuffer.objects.get(id=cmdId)

    self.bridge.bridgeFromDb(self.adapterBufferModel, self._executeCommand, self.uiParam)
