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

class MongoModelDetectorBase(object):
  """This class detect the data type from MongoDB fields, but it does not
  handle any data type."""
  __metaclass__ = ABCMeta

  def __init__(self):
    self.fieldPropDict = OrderedDict()

  def run(self, queryset, fieldNameFieldTypeLabelMap):
    """
    :param queryset: db model instance queryset
    :param fieldNameFieldTypeLabelMap: To map the field name vs the db field
      type label as a string which still retain the nest relationship
    """
    self.queryset = queryset

    self._buildTypeCatMap()
    for fieldName, fieldTypeLabel in fieldNameFieldTypeLabelMap.iteritems():
      fieldTypeLabelTokenLst = fieldTypeLabel.split(".")
      handlerFxnName = ""
      for fieldTypeLabelToken in fieldTypeLabelTokenLst:
        if(handlerFxnName==""):
          fieldTypeLabelToken = fieldTypeLabelToken.split("_")[0]
          # When it is in top level, we treated it as normal
          handlerFxnName = self._typeCatMap[fieldTypeLabelToken][0]
        elif(handlerFxnName=="nonEditableForceStrField"):
          break
        else:
          fieldTypeLabelToken = fieldTypeLabelToken.split("_")[0]
          # When it is NOT in top level, we treated it as child
          handlerFxnName += self._typeCatMap[fieldTypeLabelToken][1]
      if(handlerFxnName=="intField" and \
          hasattr(
            getattr(self.queryset[0].__class__, fieldName),
            "choices"
          ) and \
          getattr(
            getattr(self.queryset[0].__class__, fieldName),
            "choices"
            ) is not None
          ):
        handlerFxnName = self._typeCatMap["EnumField"][0]
        self.fieldPropDict[fieldName] = self._fillUpTypeHandler(
            handlerFxnName,
            ""
            )
        self.fieldPropDict[fieldName]["choices"] = \
            dict(
                getattr(
                  getattr(self.queryset[0].__class__, fieldName),
                  "choices"
                )
            )
      else:
        self.fieldPropDict[fieldName] = self._fillUpTypeHandler(
            handlerFxnName,
            ""
            )

  @abstractmethod
  def _fillUpTypeHandler(self, klassLabel, prefix=""):
    pass

  @abstractmethod
  def _buildTypeCatMap(self):
    pass
