# -*- coding: utf-8 -*-
#!/usr/bin/env python
##### System wide lib #####

##### Theory lib #####
from theory.apps.model import Command
from theory.core.cmdParser.txtCmdParser import TxtCmdParser
from theory.db.model import Q
from theory.utils.importlib import importClass

##### Theory third-party lib #####

##### Local app #####

##### Theory app #####

##### Misc #####

__all__ = ('AutoCompleteMixin',)


class AutoCompleteMixin(object):
  autocompleteCounter = 0
  lastAutocompleteFrag = ""
  originalQuest = ""

  def __init__(self, *args, **kwargs):
    self.parser = TxtCmdParser()
    super(AutoCompleteMixin, self).__init__()

  def _autocompleteRequest(self, cmdPartialName):
    self.parser.cmdInTxt = cmdPartialName
    self.parser.run()
    (mode, frag) = self.parser.partialInput
    self.actionQ.append({
      "action": "cleanUpCrt",
    })
    if mode == self.parser.MODE_ERROR:
      # Not doing anything in here, but the cleanUpCrt() and initVar() will
      # still be run
      self.actionQ.append({
        "action": "printStdOut",
        "val": "Your command '{0}' is invalid".format(cmdPartialName)
      })
      self.parser.initVar()
    elif mode == self.parser.MODE_COMMAND:
      (entryOutput, crtOutput)= self._queryCommandAutocomplete(frag)
      if crtOutput:
        self.actionQ.append({
          "action": "printStdOut",
          "val": crtOutput
        })
        self.actionQ.append({
          "action": "setCmdLine",
          "val": entryOutput
        })
        self.actionQ.append({
          "action": "selectCmdLine",
          "val": "{0},{1}".format(len(cmdPartialName), len(entryOutput))
        })
      else:
        self.actionQ.append({
          "action": "setCmdLine",
          "val": entryOutput
        })
      self.parser.initVar()
    elif mode == self.parser.MODE_ARGS:
      if self._loadCmdModel():
        cmdParamFormKlass = importClass(self.cmdModel.classImportPath).ParamForm
        cmdParamForm = cmdParamFormKlass()

        self.paramFormCache[self.cmdModel.id] =  cmdParamForm
        try:
          self.actionQ.append({
            "action": "buildParamForm",
            "val": self._buildCmdForm(None)
          })
          self.actionQ.append({
            "action": "focusOnParamFormFirstChild",
          })
        except Exception as e:
          self.logger.error(e, exc_info=True)
          self.actionQ.append({
            "action": "printStdOut",
            "val": "Internal err. Check your log"
          })
      else:
        self.actionQ.append({
          "action": "cleanUpCrt",
        })
        self.actionQ.append({
          "action": "printStdOut",
          "val": "Your command '{0}' is invalid".format(cmdPartialName)
        })

  def _queryCommandAutocomplete(self, frag):
    # which means user keeps tabbing
    if self.lastAutocompleteFrag == frag:
      frag = self.originalQuest
      self.autocompleteCounter += 1
    else:
      self.autocompleteCounter = 0
      self.lastAutocompleteFrag = ""
      self.originalQuest = ""

    cmdModelQuery = Command.objects.filter(
        Q(name__startswith=frag) & \
        (Q(moodSet__name=self.moodName) | Q(moodSet__name="norm"))
        )
    cmdModelQueryNum = cmdModelQuery.count()
    if cmdModelQueryNum == 0:
      return (self.parser.cmdInTxt, None)
    elif cmdModelQueryNum == 1:
      if cmdModelQuery[0].name == frag:
        crtOutput = cmdModelQuery[0].getDetailAutocompleteHints("\n")
      else:
        crtOutput = None
      return (cmdModelQuery[0].name, crtOutput)
    elif cmdModelQueryNum > 1:
      suggest = cmdModelQuery[self.autocompleteCounter % cmdModelQueryNum].name
      if self.autocompleteCounter == 0:
        self.originalQuest = frag
      self.lastAutocompleteFrag = frag
      crtOutput = "\n".join([i.getAutocompleteHints() for i in cmdModelQuery])
      # e.x: having commands like blah, blah1, blah2
      if frag == suggest:
        crtOutput += "\n\n" + cmdModelQuery[self.autocompleteCounter % cmdModelQueryNum]\
            .getDetailAutocompleteHints("\n")
      return (suggest, crtOutput)
