# -*- coding: utf-8 -*-
#!/usr/bin/env python
##### System wide lib #####
from datetime import datetime

##### Theory lib #####
from theory.db.models import *
from theory.utils.translation import ugettext_lazy as _

##### Theory third-party lib #####

##### Local app #####

##### Theory app #####

##### Misc #####

class Parameter(EmbeddedDocument):
  name = StringField(required=True, max_length=256,\
      verbose_name=_("Parameter's name"),\
      help_text=_("The name of this parameter"))
  type = StringField(max_length=256,\
      verbose_name=_("Parameter's type"),\
      help_text=_("The type of this parameter"))
  isOptional = BooleanField(default=True, verbose_name=_("Is optional flag"),\
      help_text=_("Is optional flag"))
  isReadOnly = BooleanField(default=False, verbose_name=_("Is read-only flag"),\
      help_text=_("Is read-only flag"))
  comment = StringField(help_text=_("Parameter's comment"))

class Command(Model):
  RUN_MODE_SIMPLE = 1
  RUN_MODE_ASYNC = 2

  RUN_MODE_CHOICES = (
      (RUN_MODE_SIMPLE, 'Simple run-mode'),
      (RUN_MODE_ASYNC, 'Async run-mode'),
  )

  name = StringField(required=True, max_length=256,\
      verbose_name=_("Command"),\
      help_text=_("Command name"))
  app = StringField(max_length=256,\
      required=True,
      verbose_name=_("Application"),\
      unique_with="name",\
      help_text=_("The applications which carry this command"))
  mood = ListField(StringField(max_length=256,\
      required=True,
      verbose_name=_("Mood"),\
      help_text=_("The moods which carry this command")))
  param = SortedListField(EmbeddedDocumentField(Parameter),\
      verbose_name=_("Parameter"),\
      help_text=_("The parameters of this command"))
  sourceFile = StringField(help_text=_("Command's source code location"))
  comment = StringField(help_text=_("Command's comment"))
  # We have to do reverse_delete_rule=CASCADE) ourself to avoid inf loop
  nextAvblCmd = ListField(ReferenceField("self"), \
      verbose_name=_("Next available command"),\
      help_text=_("The commands which are able to concatenate the result of this command"))
  runMode = IntField(\
      choices=RUN_MODE_CHOICES, default=RUN_MODE_SIMPLE,
      help_text=_("The way how this command to be run. Most users should neglect this field."))

  def getDetailAutocompleteHints(self, crlf):
    comment = lambda x: x if(x) else "No comment"
    hints = "%s -- %s%sParameters:" % (self.name, comment(self.comment), crlf)

    for i in self.param:
      if(i.isOptional):
        hints += crlf + "(%s) [%s]: %s" % (i.type, i.name, comment(i.comment))
      else:
        hints += crlf + "(%s) %s: %s" % (i.type, i.name, comment(i.comment))
    hints += crlf + '<a href="%s">Source File</a>' % (self.sourceFile)
    return hints

  def getAutocompleteHints(self):
    comment = self.comment if(self.comment) else "No comment"
    param = ",".join([i.name for i in self.param if(not i.isOptional)])
    optionalParam = ",".join([i.name for i in self.param if(i.isOptional)])
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

class History(Model):
  commandName = StringField(required=True,\
      verbose_name=_("Command in Text"),\
      help_text=_("Command in Text including paramter"))
  # Temp diable. During the development stage, reprobeAllModule is run almost
  # everytime which delete all command module. However, since the
  # reverse_delete_rule of the command field is cascade, all history record
  # will be lost. This field should re-enable in the future.
  #command = ReferenceField(Command, required=True,\
  #    reverse_delete_rule=CASCADE)
  mood = StringField(max_length=256,\
      required=True,
      verbose_name=_("Mood"),\
      help_text=_("The moods where the command being executed"))
  touched = DateTimeField(required=True, default=datetime.utcnow())
  repeated = IntField(default=1)

  meta = {
      'ordering': ['-touched',]
  }


class Adapter(Model):
  name = StringField(required=True, max_length=256,\
      verbose_name=_("Adapter name"),\
      help_text=_("Adapter name"))
  importPath = StringField(max_length=256,\
      required=True,
      verbose_name=_("Import Path"),\
      unique=True,\
      help_text=_("The path to import the adapter"))
  property = ListField(StringField(max_length=256,\
      verbose_name=_("Property"),\
      help_text=_("The properties which accepted by this adapter")))

class AdapterBuffer(Model):
  """This model is designed as a buffer for adapters between async commands"""
  fromCmd = ReferenceField("Command", \
      required=True, \
      verbose_name=_("From command"),\
      help_text=_("The input command of the adapter"))
  toCmd = ReferenceField("Command", \
      verbose_name=_("To command"),\
      required=True, \
      help_text=_("The output command of the adapter"))
  adapter = ReferenceField("Adapter", \
      verbose_name=_("adapter"),\
      required=True, \
      help_text=_("The adapter being used"))
  data = StringField(required=True, \
      verbose_name=_("data"), \
      help_text=_("The data adapted to next command and stored in JSON format"))
  created = DateTimeField(required=True, default=datetime.utcnow())

class BinaryClassifierHistory(Model):
  ref = GenericReferenceField()
  initState = SortedListField(BooleanField())
  finalState = SortedListField(BooleanField())

class AppModel(Model):
  name = StringField(
      required=True,
      max_length=256,
      verbose_name=_("App model name"),
      help_text=_("Application model name"),
      unique_with="app",
      )
  app = StringField(
      required=True,
      max_length=256,
      verbose_name=_("Application name"),
      help_text=_("Application name")
      )
  tblField = SortedListField(
      StringField(
        max_length=256,
        verbose_name=_("Table field"),
        help_text=_("The fields being showed in a table")
        ),
      required=True,
      )
  formField = SortedListField(
      StringField(
        max_length=256,
        verbose_name=_("Form field"),
        help_text=_("The fields being showed in a form")
        ),
      required=True,
      )
  fieldNameTypeMap = MapField(
      field=StringField(max_length=256,),
      verbose_name=_("Field name and type map"),
      help_text=_("All fields' name and their type"),
      required=True,
      )
  importPath = StringField(
      max_length=256,
      required=True,
      verbose_name=_("Import path"),
      unique=True,
      help_text=_("The path to import the adapter")
      )
