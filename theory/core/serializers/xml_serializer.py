"""
XML serializer.
"""

from __future__ import unicode_literals

from theory.apps import apps
from theory.conf import settings
from theory.core.serializers import base
from theory.db import model, DEFAULT_DB_ALIAS
from theory.utils.xmlutils import SimplerXMLGenerator
from theory.utils.encoding import smartText
from xml.dom import pulldom
from xml.sax import handler
from xml.sax.expatreader import ExpatParser as _ExpatParser


class Serializer(base.Serializer):
  """
  Serializes a QuerySet to XML.
  """

  def indent(self, level):
    if self.options.get('indent', None) is not None:
      self.xml.ignorableWhitespace('\n' + ' ' * self.options.get('indent', None) * level)

  def startSerialization(self):
    """
    Start serialization -- open the XML document and the root element.
    """
    self.xml = SimplerXMLGenerator(self.stream, self.options.get("encoding", settings.DEFAULT_CHARSET))
    self.xml.startDocument()
    self.xml.startElement("theory-objects", {"version": "1.0"})

  def endSerialization(self):
    """
    End serialization -- end the document.
    """
    self.indent(0)
    self.xml.endElement("theory-objects")
    self.xml.endDocument()

  def startObject(self, obj):
    """
    Called as each object is handled.
    """
    if not hasattr(obj, "_meta"):
      raise base.SerializationError("Non-model object (%s) encountered during serialization" % type(obj))

    self.indent(1)
    attrs = {"model": smartText(obj._meta)}
    if not self.useNaturalPrimaryKeys or not hasattr(obj, 'naturalKey'):
      objPk = obj._getPkVal()
      if objPk is not None:
        attrs['pk'] = smartText(objPk)

    self.xml.startElement("object", attrs)

  def endObject(self, obj):
    """
    Called after handling all fields for an object.
    """
    self.indent(1)
    self.xml.endElement("object")

  def handleField(self, obj, field):
    """
    Called to handle each field on an object (except for ForeignKeys and
    ManyToManyFields)
    """
    self.indent(2)
    self.xml.startElement("field", {
      "name": field.name,
      "type": field.getInternalType()
    })

    # Get a "string version" of the object's data.
    if getattr(obj, field.name) is not None:
      self.xml.characters(field.valueToString(obj))
    else:
      self.xml.addQuickElement("None")

    self.xml.endElement("field")

  def handleFkField(self, obj, field):
    """
    Called to handle a ForeignKey (we need to treat them slightly
    differently from regular fields).
    """
    self._startRelationalField(field)
    relatedAtt = getattr(obj, field.getAttname())
    if relatedAtt is not None:
      if self.useNaturalForeignKeys and hasattr(field.rel.to, 'naturalKey'):
        related = getattr(obj, field.name)
        # If related object has a natural key, use it
        related = related.naturalKey()
        # Iterable natural keys are rolled out as subelements
        for keyValue in related:
          self.xml.startElement("natural", {})
          self.xml.characters(smartText(keyValue))
          self.xml.endElement("natural")
      else:
        self.xml.characters(smartText(relatedAtt))
    else:
      self.xml.addQuickElement("None")
    self.xml.endElement("field")

  def handleM2mField(self, obj, field):
    """
    Called to handle a ManyToManyField. Related objects are only
    serialized as references to the object's PK (i.e. the related *data*
    is not dumped, just the relation).
    """
    if field.rel.through._meta.autoCreated:
      self._startRelationalField(field)
      if self.useNaturalForeignKeys and hasattr(field.rel.to, 'naturalKey'):
        # If the objects in the m2m have a natural key, use it
        def handleM2m(value):
          natural = value.naturalKey()
          # Iterable natural keys are rolled out as subelements
          self.xml.startElement("object", {})
          for keyValue in natural:
            self.xml.startElement("natural", {})
            self.xml.characters(smartText(keyValue))
            self.xml.endElement("natural")
          self.xml.endElement("object")
      else:
        def handleM2m(value):
          self.xml.addQuickElement("object", attrs={
            'pk': smartText(value._getPkVal())
          })
      for relobj in getattr(obj, field.name).iterator():
        handleM2m(relobj)

      self.xml.endElement("field")

  def _startRelationalField(self, field):
    """
    Helper to output the <field> element for relational fields
    """
    self.indent(2)
    self.xml.startElement("field", {
      "name": field.name,
      "rel": field.rel.__class__.__name__,
      "to": smartText(field.rel.to._meta),
    })


class Deserializer(base.Deserializer):
  """
  Deserialize XML.
  """

  def __init__(self, streamOrString, **options):
    super(Deserializer, self).__init__(streamOrString, **options)
    self.eventStream = pulldom.parse(self.stream, self._makeParser())
    self.db = options.pop('using', DEFAULT_DB_ALIAS)
    self.ignore = options.pop('ignorenonexistent', False)

  def _makeParser(self):
    """Create a hardened XML parser (no custom/external entities)."""
    return DefusedExpatParser()

  def __next__(self):
    for event, node in self.eventStream:
      if event == "START_ELEMENT" and node.nodeName == "object":
        self.eventStream.expandNode(node)
        return self._handleObject(node)
    raise StopIteration

  def _handleObject(self, node):
    """
    Convert an <object> node to a DeserializedObject.
    """
    # Look up the model using the model loading mechanism. If this fails,
    # bail.
    Model = self._getModelFromNode(node, "model")

    # Start building a data dictionary from the object.
    data = {}
    if node.hasAttribute('pk'):
      data[Model._meta.pk.attname] = Model._meta.pk.toPython(
        node.getAttribute('pk'))

    # Also start building a dict of m2m data (this is saved as
    # {m2mAccessorAttribute : [listOfRelatedObjects]})
    m2mData = {}

    modelFields = Model._meta.getAllFieldNames()
    # Deseralize each field.
    for fieldNode in node.getElementsByTagName("field"):
      # If the field is missing the name attribute, bail (are you
      # sensing a pattern here?)
      fieldName = fieldNode.getAttribute("name")
      if not fieldName:
        raise base.DeserializationError("<field> node is missing the 'name' attribute")

      # Get the field from the Model. This will raise a
      # FieldDoesNotExist if, well, the field doesn't exist, which will
      # be propagated correctly unless ignorenonexistent=True is used.
      if self.ignore and fieldName not in modelFields:
        continue
      field = Model._meta.getField(fieldName)

      # As is usually the case, relation fields get the special treatment.
      if field.rel and isinstance(field.rel, model.ManyToManyRel):
        m2mData[field.name] = self._handleM2mFieldNode(fieldNode, field)
      elif field.rel and isinstance(field.rel, model.ManyToOneRel):
        data[field.attname] = self._handleFkFieldNode(fieldNode, field)
      else:
        if fieldNode.getElementsByTagName('None'):
          value = None
        else:
          value = field.toPython(getInnerText(fieldNode).strip())
        data[field.name] = value

    obj = base.buildInstance(Model, data, self.db)

    # Return a DeserializedObject so that the m2m data has a place to live.
    return base.DeserializedObject(obj, m2mData)

  def _handleFkFieldNode(self, node, field):
    """
    Handle a <field> node for a ForeignKey
    """
    # Check if there is a child node named 'None', returning None if so.
    if node.getElementsByTagName('None'):
      return None
    else:
      if hasattr(field.rel.to._defaultManager, 'getByNaturalKey'):
        keys = node.getElementsByTagName('natural')
        if keys:
          # If there are 'natural' subelements, it must be a natural key
          fieldValue = [getInnerText(k).strip() for k in keys]
          obj = field.rel.to._defaultManager.dbManager(self.db).getByNaturalKey(*fieldValue)
          objPk = getattr(obj, field.rel.fieldName)
          # If this is a natural foreign key to an object that
          # has a FK/O2O as the foreign key, use the FK value
          if field.rel.to._meta.pk.rel:
            objPk = objPk.pk
        else:
          # Otherwise, treat like a normal PK
          fieldValue = getInnerText(node).strip()
          objPk = field.rel.to._meta.getField(field.rel.fieldName).toPython(fieldValue)
        return objPk
      else:
        fieldValue = getInnerText(node).strip()
        return field.rel.to._meta.getField(field.rel.fieldName).toPython(fieldValue)

  def _handleM2mFieldNode(self, node, field):
    """
    Handle a <field> node for a ManyToManyField.
    """
    if hasattr(field.rel.to._defaultManager, 'getByNaturalKey'):
      def m2mConvert(n):
        keys = n.getElementsByTagName('natural')
        if keys:
          # If there are 'natural' subelements, it must be a natural key
          fieldValue = [getInnerText(k).strip() for k in keys]
          objPk = field.rel.to._defaultManager.dbManager(self.db).getByNaturalKey(*fieldValue).pk
        else:
          # Otherwise, treat like a normal PK value.
          objPk = field.rel.to._meta.pk.toPython(n.getAttribute('pk'))
        return objPk
    else:
      m2mConvert = lambda n: field.rel.to._meta.pk.toPython(n.getAttribute('pk'))
    return [m2mConvert(c) for c in node.getElementsByTagName("object")]

  def _getModelFromNode(self, node, attr):
    """
    Helper to look up a model from a <object model=...> or a <field
    rel=... to=...> node.
    """
    modelIdentifier = node.getAttribute(attr)
    if not modelIdentifier:
      raise base.DeserializationError(
        "<%s> node is missing the required '%s' attribute"
        % (node.nodeName, attr))
    try:
      return apps.getModel(modelIdentifier)
    except (LookupError, TypeError):
      raise base.DeserializationError(
        "<%s> node has invalid model identifier: '%s'"
        % (node.nodeName, modelIdentifier))


def getInnerText(node):
  """
  Get all the inner text of a DOM node (recursively).
  """
  # inspired by http://mail.python.org/pipermail/xml-sig/2005-March/011022.html
  innerText = []
  for child in node.childNodes:
    if child.nodeType == child.TEXT_NODE or child.nodeType == child.CDATA_SECTION_NODE:
      innerText.append(child.data)
    elif child.nodeType == child.ELEMENT_NODE:
      innerText.extend(getInnerText(child))
    else:
      pass
  return "".join(innerText)


# Below code based on Christian Heimes' defusedxml


class DefusedExpatParser(_ExpatParser):
  """
  An expat parser hardened against XML bomb attacks.

  Forbids DTDs, external entity references

  """
  def __init__(self, *args, **kwargs):
    _ExpatParser.__init__(self, *args, **kwargs)
    self.setFeature(handler.featureExternalGes, False)
    self.setFeature(handler.featureExternalPes, False)

  def startDoctypeDecl(self, name, sysid, pubid, hasInternalSubset):
    raise DTDForbidden(name, sysid, pubid)

  def entityDecl(self, name, isParameterEntity, value, base,
          sysid, pubid, notationName):
    raise EntitiesForbidden(name, value, base, sysid, pubid, notationName)

  def unparsedEntityDecl(self, name, base, sysid, pubid, notationName):
    # expat 1.2
    raise EntitiesForbidden(name, None, base, sysid, pubid, notationName)

  def externalEntityRefHandler(self, context, base, sysid, pubid):
    raise ExternalReferenceForbidden(context, base, sysid, pubid)

  def reset(self):
    _ExpatParser.reset(self)
    parser = self._parser
    parser.StartDoctypeDeclHandler = self.startDoctypeDecl
    parser.EntityDeclHandler = self.entityDecl
    parser.UnparsedEntityDeclHandler = self.unparsedEntityDecl
    parser.ExternalEntityRefHandler = self.externalEntityRefHandler


class DefusedXmlException(ValueError):
  """Base exception."""
  def __repr__(self):
    return str(self)


class DTDForbidden(DefusedXmlException):
  """Document type definition is forbidden."""
  def __init__(self, name, sysid, pubid):
    super(DTDForbidden, self).__init__()
    self.name = name
    self.sysid = sysid
    self.pubid = pubid

  def __str__(self):
    tpl = "DTDForbidden(name='{}', systemId={!r}, publicId={!r})"
    return tpl.format(self.name, self.sysid, self.pubid)


class EntitiesForbidden(DefusedXmlException):
  """Entity definition is forbidden."""
  def __init__(self, name, value, base, sysid, pubid, notationName):
    super(EntitiesForbidden, self).__init__()
    self.name = name
    self.value = value
    self.base = base
    self.sysid = sysid
    self.pubid = pubid
    self.notationName = notationName

  def __str__(self):
    tpl = "EntitiesForbidden(name='{}', systemId={!r}, publicId={!r})"
    return tpl.format(self.name, self.sysid, self.pubid)


class ExternalReferenceForbidden(DefusedXmlException):
  """Resolving an external reference is forbidden."""
  def __init__(self, context, base, sysid, pubid):
    super(ExternalReferenceForbidden, self).__init__()
    self.context = context
    self.base = base
    self.sysid = sysid
    self.pubid = pubid

  def __str__(self):
    tpl = "ExternalReferenceForbidden(systemId='{}', publicId={})"
    return tpl.format(self.sysid, self.pubid)
