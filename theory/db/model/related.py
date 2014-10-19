from collections import namedtuple

from theory.utils.encoding import smartText
from theory.db.model.fields import BLANK_CHOICE_DASH

# PathInfo is used when converting lookups (fk__somecol). The contents
# describe the relation in Model terms (modal Options and Fields for both
# sides of the relation. The joinField is the field backing the relation.
PathInfo = namedtuple('PathInfo',
           'fromOpts toOpts targetFields joinField '
           'm2m direct')


class RelatedObject(object):
  def __init__(self, parentModel, modal, field):
    self.parentModel = parentModel
    self.modal = modal
    self.opts = modal._meta
    self.field = field
    self.name = '%s:%s' % (self.opts.appLabel, self.opts.modelName)
    self.varName = self.opts.modelName

  def getChoices(self, includeBlank=True, blankChoice=BLANK_CHOICE_DASH,
          limitToCurrentlyRelated=False):
    """Returns choices with a default blank choices included, for use
    as SelectField choices for this field.

    Analogue of theory.db.model.fields.Field.getChoices, provided
    initially for utilization by RelatedFieldListFilter.
    """
    firstChoice = blankChoice if includeBlank else []
    queryset = self.modal._defaultManager.all()
    if limitToCurrentlyRelated:
      queryset = queryset.complexFilter(
        {'%s__isnull' % self.parentModel._meta.modelName: False})
    lst = [(x._getPkVal(), smartText(x)) for x in queryset]
    return firstChoice + lst

  def getDbPrepLookup(self, lookupType, value, connection, prepared=False):
    # Defer to the actual field definition for db prep
    return self.field.getDbPrepLookup(lookupType, value,
            connection=connection, prepared=prepared)

  def editableFields(self):
    "Get the fields in this class that should be edited inline."
    return [f for f in self.opts.fields + self.opts.manyToMany if f.editable and f != self.field]

  def __repr__(self):
    return "<RelatedObject: %s related to %s>" % (self.name, self.field.name)

  def getAccessorName(self):
    # This method encapsulates the logic that decides what name to give an
    # accessor descriptor that retrieves related many-to-one or
    # many-to-many objects. It uses the lower-cased objectName + "Set",
    # but this can be overridden with the "relatedName" option.
    if self.field.rel.multiple:
      # If this is a symmetrical m2m relation on self, there is no reverse accessor.
      if getattr(self.field.rel, 'symmetrical', False) and self.modal == self.parentModel:
        return None
      return self.field.rel.relatedName or (self.opts.modelName + 'Set')
    else:
      return self.field.rel.relatedName or (self.opts.modelName)

  def getCacheName(self):
    return "_%sCache" % self.getAccessorName()

  def getPathInfo(self):
    return self.field.getReversePathInfo()
