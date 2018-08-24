# -*- coding: utf-8 -*-
#!/usr/bin/env python
##### System wide lib #####
from abc import ABCMeta, abstractmethod
from collections import OrderedDict
import json

##### Theory lib #####

##### Theory third-party lib #####

##### Local app #####

##### Theory app #####

##### Misc #####

class TheoryModelDetectorBase(object):
  """This class detect the data type from theory fields, but it does not
  handle any data type."""
  __metaclass__ = ABCMeta

  def run(self, fieldParamMap):
    """
    :param queryset: db model instance queryset
    :param fieldNameFieldTypeLabelMap: To map the field name vs the db field
      type label as a string which still retain the nest relationship
    """

    self._buildTypeCatMap()
    propLst = []
    handlerLst = []

    for fieldParam in fieldParamMap:
      fieldName = fieldParam.name
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
          if i.name=="choices":
            handlerFxnName = self._typeCatMap["EnumField"][0]
            choices = i.data
            break

      propLst.append((fieldName, self._getFieldNameVsProp(
          handlerFxnName,
          choices,
          ""
      )))
      if handlerFxnName=="modelField":
        for childFieldParam in fieldParam.childParamLst.all():
          propLst[-1][1][childFieldParam.name] = childFieldParam.data

      handlerLst.append((fieldName, self._getFieldNameVsHandlerDict(
          handlerFxnName,
          ""
      )))
    self.fieldNameVsProp = OrderedDict(propLst)
    self.fieldNameVsHandlerDict = OrderedDict(handlerLst)

  def _getFieldNameVsProp(self, klassLabel, choices, prefix=""):
    r = {
        "klassLabel": prefix + klassLabel,
        "type": klassLabel[:-5],
    }
    if(choices is not None):
      r["choices"] = dict(json.loads(choices))
    return r

  @abstractmethod
  def _getFieldNameVsHandlerDict(self, klassLabel, prefix=""):
    pass

  @abstractmethod
  def _buildTypeCatMap(self):
    pass
