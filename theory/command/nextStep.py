# -*- coding: utf-8 -*-
#!/usr/bin/env python
##### System wide lib #####

##### Theory lib #####
from theory.command.baseCommand import SimpleCommand
from theory.core.bridge import Bridge
from theory.gui import field
from theory.model import AdapterBuffer, Command

##### Theory third-party lib #####

##### Local app #####

##### Theory app #####

##### Misc #####

__all__ = ("NextStep", )

class ParamForm(SimpleCommand.ParamForm):
  # This form can move to somewhere else if we like
  commandReady = field.ChoiceField(choices=(),\
      label="Command Ready", help_text="Select a command ready to be continued")

  def __init__(self, *args, **kwargs):
    super(ParamForm, self).__init__(*args, **kwargs)
    self.fields["commandReady"].choices = self.getCommandChoiceLst()

  def getCommandChoiceLst(self):
    # example return value:  ((1, "command1"), (2, "command2"))
    return [(i.pk, "%s -> %s (%s)" % \
        (Command.objects.get(id=i.fromCmd.id).name, \
        Command.objects.get(id=i.toCmd.id).name, \
        i.created)) \
        for i in AdapterBuffer.objects.all()]

class NextStep(SimpleCommand):
  """
  List all command which is ready for next step. In the first version,
  users are not allowed to pipe up command which has been just executed.
  """
  name = "nextStep"
  verboseName = "nextStep"
  _notations = ["Command",]
  ParamForm = ParamForm

  def __init__(self, *args, **kwargs):
    super(NextStep, self).__init__(*args, **kwargs)
    self.bridge = Bridge()

  def run(self, *args, **kwargs):
    if(self.paramForm.is_valid()):
      if(self.bridge == None):
        self.bridge = Bridge()
      cmdId = self.paramForm.clean()["commandReady"]
      adapterBufferModel = AdapterBuffer.objects.get(id=cmdId)

      cmd = self.bridge.bridgeFromDb(adapterBufferModel)
      cmdModel = adapterBufferModel.toCmd
      self.bridge._execeuteCommand(cmd, cmdModel)
    else:
      # TODO: integrate with std reactor error system
      print self.paramForm.errors
