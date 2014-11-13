# -*- coding: utf-8 -*-
#!/usr/bin/env python
##### System wide lib #####
from abc import ABCMeta, abstractmethod
from collections import OrderedDict

##### Theory lib #####

##### Theory third-party lib #####

##### Local app #####

##### Theory app #####

##### Misc #####

class TheoryModelDetectorBase(object):
  """This class detect the data type from theory fields, but it does not
  handle any data type."""
  __metaclass__ = ABCMeta

  def __init__(self):
    self.fieldPropDict = OrderedDict()

  def run(self, fieldParamMap):
    """
    :param queryset: db model instance queryset
    :param fieldNameFieldTypeLabelMap: To map the field name vs the db field
      type label as a string which still retain the nest relationship
    """

    self._buildTypeCatMap()

    #for fieldName, fieldParam in fieldParamMap.iteritems():
    for fieldParam in fieldParamMap:
      fieldName = fieldParam.name
      #handlerFxnName = self._typeCatMap[fieldParam.name][0]
      if not fieldParam.isField:
        continue
      handlerFxnName = self._typeCatMap[fieldParam.data][0]
      choices = None
      if(handlerFxnName=="listField"):
        handlerFxnName += self._typeCatMap[
            fieldParam.childParamLst.first().data
            ][1]
      elif(handlerFxnName=="intField"):
        for i in fieldParam.childParamLst.all():
          if(i.name=="choices"):
            handlerFxnName = self._typeCatMap["EnumField"][0]
            choices = i.data
            break

      self.fieldPropDict[fieldName] = self._fillUpTypeHandler(
          handlerFxnName,
          ""
          )
      if(choices is not None):
        self.fieldPropDict[fieldName]["choices"] = dict(i.data)

  @abstractmethod
  def _fillUpTypeHandler(self, klassLabel, prefix=""):
    pass

  @abstractmethod
  def _buildTypeCatMap(self):
    pass
