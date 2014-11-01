# -*- coding: utf-8 -*-
#!/usr/bin/env python
##### System wide lib #####
import datetime

##### Theory lib #####
from theory.contrib.postgres.fields import ArrayField
from theory.db import model
from theory.utils.translation import ugettextLazy as _

##### Theory third-party lib #####

##### Local app #####

##### Theory app #####

##### Misc #####

__all__ = (
      "Command", "Mood", "Adapter", "History", "Parameter",
      "AdapterBuffer", "AppModel", "BinaryClassifierHistory",
      "FieldParameter"
  )

class Parameter(model.Model):
  name = model.CharField(
      maxLength=256,
      verboseName=_("Parameter's name"),
      helpText=_("The name of this parameter")
      )
  type = model.CharField(
      maxLength=256,
      verboseName=_("Parameter's type"),
      helpText=_("The type of this parameter")
      )
  command = model.ForeignKey("Command")

  isOptional = model.BooleanField(
      default=True,
      verboseName=_("Is optional flag"),
      helpText=_("Is optional flag")
      )
  isReadOnly = model.BooleanField(
      default=False,
      verboseName=_("Is read-only flag"),
      helpText=_("Is read-only flag")
      )
  comment = model.TextField(helpText=_("Parameter's comment"))

  def __str__(self):
    return self.name

class Mood(model.Model):
  name = model.CharField(
      maxLength=256,
      verboseName=_("Name"),
      helpText=_("Mood name")
      )

  def __str__(self):
    return self.name

class Command(model.Model):
  RUN_MODE_SIMPLE = 1
  RUN_MODE_ASYNC = 2

  RUN_MODE_CHOICES = (
      (RUN_MODE_SIMPLE, 'Simple run-mode'),
      (RUN_MODE_ASYNC, 'Async run-mode'),
  )

  name = model.CharField(
      maxLength=256,
      verboseName=_("Name"),
      helpText=_("Command name")
      )
  app = model.CharField(
      maxLength=256,
      verboseName=_("Application"),
      #uniqueWith="name",
      helpText=_("The applications which carry this command")
      )
  moodSet = model.ManyToManyField(
      Mood,
      verboseName=_("MoodSet"),
      helpText=_("The moods which carry this command")
      )
  #param = model.ForeignKey(
  #    Parameter,
  #    verboseName=_("Parameter"),
  #    helpText=_("The parameters of this command")
  #    )
  sourceFile = model.CharField(
      maxLength=1024,
      helpText=_("Command's source code location")
      )
  comment = model.TextField(
      null=True,
      blank=True,
      helpText=_("Command's comment")
      )
  # We have to do reverse_delete_rule=CASCADE) ourself to avoid inf loop
  nextAvblCmd = model.ManyToManyField(
      "self",
      null=True,
      blank=True,
      verboseName=_("Next available command"),
      helpText=_("The commands which are able to concatenate the result of this command")
      )
  runMode = model.IntegerField(
      choices=RUN_MODE_CHOICES,
      default=RUN_MODE_SIMPLE,
      helpText=_("The way how this command to be run. Most users should neglect this field.")
      )

  def getDetailAutocompleteHints(self, crlf):
    comment = lambda x: x if(x) else "No comment"
    hints = "%s -- %s%sParameters:" % (self.name, comment(self.comment), crlf)

    for i in self.parameterSet.all():
      if(i.isOptional):
        hints += crlf + "(%s) [%s]: %s" % (i.type, i.name, comment(i.comment))
      else:
        hints += crlf + "(%s) %s: %s" % (i.type, i.name, comment(i.comment))
    hints += crlf + '<a href="%s">Source File</a>' % (self.sourceFile)
    return hints

  def getAutocompleteHints(self):
    comment = self.comment if(self.comment) else "No comment"
    param = ",".join([i.name for i in self.parameterSet.filter(isOptional=False)])
    optionalParam = ",".join([i.name for i in self.parameterSet.filter(isOptional=True)])
    if(optionalParam!=""):
      if(param):
        optionalParam = ", [%s]" % (optionalParam)
      else:
        optionalParam = "[%s]" % (optionalParam)
    return "%s(%s%s) -- %s" % (self.name, param, optionalParam, comment)

  @property
  def className(self):
    return self.name[0].upper() + self.name[1:]

  @property
  def moduleImportPath(self):
    return "%s.command.%s" % (self.app, self.name)

  @property
  def classImportPath(self):
    return "%s.command.%s.%s" % (self.app, self.name, self.className)

  def __str__(self):
    return "{0} - {1}".format(self.app, self.name)

class History(model.Model):
  commandName = model.CharField(
      maxLength=256,
      verboseName=_("Command in Text"),
      helpText=_("Command in Text including paramter")
      )
  # Temp diable. During the development stage, reprobeAllModule is run almost
  # everytime which delete all command module. However, since the
  # reverse_delete_rule of the command field is cascade, all history record
  # will be lost. This field should re-enable in the future.
  #command = ReferenceField(Command, required=True,\
  #    reverse_delete_rule=CASCADE)
  moodSet = model.ManyToManyField(
      Mood,
      verboseName=_("MoodSet"),
      helpText=_("The moods where the command being executed")
      )
  jsonData = model.TextField(
      verboseName=_("Json data"),
      helpText=_(
        "The data from the command paramForm and stored in JSON format"
        )
      )
  touched = model.DateTimeField(
      default=datetime.datetime.utcnow()
      )
  repeated = model.IntegerField(default=1)

  meta = {
      'ordering': ['-touched',]
  }

class Adapter(model.Model):
  name = model.CharField(
      maxLength=256,
      verboseName=_("Adapter name"),
      helpText=_("Adapter name")
      )
  importPath = model.CharField(
      maxLength=256,
      verboseName=_("Import Path"),
      unique=True,
      helpText=_("The path to import the adapter")
      )
  propertyLst = ArrayField(
      model.TextField(),
      default=[],
      verboseName=_("PropertyLst"),
      helpText=_("The properties which accepted by this adapter")
      )

  #propertyInTxt = model.TextField(
  #    null=True,
  #    blank=True,
  #    verboseName=_("PropertyLst"),
  #    helpText=_("The properties which accepted by this adapter")
  #    )

  #@property
  #def propertyLst(self):
  #  return self.propertyInTxt.split(",")

  #@propertyLst.setter
  #def propertyLst(self, propertyLst):
  #  self.propertyInTxt = ",".join(propertyLst)

  def __str__(self):
    return self.name

class AdapterBuffer(model.Model):
  """This model is designed as a buffer for adapters between async commands"""
  fromCmd = model.ForeignKey(
      "Command",
      verboseName=_("From command"),
      helpText=_("The input command of the adapter")
      )
  toCmd = model.ForeignKey(
      "Command",
      verboseName=_("To command"),
      helpText=_("The output command of the adapter")
      )
  adapter = model.ForeignKey(
      "Adapter",
      verboseName=_("adapter"),
      helpText=_("The adapter being used")
      )
  data = model.TextField(
      verboseName=_("data"),
      null=True,
      blank=True,
      helpText=_("The data adapted to next command and stored in JSON format")
      )
  created = model.DateTimeField(default=datetime.datetime.utcnow())

  def __str__(self):
    return "{0} -> {1} ({2})".format(
        Command.objects.only("name").get(id=self.fromCmd.id).name,
        Command.objects.only("name").get(id=self.toCmd.id).name,
        self.created
        )

class BinaryClassifierHistory(model.Model):
  ref = model.IntegerField()
  initState = ArrayField(model.BooleanField())
  finalState = ArrayField(model.BooleanField())

class FieldParameter(model.Model):
  name = model.CharField(
      maxLength=256,
      verboseName=_("Parameter's name"),
      helpText=_(
        "The name of this parameter. Regard as args if name is missing"
        )
      )
  data = model.TextField(
      verboseName=_("Parameter's value"),
      helpText=_("The type of this parameter"),
      #required=True,
      )
  isField = model.BooleanField(
      default=False,
      verboseName=_("Is a field flag"),
      helpText=_("Is a field flag")
      )
  isCircular = model.BooleanField(
      default=False,
      verboseName=_("Is circular graph flag"),
      helpText=_("Is circular graph flag")
      )
  parent = model.ForeignKey(
      "FieldParameter",
      null=True,
      blank=True,
      relatedName="childParamLst",
      relatedQueryName="childParam",
      verboseName=_("Field name and parameter list"),
      helpText=_("All fields' name and their parameter"),
      )
  appModel = model.ForeignKey(
      "AppModel",
      relatedName="fieldParamMap",
      verboseName=_("Field name and parameter map"),
      helpText=_("All fields' name and their parameter"),
      )

  def __str__(self):
    return self.name

class AppModel(model.Model):
  name = model.CharField(
      maxLength=256,
      verboseName=_("App model name"),
      helpText=_("Application model name"),
      #uniqueWith="app",
      )
  app = model.CharField(
      maxLength=256,
      verboseName=_("Application name"),
      helpText=_("Application name")
      )
  tblField = ArrayField(
      model.TextField(maxLength=64),
      verboseName=_("Table field"),
      helpText=_("The fields being showed in a table")
      )
  formField = ArrayField(
      model.TextField(maxLength=64),
      verboseName=_("Form field"),
      helpText=_("The fields being showed in a form")
      )
  #fieldParamMap = model.ForeignKey(
  #    FieldParameter,
  #    verboseName=_("Field name and parameter map"),
  #    helpText=_("All fields' name and their parameter"),
  #    #required=True,
  #    )
  importPath = model.CharField(
      maxLength=256,
      verboseName=_("Import path"),
      unique=True,
      helpText=_("The path to import the model")
      )
  importanceRating = model.IntegerField(
      default=0,
      verboseName=_("importance rating"),
      helpText=_("""The level of importance of this model to the app. The
        higher the rating, the more important model to the app."""),
      )

  def __str__(self):
    return "{0} - {1}".format(self.app, self.name)
