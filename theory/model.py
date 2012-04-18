# -*- coding: utf-8 -*-
##### System wide lib #####
from datetime import datetime
from theory.db.models import *

##### Theory lib #####
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

class Command(Document):
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

  @property
  def className(self):
    return self.name[0].upper() + self.name[1:]

class History(Document):
  command = StringField(required=True,\
      verbose_name=_("Command in Text"),\
      help_text=_("Command in Text including paramter"))
  commandRef = ReferenceField(Command, required=True,\
      reverse_delete_rule=CASCADE)
  mood = StringField(max_length=256,\
      required=True,
      verbose_name=_("Mood"),\
      help_text=_("The moods where the command being executed"))
  touched = DateTimeField(required=True, default=datetime.utcnow())
  repeated = IntField(default=1)

class Adapter(Document):
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


