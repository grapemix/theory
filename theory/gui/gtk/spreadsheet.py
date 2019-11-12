# -*- coding: utf-8 -*-
#!/usr/bin/env python
##### System wide lib #####
from collections import OrderedDict
from theory.thevent import gevent
import notify2

##### Theory lib #####
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
      spData,
      fetchMoreRowFxn,
      showStackDataFxn
      ):
    self.window = gtk.Window()
    self.title = title
    self.window.set_title(title)
    self.window.set_size_request(-1, -1)
    self.window.connect("delete-event", self.close_window)
    self.childSpreadSheetLst = []
    self.isMainWindow = True
    self.selectedIdLst = selectedIdLst
    self.idLabelIdx = idLabelIdx
    self.spData = spData
    self.fetchMoreRowFxn = fetchMoreRowFxn

    self.renderKwargsSet = renderKwargsSet
    self.showStackDataFxn = showStackDataFxn

    # model creation
    self.flagColIdx = len(listStoreDataType)
    # one col for hasBeenChanged, one col for isSelected
    listStoreDataType.append(bool)
    listStoreDataType.append(bool)

    self.model = gtk.ListStore(*listStoreDataType)
    self._appendToModel(model)

    self._switchToGeventLoop()

    self.create_interior()
    self.window.show_all()

  def _appendToModel(self, model):
    for i in model:
      # Since QuerysetField should allow None as initData which means untouched
      # data
      if self.selectedIdLst is not None \
          and i[self.idLabelIdx] in self.selectedIdLst:
        self.model.append(i + [False, True])
      else:
        self.model.append(i + [False, False])

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
    self.model = []
    for child in self.childSpreadSheetLst:
      child.model = []
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

    button = gtk.Button(stock=gtk.STOCK_GO_FORWARD)
    button.connect("clicked", self.fetchMore)
    bbox.add(button)

    button = gtk.Button(stock=gtk.STOCK_OK)
    button.connect("clicked", self.close_window)
    bbox.add(button)

    button = gtk.Button(stock=gtk.STOCK_CANCEL)
    button.connect("clicked", self.discard_change)
    bbox.add(button)

    return frame

  def fetchMore(self, *args, **kwargs):
    self.spData["pageNum"] += 1
    mdlLst = self.fetchMoreRowFxn(**self.spData)
    if len(mdlLst) == 0:
      n = notify2.Notification(
          "No more data",
          "No more data",
          "notification-message-im"   # Icon name
          )
      n.show()
    else:
      self._appendToModel(mdlLst)

  def close_window(self, *args, **kwargs):
    r = []
    for i in self.model:
      if i[-1]:
        r.append(i)
    self.model = r

    for child in self.childSpreadSheetLst:
      child.close_window()

    self.window.destroy()
    if self.isMainWindow:
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

class SpreadsheetBuilder(object):
  """This class is used to provide information in order to render the data
  field and to decide the interaction of the data field based on the
  data field type being detected. It is specific to work with spreadsheet
  class, so it should also prepare/transform data for the spreadsheet
  class."""

  def run(
      self,
      appName,
      mdlName,
      data,
      fieldNameVsProp,
      isEditable,
      selectedIdLst,
      spData,
      fetchMoreRowFxn,
      showStackFxn,
      ):
    self.idLabelIdx = None
    self.isEditable = isEditable
    self.selectedIdLst = selectedIdLst
    self.showStackFxn = showStackFxn
    self.appName = appName
    self.mdlName = mdlName

    self.childSpreadSheetBuilderLst = []

    self.fieldNameVsProp = fieldNameVsProp
    for i, fieldName in enumerate(list(self.fieldNameVsProp.keys())):
      if fieldName=="id" :
        self.idLabelIdx = i

    listStoreDataType, neglectColIdxLst = self._buildListStoreDataType(
      self.fieldNameVsProp
    )
    essentialData = []
    for row in data:
      essentialRow = []
      for i, cell in enumerate(row):
        if i not in neglectColIdxLst:
          essentialRow.append(cell)
      essentialData.append(essentialRow)
    for neglectColIdx in neglectColIdxLst:
      if neglectColIdx <= self.idLabelIdx:
        self.idLabelIdx -= 1

    self.renderKwargsSet = self._buildRenderKwargsSet(self.fieldNameVsProp)

    self.spreadsheet = Spreadsheet(
        "Listing {0}-{1}".format(appName, mdlName),
        listStoreDataType,
        essentialData,
        self.renderKwargsSet,
        self.selectedIdLst,
        self.idLabelIdx,
        spData,
        fetchMoreRowFxn,
        self.showStackData,
        )

    return self.spreadsheet

  def showWidget(self, isMainSpreadsheet):
    if isMainSpreadsheet:
      self.spreadsheet.main()
    else:
      self.spreadsheet.isMainWindow = False

  def showStackData(self, toggleWidget, rowNum, colIdx):
    rowNum = int(rowNum)
    fieldProp = self.fieldNameVsProp[self.renderKwargsSet[colIdx]["title"]]
    self.showStackFxn(
      fieldProp["foreignApp"],
      fieldProp["foreignModel"],
      self.isEditable,
      self.selectedIdLst,
      self
    )

  def getDataModel(self):
    return self.spreadsheet.getDataModel()

  def addChild(self, spreadsheetBuilder):
      self.childSpreadSheetBuilderLst.append(spreadsheetBuilder)
      self.spreadsheet.childSpreadSheetLst.append(
        spreadsheetBuilder.spreadsheet
      )

  def getSelectedIdLst(self):
    dataRow = self.getDataModel()
    r = []
    for row in dataRow:
        if row[-1]:
          r.append(row[self.idLabelIdx])
    return r

  def getJsonDataLst(self, handlerFxn, r):
    for childSpreadSheetBuilder in self.childSpreadSheetBuilderLst:
      r = childSpreadSheetBuilder.getJsonDataLst(handlerFxn, r)
    dataRow = self.getDataModel()
    if len(dataRow) != 0:
      columnHandlerLabel = self.getColumnHandlerLabel()
      jsonDataLst = handlerFxn.run(
          dataRow,
          columnHandlerLabel,
          self.fieldNameVsProp,
          )
      r.append((self.appName, self.mdlName, jsonDataLst))
    return r

  def getColumnHandlerLabel(self):
    """This fxn does not required to build a spreadsheet. Instead, this fxn
    will be called to convert modified data from dataModel to other format
    (e.g. back to db instance). The value should have 2 cases: 1) in the
    dataModel and editable 2) in the dataModel and non-editable"""
    columnHandlerLst = []
    for field in self.renderKwargsSet:
      try:
        if(field["editable"]):
          columnHandlerLst.append((
            field["title"],
            self.fieldNameVsProp[field["title"]]["klassLabel"]
          ))
        else:
          columnHandlerLst.append((field["title"], None))
      except KeyError:
        columnHandlerLst.append((field["title"], None))
    return OrderedDict(columnHandlerLst)


  def _getFieldNameVsHandlerDict(self, klassLabel, prefix=""):
    return {
        "dataHandler": getattr(self, "_%s%sDataHandler" % (prefix, klassLabel)),
        "renderHandler": getattr(
          self,
          "_%s%sRenderHandler" % (prefix, klassLabel)
        ),
    }

  def _buildRenderKwargsSet(self, fieldNameVsProp):
    kwargsSet = []
    for fieldName, fieldProp in fieldNameVsProp.items():
      kwargs = getattr(
        self,
        "_{0}FieldRenderHandler".format(fieldProp["type"])
      )(fieldName)
      if(kwargs is not None):
        kwargs.update({"title": fieldName})
        kwargsSet.append(kwargs)
    return kwargsSet

  def _queryRowToGtkDataModel(self, queryrow):
    row = []

    for fieldName, handlerDict in self.fieldNameVsHandlerDict.items():
      result = handlerDict["dataHandler"](
          id,
          fieldName,
          getattr(queryrow, fieldName)
          )
      if result is not None:
        row.append(result)
    return row

  def _buildListStoreDataType(self, fieldNameVsProp):
    args = []
    self.modelFieldnameMap = {}
    idx = -1
    neglectColIdxLst = []
    for fieldName, fieldProp in fieldNameVsProp.items():
      idx += 1
      if(fieldProp["type"]=="neglect"):
        neglectColIdxLst.append(idx)
        continue
      elif(fieldProp["type"]=="nonEditableForceStr"
          or fieldProp["type"]=="editableForceStr"
          or fieldProp["type"]=="str"
      ):
        args.append(str)
      elif(fieldProp["type"].startswith("list")
          # TODO: remove me
          or fieldProp["type"]=="model"
      ):
        self.modelFieldnameMap[idx] = fieldName
        args.append(str)
      elif fieldProp["type"] in ["float", "enum", "int"]:
        args.append(str)
      elif(fieldProp["type"]=="bool"):
        args.append(bool)
    return (args, neglectColIdxLst)

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
    choices = self.fieldNameVsProp[field]["choices"].values()
    return {
        "editable": self.isEditable and True,
        "fxnName": "renderComboBoxCol",
        "choices": choices
        }
