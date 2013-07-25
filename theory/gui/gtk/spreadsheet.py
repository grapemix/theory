# -*- coding: utf-8 -*-
#!/usr/bin/env python
##### System wide lib #####
from collections import OrderedDict
from bson.json_util import loads as jsonLoads
##### Theory lib #####
from theory.gui import field
from theory.gui.transformer import (
    MongoModelDataHandler,
    MongoModelBSONDataHandler
    )
from theory.model import AppModel

##### Theory third-party lib #####

##### Local app #####

##### Theory app #####

##### Misc #####
# ensure that PyGTK 2.0 is loaded - not an older version
import pygtk
pygtk.require('2.0')
# import the GTK module
import gtk
import gobject

__all__ = ("SpreadsheetBuilder",)

class Spreadsheet(object):
  def __init__(self, title, listStoreDataType, model,
      renderKwargsSet, showStackDataFxn):
    self.window = gtk.Window()
    self.title = title
    self.window.set_title(title)
    self.window.set_size_request(-1, -1)
    self.window.connect("delete-event", self.close_window)
    self.childSpreadSheetLst = []
    self.isMainWindow = True

    self.renderKwargsSet = renderKwargsSet
    self.showStackDataFxn = showStackDataFxn

    # model creation
    self.flagColIdx = len(listStoreDataType)
    # one col for hasBeenChanged, one col for isSelected
    listStoreDataType.append(bool)
    listStoreDataType.append(bool)

    self.model = gtk.ListStore(*listStoreDataType)

    for i in model:
      self.model.append(i + [False, False])

    self.create_interior()
    self.window.show_all()

  def getSelectedRow(self):
    return [i for i, v in enumerate(self.model) if(v[-1])]

  def getDataModel(self):
    return self.model

  def discard_change(self, button):
    for i in self.model:
      i[-1] = False
    self.close_window()

  # Create a Button Box with the specified parameters
  def create_bbox(self, horizontal, title, spacing, layout):
    frame = gtk.Frame(title)

    if horizontal:
      bbox = gtk.HButtonBox()
    else:
      bbox = gtk.VButtonBox()

    bbox.set_border_width(5)
    frame.add(bbox)

    # Set the appearance of the Button Box
    bbox.set_layout(layout)
    bbox.set_spacing(spacing)

    button = gtk.Button(stock=gtk.STOCK_OK)
    button.connect("clicked", self.close_window)
    bbox.add(button)

    button = gtk.Button(stock=gtk.STOCK_CANCEL)
    button.connect("clicked", self.discard_change)
    bbox.add(button)

    return frame

  def close_window(self, *args, **kwargs):
    for child in self.childSpreadSheetLst:
      child.close_window()

    self.window.destroy()
    if(self.isMainWindow):
      gtk.main_quit()

  def create_interior(self):
    main_vbox = gtk.VBox(False, 0)
    self.window.add(main_vbox)

    treeviewBox = gtk.ScrolledWindow()
    main_vbox.pack_start(treeviewBox, True, True, 0)
    treeviewBox.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)

    # the treeview
    self.treeview = gtk.TreeView(self.model)

    self.renderStatusCol(0)

    for i, kwargs in enumerate(self.renderKwargsSet):
      fxnName = kwargs["fxnName"]
      del kwargs["fxnName"]
      kwargs["colIdx"] = i
      getattr(self, fxnName)(**kwargs)

    # pack the treeview
    treeviewBox.add(self.treeview)
    # show the box
    treeviewBox.set_size_request(500, 260)

    main_vbox.pack_start(
        self.create_bbox(
          True,
          "Action",
          40,
          gtk.BUTTONBOX_SPREAD
        ),
        False,
        True,
        0
    )

    treeviewBox.show()

  def renderTextCol(self, title, colIdx, editable):
    col = gtk.TreeViewColumn(title)
    self.treeview.append_column(col)
    cell = gtk.CellRendererText()
    col.pack_start(cell, expand=False)
    cell.set_property("editable", editable)
    col.set_attributes(cell, text=colIdx)
    col.set_sort_column_id(colIdx)
    cell.connect('edited', self._text_changed, colIdx)

  def renderFloatCol(self, title, colIdx, editable, min=0, max=10, step=0.1):
    col = gtk.TreeViewColumn(title)
    self.treeview.append_column(col)
    cell = gtk.CellRendererSpin()
    cell.set_property(
        "adjustment",
        gtk.Adjustment(lower=min, upper=max, step_incr=step)
        )
    cell.set_property("editable", editable)
    col.pack_start(cell, expand=False)
    col.set_attributes(cell, text=colIdx)
    cell.connect('edited', self._float_changed, colIdx)

  def renderIconCol(self, colIdx):
    col = gtk.TreeViewColumn("State")
    self.treeview.insert_column(col, 0)
    cell = gtk.CellRendererPixbuf()
    col.pack_start(cell, expand=False)
    cell.set_property('cell-background', 'greenyellow')
    col.set_cell_data_func(cell, self._render_icon)

  def renderStatusCol(self, colIdx):
    col = gtk.TreeViewColumn("State")
    self.treeview.insert_column(col, 0)
    cell = gtk.CellRendererToggle()
    cell.set_property("activatable", True)
    col.pack_start(cell, expand=False)
    cell.set_property('cell-background', 'greenyellow')
    col.set_attributes(cell, active=self.flagColIdx + 1)
    col.set_cell_data_func(cell, self._render_status)
    cell.connect('toggled', self._statusbox_toggled)

  def renderBtnCol(self, title, colIdx, **kwargs):
    kwargs["colIdx"] = colIdx
    cell = CellRendererButton(callable=self.showStackDataFxn, kwargs=kwargs)
    col = gtk.TreeViewColumn(title, cell, text=colIdx)
    self.treeview.append_column(col)
    col.pack_start(cell, expand=False)

  def renderCheckBoxCol(self, title, colIdx, editable):
    col = gtk.TreeViewColumn(title)
    self.treeview.append_column(col)
    cell = gtk.CellRendererToggle()
    cell.set_property("activatable", editable)
    col.pack_start(cell, expand=False)
    col.set_attributes(cell, active=colIdx)
    col.set_sort_column_id(colIdx)
    cell.connect('toggled', self._checkbox_toggled, colIdx)

  def renderComboBoxCol(self, title, colIdx, editable, choices):
    col = gtk.TreeViewColumn(title)
    self.treeview.append_column(col)
    cell = gtk.CellRendererCombo()
    cell.set_property("editable", editable)
    # we need a separate model for the combo
    model = gtk.ListStore(str)
    for value in choices:
      model.append([value])
    cell.set_property("model", model)
    cell.set_property("text-column", 0)
    col.pack_start(cell, expand=False)
    col.set_attributes(cell, text=colIdx)
    col.set_sort_column_id(colIdx)
    cell.connect('edited', self._combobox_changed, colIdx)

  def renderProgressCol(self, title, colIdx):
    # Progress column
    col = gtk.TreeViewColumn(title)
    self.treeview.append_column(col)
    cell = gtk.CellRendererProgress()
    col.pack_start(cell, expand=True)
    col.set_attributes(cell, value=colIdx)
    col.set_sort_column_id(colIdx)

  def _render_status(self, column, cell, model, iter):
    data = self.model.get_value(iter, self.flagColIdx)
    cell.set_property('cell-background-set', data)

  def _render_icon(self, column, cell, model, iter):
    data = self.model.get_value(iter, self.flagColIdx)
    if data == True:
      stock = gtk.STOCK_YES
    else:
      stock = gtk.STOCK_NO
    pixbuf = self.window.render_icon(stock_id=stock, size=gtk.ICON_SIZE_MENU)
    cell.set_property('pixbuf', pixbuf)

  def _checkbox_toggled(self, w, row, column):
    self.model[row][column] = not self.model[row][column]
    self.model[row][self.flagColIdx] = True

  def _statusbox_toggled(self, w, row):
    self.model[row][self.flagColIdx + 1] = \
        not self.model[row][self.flagColIdx + 1]

  def _text_changed(self, w, row, new_value, column):
    if(self.model[row][self.flagColIdx] == False
        and self.model[row][column] != new_value):
      self.model[row][self.flagColIdx] = True
    self.model[row][column] = new_value

  def _float_changed(self, w, row, new_value, column):
    if(self.model[row][self.flagColIdx] == False
        and self.model[row][column] != int(new_value)):
      self.model[row][self.flagColIdx] = True
    self.model[row][column] = int(new_value)

  def _combobox_changed(self, w, row, new_value, column):
    if(self.model[row][self.flagColIdx] == False
        and self.model[row][column] != new_value):
      self.model[row][self.flagColIdx] = True
    self.model[row][column] = new_value

  def main(self):
    gtk.main()

class CellRendererButton(gtk.CellRendererText):
  __gproperties__ = { "callable": (gobject.TYPE_PYOBJECT,
          "callable property",
          "callable property",
          gobject.PARAM_READWRITE) }
  _button_width = 40
  _button_height = 30

  def __init__(self, callable=None, kwargs={}):
    self.__gobject_init__()
    gtk.CellRendererText.__init__(self)
    self.set_property("xalign", 0.5)
    self.set_property("mode", gtk.CELL_RENDERER_MODE_ACTIVATABLE)
    self.callable = callable
    self.callableKwargs = kwargs
    self.table = None


  def do_set_property(self, pspec, value):
    if pspec.name == "callable":
      if callable(value):
        self.callable = value
      else:
        raise TypeError("callable property must be callable!")
    else:
      raise AttributeError("Unknown property %s" % pspec.name)


  def do_get_property(self, pspec):
    if pspec.name == "callable":
      return self.callable
    else:
      raise AttributeError("Unknown property %s" % pspec.name)


  def do_get_size(self, wid, cell_area):
    xpad = self.get_property("xpad")
    ypad = self.get_property("ypad")

    if not cell_area:
      x, y = 0, 0
      w = 2 * xpad + self._button_width
      h = 2 * ypad + self._button_height
    else:
      w = 2 * xpad + cell_area.width
      h = 2 * ypad + cell_area.height

      xalign = self.get_property("xalign")
      yalign = self.get_property("yalign")

      x = max(0, xalign * (cell_area.width - w))
      y = max(0, yalign * (cell_area.height - h))

    return (x, y, w, h)


  def do_render(self, window, wid, bg_area, cell_area, expose_area, flags):
    if not window:
      return

    xpad = self.get_property("xpad")
    ypad = self.get_property("ypad")

    x, y, w, h = self.get_size(wid, cell_area)

    if flags & gtk.CELL_RENDERER_PRELIT :
      state = gtk.STATE_PRELIGHT
      shadow = gtk.SHADOW_ETCHED_OUT
    else :
      state = gtk.STATE_NORMAL
      shadow = gtk.SHADOW_OUT
    wid.get_style().paint_box(
        window,
        state,
        shadow,
        cell_area,
        wid,
        "button",
        cell_area.x + x + xpad,
        cell_area.y + y + ypad,
        w - 6,
        h - 6
        )
    flags = flags & ~gtk.STATE_SELECTED
    cell = gtk.CellRendererText.do_render(
        self,
        window,
        wid,
        bg_area,
        (cell_area[0], cell_area[1] + ypad, cell_area[2],cell_area[3]),
        expose_area,
        flags
        )

  def do_activate(self, event, wid, path, bg_area, cell_area, flags):
    cb = self.get_property("callable")
    if cb != None :
      cb (path, **self.callableKwargs)
    return True


gobject.type_register(CellRendererButton)


class SpreadsheetBuilder(MongoModelBSONDataHandler):
#class SpreadsheetBuilder(MongoModelDataHandler):
  """This class is used to provide information in order to render the data
  field and to decide the interaction of the data field based on the
  data field type being detected. It is specific to work with spreadsheet
  class, so it should also prepare/transform data for the spreadsheet
  class."""

  def run(self, queryset, isEditable=False, isMainSpreadsheet=True):
    self.modelKlass = queryset[0].__class__

    if(self.modelKlass._is_document):
      nameToken = self.modelKlass._get_collection_name().split("_")
      appName = nameToken[0]
      modelName = ""
      for i in nameToken[1:]:
        modelName += i.title()
      appModelmodel = AppModel.objects.get(name=modelName, app=appName)
    else:
      # embedded document. There has not enough info to get app name.
      # In this way, it will cause a bug if there exists two models with the
      # same name in different apps.
      appModelmodel = AppModel.objects.get(name=self.modelKlass._class_name)

    self.isEditable = isEditable
    super(SpreadsheetBuilder, self).run(queryset, appModelmodel.fieldNameTypeMap)

    listStoreDataType = self._buildListStoreDataType()
    gtkDataModel = self._buildGtkDataModel()
    self.renderKwargsSet = self._buildRenderKwargsSet()

    self._showWidget(listStoreDataType, gtkDataModel, self.renderKwargsSet, isMainSpreadsheet)

  def _showWidget(self, listStoreDataType, gtkDataModel, renderKwargsSet, isMainSpreadsheet):
    self.spreadsheet = Spreadsheet(
        "Listing %s" % (self.modelKlass._class_name),
        listStoreDataType,
        gtkDataModel,
        renderKwargsSet,
        self.showStackData,
        )
    if(isMainSpreadsheet):
      self.spreadsheet.main()
    else:
      self.spreadsheet.isMainWindow = False

  def showStackData(self, rowNum, **kwargs) :
    if(self.fieldType[
        self.modelFieldnameMap[kwargs["colIdx"]]
      ]["klassLabel"].startswith("listField")):
      # This is for listfield linked with reference/embedded field
      queryset = getattr(
          self.queryset[int(rowNum)],
          self.modelFieldnameMap[kwargs["colIdx"]]
          )
    else:
      # This is for reference/embedded field
      id = getattr(
          self.queryset[int(rowNum)],
          self.modelFieldnameMap[kwargs["colIdx"]]
          )
      queryset = [id] if(id is not None) else []

    clone = SpreadsheetBuilder()
    clone.run(queryset, self.isEditable, False)
    self.spreadsheet.childSpreadSheetLst.append(clone.spreadsheet)

  def getSelectedRow(self):
    return self.spreadsheet.getSelectedRow()

  def getDataModel(self):
    return self.spreadsheet.getDataModel()

  def getColumnHandlerLabel(self):
    """This fxn does not required to build a spreadsheet. Instead, this fxn
    will be called to convert modified data from dataModel to other format
    (e.g. back to db instance). The value should have 2 cases: 1) in the
    dataModel and editable 2) in the dataModel and non-editable"""
    columnHandlerLabel = OrderedDict()
    for field in self.renderKwargsSet:
      try:
        if(field["editable"]):
          columnHandlerLabel[field["title"]] = \
              self.fieldType[field["title"]]["klassLabel"]
        else:
          columnHandlerLabel[field["title"]] = None
      except KeyError:
        columnHandlerLabel[field["title"]] = None
    return columnHandlerLabel

  def _fillUpTypeHandler(self, klassLabel, prefix=""):
    return {
        "klassLabel": prefix + klassLabel,
        "dataHandler": getattr(self, "_%s%sDataHandler" % (prefix, klassLabel)),
        "renderHandler": getattr(
          self,
          "_%s%sRenderHandler" % (prefix, klassLabel)
        ),
    }

  def _buildRenderKwargsSet(self):
    kwargsSet = []
    for fieldName, fieldHandlerFxn in self.fieldType.iteritems():
      kwargs = fieldHandlerFxn["renderHandler"](self.fieldsDict[fieldName])
      if(kwargs is not None):
        kwargs.update({"title": fieldName})
        kwargsSet.append(kwargs)
    return kwargsSet

  def _buildGtkDataModel(self):
    gtkDataModel = []
    for queryrow in self.queryset:
      queryrowInJson = jsonLoads(queryrow.to_json())
      row = []

      try:
        id = str(queryrow.id)
      except AttributeError:
        # For example, EmbeddedModel does not have an id
        id = ""

      for fieldName, fieldHandlerFxnLst in self.fieldType.iteritems():
        try:
          result = fieldHandlerFxnLst["dataHandler"](id, queryrowInJson[fieldName])
        except KeyError:
          result = fieldHandlerFxnLst["dataHandler"](id, None)
        if(result is not None):
          row.append(result)
      gtkDataModel.append(row)
    return gtkDataModel

  def _buildListStoreDataType(self):
    args = []
    self.modelFieldnameMap = {}
    idx = 0
    for fieldName, fieldHandlerFxnLst in self.fieldType.iteritems():
      fieldHandlerFxn = fieldHandlerFxnLst["klassLabel"]
      if(fieldHandlerFxn=="neglectField"):
        continue
      elif(fieldHandlerFxn=="nonEditableForceStrField"
          or fieldHandlerFxn=="editableForceStrField"
          or fieldHandlerFxn=="strField"
      ):
        args.append(str)
      elif(fieldHandlerFxn=="embeddedField"
          or fieldHandlerFxn.startswith("listField")
          or fieldHandlerFxn.startswith("mapField")
          or fieldHandlerFxn.startswith("dictField")
          # TODO: remove me
          or fieldHandlerFxn=="modelField"
      ):
        self.modelFieldnameMap[idx] = fieldName
        args.append(str)
      elif(fieldHandlerFxn=="floatField"):
        args.append(float)
      elif(fieldHandlerFxn=="intField"):
        args.append(int)
      elif(fieldHandlerFxn=="boolField"):
        args.append(bool)
      idx += 1
    return args

  def _neglectFieldRenderHandler(self, field):
    pass

  def _nonEditableForceStrFieldRenderHandler(self, field):
    return {"editable": False, "fxnName": "renderTextCol"}

  def _editableForceStrFieldRenderHandler(self, field):
    return {"editable": self.isEditable and True, "fxnName": "renderTextCol"}

  def _dictFieldRenderHandler(self, field):
    return {"editable": False, "fxnName": "renderTextCol"}

  def _modelFieldRenderHandler(self, field):
    return {"fxnName": "renderBtnCol"}

  def _listFieldneglectFieldRenderHandler(self, field):
    pass

  def _listFieldnonEditableForceStrFieldRenderHandler(self, field):
    return {"editable": self.isEditable and False, "fxnName": "renderTextCol"}

  def _listFieldeditableForceStrFieldRenderHandler(self, field):
    return {"editable": self.isEditable and True, "fxnName": "renderTextCol"}

  def _listFieldembeddedFieldRenderHandler(self, field):
    return {"fxnName": "renderBtnCol"}

  def _listFieldmodelFieldRenderHandler(self, field):
    return {"fxnName": "renderBtnCol"}

  def _embeddedFieldRenderHandler(self, field):
    return {"fxnName": "renderBtnCol"}

  def _boolFieldRenderHandler(self, field):
    return {"editable": self.isEditable and True, "fxnName": "renderCheckBoxCol"}

  def _strFieldRenderHandler(self, field):
    return {"editable": self.isEditable and True, "fxnName": "renderTextCol"}

  def _floatFieldRenderHandler(self, field):
    return {
        "editable": self.isEditable and True,
        "step": 0.1,
        "fxnName": "renderFloatCol"
        }

  def _intFieldRenderHandler(self, field):
    try:
      choices = [i[1] for i in getattr(field, "choices")]
      return {
          "editable": self.isEditable and True,
          "fxnName": "renderComboBoxCol",
          "choices": choices
          }
    except (TypeError, AttributeError):
      return {
          "editable": self.isEditable and True,
          "step": 1,
          "fxnName": "renderFloatCol"
          }
