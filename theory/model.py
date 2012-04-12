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
  mood = StringField(max_length=256,\
      required=True,
      verbose_name=_("Mood"),\
      help_text=_("The moods which carry this command"))
  param = ListField(EmbeddedDocumentField(Parameter),\
      verbose_name=_("Parameter"),\
      help_text=_("The parameters of this command"))
  sourceFile = StringField(help_text=_("Command's source code location"))
  comment = StringField(help_text=_("Command's comment"))

class History(Document):
  command = StringField(required=True,\
      verbose_name=_("Command"),\
      help_text=_("Command being executer"))
  commandRef = ReferenceField(Command, required=True,\
      reverse_delete_rule=CASCADE)
  mood = StringField(max_length=256,\
      required=True,
      verbose_name=_("Mood"),\
      help_text=_("The moods where the command being executed"))
  touched = DateTimeField(required=True, default=datetime.utcnow())
  repeated = IntField(default=1)

