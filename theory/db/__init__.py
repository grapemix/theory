# -*- coding: utf-8 -*-
##### System wide lib #####
from mongoengine import *

##### Theory lib #####
from theory.conf import settings

##### Theory third-party lib #####

##### Local app #####

##### Theory app #####

##### Misc #####

for alias, database in settings.DATABASES.items():
  if(database["ENGINE"]=="theory.db.mongoengine"):
    connect(database["NAME"], port=int(database["PORT"]))
