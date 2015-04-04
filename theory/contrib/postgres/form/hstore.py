from collections import OrderedDict
import json
from inspect import isclass

from theory.core.exceptions import ValidationError
from theory.gui.common.baseField import DictField
from theory.utils import six
from theory.utils.translation import ugettextLazy as _

__all__ = ['HStoreField']


class HStoreField(DictField):
  """A field for HStore data which accepts JSON input."""
  default_error_messages = {
      'invalidJson': _('Could not load JSON data.'),
  }

  @property
  def initData(self):
    return self._initData

  # Plz sync up with dictField's initData
  @initData.setter
  def initData(self, initData):
    initData = self.toPython(initData)
    self._initData = initData
    self.keyFields = []
    self.valueFields = []
    self._setupChildrenData(initData, "initData")
    self._changedData = self._finalData = {}

  def prepareValue(self, value):
    if isinstance(value, dict):
      if len(value) == 0:
        return ""
      else:
        return json.dumps(value)
    return value

  def toPython(self, value):
    if not value:
      return {}
    try:
      value = json.loads(value)
    except ValueError:
      raise ValidationError(
          self.error_messages['invalidJson'],
          code='invalidJson',
      )
    # Cast everything to strings for ease.
    for key, val in value.items():
      value[key] = six.textTypes(val)
    return value

  ## This is a special case of overriding multiple property methods
  ## This class now has an this propertyField with a modified getter
  ## so modify its setter rather than Parent.propertyField's setter.
  ## This is an examaple: @DictField.finalData.getter

  ## OK, since we have setter, we can simply use @property instead
  #@property
  #def finalData(self):
  #  """It is used to store data directly from widget before validation and
  #  cleaning."""
  #  # TODO: allow lazy update
  #  if(isclass(self.widget) or self.widget.isOverridedData):
  #    # some widget like Multibuttonentry from the e17 need special treatment
  #    # on retriving data
  #    return self.prepareValue(super(HStoreField, self).finalData)
  #  else:
  #    d = OrderedDict()
  #    for i in range(len(self.keyFields)):
  #      d[self.keyFields[i].finalData] = self.valueFields[i].finalData
  #    return self.prepareValue(d)

  #@finalData.setter
  #def finalData(self, finalData):
  #  if(not isinstance(self.widget, type) and self.widget.isOverridedData):
  #    DictField.finalData.fset(self, self.toPython(finalData))
  #  else:
  #    self._setupChildrenData(self.toPython(finalData), "finalData")

  def clean(self, valueOrderedDict, isEmptyForgiven=False):
    return self.prepareValue(
        super(HStoreField, self).clean(valueOrderedDict, isEmptyForgiven)
        )
