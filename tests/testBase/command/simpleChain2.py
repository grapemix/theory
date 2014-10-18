# -*- coding: utf-8 -*-
##### System wide lib #####

##### Theory lib #####

##### Theory third-party lib #####
from theory.apps.command.baseCommand import SimpleCommand

##### Local app #####
from .baseChain2 import BaseChain2

##### Theory app #####

##### Misc #####

class SimpleChain2(BaseChain2, SimpleCommand):
  name = "simpleChain2"
  verboseName = "simpleChain2"
