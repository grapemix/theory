# -*- coding: utf-8 -*-
#!/usr/bin/env python
##### System wide lib #####
from collections import OrderedDict
import gevent

##### Theory lib #####
from theory.apps.model import AppModel
from theory.gui.transformer import TheoryModelBSONTblDataHandler

##### Theory third-party lib #####

##### Local app #####

##### Theory app #####

##### Misc #####
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk as gtk
from gi.repository import GObject as gobject

__all__ = ("SpreadsheetBuilder",)

class Spreadsheet(object):
  def __init__(
      self,
      title,
      listStoreDataType,
      model,
      renderKwargsSet,
      selectedIdLst,
      idLabelIdx,
      showStackDataFxn
      ):
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
      if i[idLabelIdx] in selectedIdLst:
        self.model.append(i + [False, True])
      else:
        self.model.append(i + [False, False])

    self._switchToGeventLoop()

    self.create_interior()
    self.window.show_all()

  def _switchToGeventLoop(self):
    gevent.sleep(0)
    gobject.timeout_add(
        3,
        self._switchToGeventLoop,
        priority=gobject.PRIORITY_HIGH
    )

  def getSelectedRow(self):
    return [i for i, v in enumerate(self.model) if(v[-1])]

  def getDataModel(self):
    return self.model

  def discard_change(self, button):
    for i in self.model:
      i[-1] = False
    self.close_window()

  # Create a Button Box with the specified parameters
  def create_bbox(self, horizontal, spacing):
    frame = gtk.Frame()

    if horizontal:
      bbox = gtk.HButtonBox()
    else:
      bbox = gtk.VButtonBox()

    bbox.set_border_width(5)
    frame.add(bbox)

    # Set the appearance of the Button Box
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
    treeviewBox.set_policy(gtk.PolicyType.AUTOMATIC, gtk.PolicyType.AUTOMATIC)

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
          40,
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
    col.add_attribute(cell, "text", colIdx)
    col.set_sort_column_id(colIdx)
    cell.connect('edited', self._text_changed, colIdx)

  def renderFloatCol(self, title, colIdx, editable, min=0, max=10, step=0.1):
    col = gtk.TreeViewColumn(title)
    self.treeview.append_column(col)
    cell = gtk.CellRendererSpin()
    cell.set_property(
        "adjustment",
        gtk.Adjustment(lower=min, upper=max, step_increment=step)
        )
    cell.set_property("editable", editable)
    col.pack_start(cell, expand=False)
    col.add_attribute(cell, "text", colIdx)
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
    col.add_attribute(cell, "active", self.flagColIdx + 1)
    col.set_cell_data_func(cell, self._render_status)
    cell.connect('toggled', self._statusbox_toggled)

  def renderBtnCol(self, title, colIdx, **kwargs):
    kwargs["colIdx"] = colIdx
    cell = gtk.CellRendererText()
    cell.set_property("editable", False)
    col = gtk.TreeViewColumn(title, cell, text=colIdx)
    self.treeview.append_column(col)
    col.pack_start(cell, expand=False)
    cell = gtk.CellRendererToggle()
    cell.connect("toggled", self.showStackDataFxn, colIdx)
    col.pack_start(cell, expand=False)

  def renderCheckBoxCol(self, title, colIdx, editable):
    col = gtk.TreeViewColumn(title)
    self.treeview.append_column(col)
    cell = gtk.CellRendererToggle()
    cell.set_property("activatable", editable)
    col.pack_start(cell, expand=False)
    col.add_attribute(cell, "active", colIdx)
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
    col.add_attribute(cell, "text", colIdx)
    col.set_sort_column_id(colIdx)
    cell.connect('edited', self._combobox_changed, colIdx)

  def renderProgressCol(self, title, colIdx):
    # Progress column
    col = gtk.TreeViewColumn(title)
    self.treeview.append_column(col)
    cell = gtk.CellRendererProgress()
    col.pack_start(cell, expand=True)
    col.add_attribute(cell, "value", colIdx)
    col.set_sort_column_id(colIdx)

  def _render_status(self, column, cell, model, iter, dummy):
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

class SpreadsheetBuilder(TheoryModelBSONTblDataHandler):
#class SpreadsheetBuilder(MongoModelTblDataHandler):
  """This class is used to provide information in order to render the data
  field and to decide the interaction of the data field based on the
  data field type being detected. It is specific to work with spreadsheet
  class, so it should also prepare/transform data for the spreadsheet
  class."""

  def run(
      self,
      queryset,
      appConfigModel,
      isEditable=False,
      selectedIdLst=[],
      isMainSpreadsheet=True
      ):
    self.idLabelIdx = None
    self.selectedIdLst = selectedIdLst
    if(len(queryset)>0):
      self.modelKlass = queryset[0].__class__
      self.modelKlassName = self.modelKlass.__class__.__name__

      # We need this to find rowData in queryset

      self.isEditable = isEditable
      self.appConfigModel = appConfigModel
      super(SpreadsheetBuilder, self).run(
          appConfigModel.fieldParamMap.filter(parent__isnull=True)
          )
    else:
      self.modelKlassName = "Unknown model"
      super(SpreadsheetBuilder, self).run(
          {}
          )
    self.queryset = queryset

    listStoreDataType = self._buildListStoreDataType()
    gtkDataModel = self._buildGtkDataModel()
    self.renderKwargsSet = self._buildRenderKwargsSet()

    self._showWidget(
        listStoreDataType,
        gtkDataModel,
        self.renderKwargsSet,
        isMainSpreadsheet
        )

  def _showWidget(
      self,
      listStoreDataType,
      gtkDataModel,
      renderKwargsSet,
      isMainSpreadsheet
      ):
    self.spreadsheet = Spreadsheet(
        "Listing %s" % (self.modelKlassName),
        listStoreDataType,
        gtkDataModel,
        renderKwargsSet,
        self.selectedIdLst,
        self.idLabelIdx,
        self.showStackData,
        )
    if(isMainSpreadsheet):
      self.spreadsheet.main()
    else:
      self.spreadsheet.isMainWindow = False

  def showStackData(self, toggleWidget, rowNum, colIdx):
    rowNum = int(rowNum)
    queryset = getattr(
        self.queryset[rowNum],
        self.modelFieldnameMap[colIdx]
        )
    if hasattr(queryset, "all"):
      # That is for many to many field
      queryset = queryset.all()
    else:
      # This is for ForeignKey
      # or may be for one to one?
      queryset = [queryset] if(queryset is not None) else []

    buf = self.appConfigModel.fieldParamMap.filter(
        parent__name=self.modelFieldnameMap[colIdx]
        )
    for i in buf:
      if i.name == "foreignApp":
        appName = buf[0].data
      elif i.name == "foreignModel":
        modelName = buf[1].data

    print appName, modelName
    appConfigModel = AppModel.objects.get(app=appName, name=modelName)
    clone = SpreadsheetBuilder()
    # We don't assume modifying the stack data is possible, so we can
    # treat the pre-selected item list as empty
    clone.run(queryset, appConfigModel, self.isEditable, [], False)
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
              self.fieldPropDict[field["title"]]["klassLabel"]
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
    for fieldName, fieldHandlerFxn in self.fieldPropDict.iteritems():
      kwargs = fieldHandlerFxn["renderHandler"](fieldName)
      if(kwargs is not None):
        kwargs.update({"title": fieldName})
        kwargsSet.append(kwargs)
    return kwargsSet

  def _queryRowToGtkDataModel(self, queryrow):
    row = []

    for fieldName, fieldHandlerFxnLst in self.fieldPropDict.iteritems():
      result = fieldHandlerFxnLst["dataHandler"](
          id,
          fieldName,
          getattr(queryrow, fieldName)
          )
      if result is not None:
        row.append(result)
    return row

  def _buildGtkDataModel(self):
    gtkDataModel = []

    for i, fieldName in enumerate(self.fieldPropDict.keys()):
      if(fieldName=="id"):
        self.idLabelIdx = i
        break

    for queryrow in self.queryset:
      gtkDataModel.append(self._queryRowToGtkDataModel(queryrow))
    return gtkDataModel

  def _buildListStoreDataType(self):
    args = []
    self.modelFieldnameMap = {}
    idx = 0
    for fieldName, fieldHandlerFxnLst in self.fieldPropDict.iteritems():
      fieldHandlerFxn = fieldHandlerFxnLst["klassLabel"]
      if(fieldHandlerFxn=="neglectField"):
        continue
      elif(fieldHandlerFxn=="nonEditableForceStrField"
          or fieldHandlerFxn=="editableForceStrField"
          or fieldHandlerFxn=="strField"
      ):
        args.append(str)
      elif(fieldHandlerFxn.startswith("listField")
          # TODO: remove me
          or fieldHandlerFxn=="modelField"
      ):
        self.modelFieldnameMap[idx] = fieldName
        args.append(str)
      elif(fieldHandlerFxn=="floatField"):
        args.append(float)
      elif(fieldHandlerFxn=="enumField"):
        args.append(str)
      elif(fieldHandlerFxn=="intField"):
        args.append(str)
      elif(fieldHandlerFxn=="boolField"):
        args.append(bool)
      idx += 1
    return args

  def _intFieldDataHandler(self, rowId, fieldName, fieldVal):
    if(fieldVal is None):
      return str(0)
    return str(fieldVal)

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
    return {
        "editable": self.isEditable and False,
        "fxnName": "renderTextCol"
        }

  def _listFieldeditableForceStrFieldRenderHandler(self, field):
    return {
        "editable": self.isEditable and True,
        "fxnName": "renderTextCol"
        }

  def _listFieldembeddedFieldRenderHandler(self, field):
    return {"fxnName": "renderBtnCol"}

  def _listFieldmodelFieldRenderHandler(self, field):
    return {"fxnName": "renderBtnCol"}

  def _embeddedFieldRenderHandler(self, field):
    return {"fxnName": "renderBtnCol"}

  def _boolFieldRenderHandler(self, field):
    return {
        "editable": self.isEditable and True,
        "fxnName": "renderCheckBoxCol"
        }

  def _strFieldRenderHandler(self, field):
    return {"editable": self.isEditable and True, "fxnName": "renderTextCol"}

  def _floatFieldRenderHandler(self, field):
    return {
        "editable": self.isEditable and True,
        "step": 0.1,
        "fxnName": "renderFloatCol"
        }

  def _intFieldRenderHandler(self, field):
    return {
        "editable": self.isEditable and True,
        "fxnName": "renderTextCol"
        }

  def _enumFieldRenderHandler(self, field):
    choices = self.fieldPropDict[field]["choices"].values()
    return {
        "editable": self.isEditable and True,
        "fxnName": "renderComboBoxCol",
        "choices": choices
        }
