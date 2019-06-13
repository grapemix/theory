# -*- coding: utf-8 -*-
#!/usr/bin/env python
##### System wide lib #####

##### Theory lib #####

##### Theory third-party lib #####

##### Local app #####

##### Theory app #####
from theory.gui.transformer.theoryModelBSONTblDataHandler \
    import TheoryModelBSONTblDataHandler

##### Misc #####

class TheoryModelTblDataHandler(TheoryModelBSONTblDataHandler):
  """
  This class handle the data conversion from MongoDB. Not being used
  currently. The reason for using this class instead of
  MongoModelBSONDataHandler is because the list of string will be handled
  without quotation which allow user to type less. On the other hand, it will
  be not as safe as BSON handler which guarantee the conversion safety.
  """

  def _editableForceStrFieldDataHandler(self, rowId, fieldName, fieldVal):
    return str(fieldVal)

  def _listFieldeditableForceStrFieldDataHandler(
      self,
      rowId,
      fieldName,
      fieldVal
      ):
    return fieldVal


