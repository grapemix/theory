# -*- coding: utf-8 -*-
##### System wide lib #####

##### Theory lib #####

##### Theory third-party lib #####
from theory.command.baseCommand import AsyncCommand

##### Local app #####
from .baseChain2 import BaseChain2

##### Theory app #####

##### Misc #####

class AsyncChain2(BaseChain2, AsyncCommand):
  name = "asyncChain2"
  verboseName = "asyncChain2"
