from theory.gui import widget

class SplitArrayWidget(widget.BaseFieldInput):

  def __init__(self, widget, size, **kwargs):
    self.widget = widget() if isinstance(widget, type) else widget
    self.size = size
    super(SplitArrayWidget, self).__init__(**kwargs)

  @property
  def isHidden(self):
    return self.widget.isHidden

  def valueFromDatadict(self, data, files, name):
    return [self.widget.valueFromDatadict(data, files, '%s_%s' % (name, index))
        for index in range(self.size)]

  def idForLabel(self, id_):
    # See the comment for RadioSelect.idForLabel()
    if id_:
      id_ += '_0'
    return id_

  def render(self, name, value, attrs=None):
    if self.isLocalized:
      self.widget.isLocalized = self.isLocalized
    value = value or []
    output = []
    finalAttrs = self.buildAttrs(attrs)
    id_ = finalAttrs.get('id', None)
    for i in range(max(len(value), self.size)):
      try:
        widgetValue = value[i]
      except IndexError:
        widgetValue = None
      if id_:
        finalAttrs = dict(finalAttrs, id='%s_%s' % (id_, i))
      output.append(self.widget.render(name + '_%s' % i, widgetValue, finalAttrs))
    return markSafe(self.formatOutput(output))

  def formatOutput(self, renderedWidgets):
    return ''.join(renderedWidgets)

  @property
  def media(self):
    return self.widget.media

  def __deepcopy__(self, memo):
    obj = super(SplitArrayWidget, self).__deepcopy__(memo)
    obj.widget = copy.deepcopy(self.widget)
    return obj

  @property
  def needsMultipartForm(self):
    return self.widget.needsMultipartForm



