# -*- coding: utf-8 -*-
#!/usr/bin/env python
##### System wide lib #####
import os
from shutil import copytree

##### Theory lib #####
from theory.command.baseCommand import SimpleCommand
from theory.conf import settings
from theory.gui import field
from theory.gui.form import StepForm
from theory.model import AdapterBuffer

##### Theory third-party lib #####

##### Local app #####

##### Theory app #####

##### Misc #####

class NextStep(SimpleCommand):
  """
  List all command which is ready for next step and execute the chosen command
  """
  name = "nextStep"
  verboseName = "nextStep"
  _notations = ["Command",]

  class OptionForm(StepForm):
    command = field.ChoiceField(label="Command", help_text="Select a command to be executed")


  def _getCommandLst(self):
    print AdapterBuffer.objects.all()
    return [(i.pk, "%s -> %s (%s)" % (i.fromCmd, i.toCmd, i.created)) \
        for i in AdapterBuffer.objects.all()]

  def _execute(self, btn):
    if(self.optionForm.is_valid()):
      print self.optionForm.clean()

  def _renderForm(self, *args, **kwargs):
    win = kwargs["uiParam"]["win"]
    bx = kwargs["uiParam"]["bx"]
    bx.clear()

    o = self.OptionForm(win, bx)
    o._nextBtnClick = self._execute
    #o.fields["command"].choices = self._getCommandLst()
    o.fields["command"].choices = ((1, "a"), (2, "b"))
    o.generateForm()
    o.generateStepControl()
    return o


  def run(self, *args, **kwargs):
    self.optionForm = self._renderForm(uiParam={"win": settings.CRTWIN, "bx": settings.CRT})
