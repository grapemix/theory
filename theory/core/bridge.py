# -*- coding: utf-8 -*-
#!/usr/bin/env python
##### System wide lib #####
import json

##### Theory lib #####
from theory.apps.adapter import BaseUIAdapter
from theory.core.exceptions import CommandSyntaxError
from theory.apps.model import Adapter, AdapterBuffer, Command
from theory.utils.importlib import importClass

##### Theory third-party lib #####

##### Local app #####

##### Theory app #####

##### Misc #####

class Bridge(object):
  """This class is the first draft for bridge and should only consider the one
  to one relationship. In the second version, we should assume the choice of
  adapter between n-1 and n-2, should not be affected by the choice of adapter
  between n and n-1, in other words, the choice of adapter should be
  independent in each round.
  """

  def _objAssign(self, o, k, v):
    setattr(o, k, v)
    return o

  def _dictAssign(self, o, k, v):
    o[k] = v
    return o

  def _formAssign(self, o, k, v):
    o.fields[k].finalData = v
    return o

  def _getCmdForAssignment(self, cmdModel):
    cmdKlass = importClass(cmdModel.classImportPath)
    cmd = cmdKlass()

    if(cmdModel.runMode==cmdModel.RUN_MODE_ASYNC):
      assignFxn = self._dictAssign
      storage = {}
    else:
      assignFxn = self._objAssign
      storage = cmd

    return (cmd, assignFxn, storage)

  def _propertiesAssign(self, adapter, assignFxn, storage, propertyLst):
    for property in propertyLst:
      try:
        v = getattr(adapter, property)
        storage = assignFxn(storage, property, v)
      except AttributeError:
        try:
          v = getattr(adapter, "_" + property)
          storage = assignFxn(storage, property, v)
        except AttributeError:
          pass
    return storage

  def getCmdComplex(self, cmdModel, args, kwargs):
    cmdKlass = importClass(cmdModel.classImportPath)
    cmd = cmdKlass()
    cmdParamForm = importClass(cmdModel.classImportPath).ParamForm
    cmd.paramForm = cmdParamForm()
    cmd.paramForm.fillFinalFields(cmdModel, args, kwargs)
    cmd.paramForm.isValid()
    return cmd

  # TODO: should be replaced later on. At least inheritance case should be
  # considered
  def _naivieAdapterMatching(self, adapterNameLst1, adapterNameLst2):
    for i in adapterNameLst1:
      if(i in adapterNameLst2):
        return i
    return None

  def _serializeAdapterPropertySelection(self, adapterModel, adapter, tailModel):
    """ This fxn will treat adapter's choice as highest priority. """
    propertyLst = self._naivieAdapterPropertySelection(adapterModel, tailModel)
    if(hasattr(adapter, "serializableProperty")):
      return adapter.serializableProperty(propertyLst)
    return propertyLst

  def _naivieAdapterPropertySelection(self, adapterModel, tailModel):
    propertyLst = []
    cmdParam = [i.name for i in tailModel.cmdFieldSet.all()]
    for i in adapterModel.propertyLst:
      if(i in cmdParam):
        propertyLst.append(i)
    return propertyLst

  def bridge(self, headInst, tailModel):
    (tailInst, assignFxn, storage) = self._getCmdForAssignment(tailModel)
    commonAdapterName = self._probeAdapter(headInst, tailInst)

    (adapterModel, adapter) = self.adaptFromCmd(commonAdapterName, headInst)

    propertyLst = self._naivieAdapterPropertySelection(adapterModel, tailModel)
    adapter.run()

    return (tailInst, self._propertiesAssign(adapter, \
        self._dictAssign, \
        {}, \
        propertyLst))

  def bridgeToSelf(self, headInst):
    cmd = headInst.__class__()
    commonAdapterName = headInst._gongs[0]

    (adapterModel, adapter) = self.adaptFromCmd(commonAdapterName, headInst)
    adapter.run()
    if(hasattr(adapter, "render")):
      adapter.render(None, None)

    for field in headInst.paramForm.fields.values():
      field.widget = field.widget.__class__

    return (
        headInst,
        self._propertiesAssign(
          adapter,
          self._formAssign,
          headInst.paramForm,
          headInst.paramForm.fields.keys()
          )
        )

  def bridgeToDb(self, headInst, tailModel):
    (tailInst, assignFxn, storage) = self._getCmdForAssignment(tailModel)

    commonAdapterName = self._probeAdapter(headInst, tailInst)

    (adapterModel, adapter) = self.adaptFromCmd(commonAdapterName, headInst)

    propertyLst = self._serializeAdapterPropertySelection(adapterModel, adapter, tailModel)
    adapter.toDb()

    jsonData = json.dumps(self._propertiesAssign(adapter, \
        self._dictAssign, \
        {}, \
        propertyLst))

    firstCmdModel = Command.objects.get(name=headInst.name)
    abm = AdapterBuffer(
      fromCmd=firstCmdModel,
      toCmd=tailModel,
      adapter=adapterModel,
      data=jsonData
    )
    abm.save()

    return jsonData

  def bridgeFromDb(self, adapterBufferModel, callbackFxn, actionQ=[]):
    jsonData = json.loads(adapterBufferModel.data)
    adapterModel = adapterBufferModel.adapter
    adapterKlass = importClass(adapterModel.importPath)
    adapter = adapterKlass()
    for k,v in jsonData.items():
      setattr(adapter, k, v)

    adapter.fromDb()

    propertyLst = self._naivieAdapterPropertySelection(
      adapterModel,
      adapterBufferModel.toCmd
    )
    if(hasattr(adapter, "render")):
      val = adapter.toUi()
      val["importPath"] = adapterModel.importPath
      val["adapterBufferModelId"] = adapterBufferModel.id

      actionQ.append({
        "action": "startAdapterUi",
        "val": json.dumps(val)
        })
    else:
      dataDict = self._propertiesAssign(
        adapter,
        self._dictAssign,
        {},
        propertyLst
      )

      callbackFxn(self.getCmdComplex(adapterBufferModel.toCmd, [], dataDict))

  def bridgeFromUIAdapter(self, adapterBufferModel, adapterObj):
    propertyLst = self._naivieAdapterPropertySelection(
        adapterBufferModel.adapter,
        adapterBufferModel.toCmd
        )
    dataDict = self._propertiesAssign(
        adapterObj,
        self._dictAssign,
        {},
        propertyLst
        )

    cmd = self.getCmdComplex(adapterBufferModel.toCmd, [], dataDict)
    return cmd

  # TODO: to support fall back
  def _probeAdapter(self, headClass, tailClass):
    return self._naivieAdapterMatching(headClass.gongs, tailClass.notations)

  def adaptFromCmd(self, adapterName, cmd):
    """Most users should not need to use this fxn. Try bridge() first"""
    try:
      adapterModel = Adapter.objects.get(name=adapterName)
    except Adapter.DoesNotExist:
      adapterModel = None

    adapter = None
    if adapterModel is not None:
      adapterKlass = importClass(adapterModel.importPath)
      adapter = adapterKlass()
      adapter = self._assignAdapterPropertiesFromCmd(
          adapterModel.propertyLst,
          adapter,
          cmd
          )
    return (adapterModel, adapter)

  def _adaptToCmd(self, adapterModel, adapter, cmd):
    if adapterModel is not None and adapter is not None and cmd is not None:
      cmd = self._assignProperties(adapterModel.property, cmd, adapter)
    return cmd

  def _assignAdapterProperties(self, properties, o1, o2):
    for property in properties:
      try:
        setattr(o1, property, getattr(o2, property))
      except AttributeError:
        try:
          setattr(o1, property, getattr(o2, "_" + property))
        except AttributeError:
          pass
    return o1

  def _assignAdapterPropertiesFromCmd(self, properties, adapter, cmd):
    form = cmd.paramForm
    if form.isValid():
      formData = form.clean()
      for property in properties:
        try:
          setattr(
              adapter,
              property,
              cmd.paramForm.cleanedData[property]
              )
        except KeyError:
          try:
            setattr(adapter, property, getattr(cmd, property))
          except AttributeError:
            try:
              setattr(adapter, property, getattr(cmd, "_" + property))
            except AttributeError:
              pass
    else:
      # TODO: somehow show/log/raise errors
      import logging
      logger = logging.getLogger("theory.usr")
      logger.error(
        f"bridge _assignAdapterPropertiesFromCmd err: {form.errors}"
      )
      print(
        f"bridge _assignAdapterPropertiesFromCmd err: {form.errors}"
      )
    return adapter

  def _executeCommand(
      self,
      cmd,
      cmdModel,
      actionQ=[],
      forceSync=False,
      runMode=None,
      ):
    if runMode is None:
      runMode = cmdModel.runMode

    try:
      if runMode == Command.RUN_MODE_ASYNC:
        if forceSync:
          cmd.run(
            paramFormData=cmd.paramForm.toPython(), cmdId=int(cmdModel.id)
          )
        else:
          cmd.apply_async(
              kwargs={
                "cmdId": int(cmdModel.id),
                "paramFormData": cmd.paramForm.toPython()
              },
          )
      else:
        if not cmd.paramForm.isValid():
          return False
        cmd.cmdId = int(cmdModel.id)
        cmd.actionQ = actionQ
        cmd.run()
      return True
    except Exception as e:
      import logging
      logger = logging.getLogger(__name__)
      logger.error(e, exc_info=True)
      raise e

  def executeEzCommand(
      self,
      appName,
      cmdName,
      args,
      kwargs,
      actionQ=[],
      forceSync=False,
      ):
    if appName == "theory" and args == []:
      # for first time running
      classImportPath = "theory.apps.command.{0}.{1}".format(
          cmdName,
          cmdName[0].upper() + cmdName[1:]
          )
      cmdKlass = importClass(classImportPath)
      cmd = cmdKlass()
      cmdParamForm = importClass(classImportPath).ParamForm
      cmd.paramForm = cmdParamForm()
      cmd.paramForm.fillFinalFields(None, args, kwargs)
      cmd.paramForm.isValid()
      # mainly for testing theory
      dummyCmdObj = type('DummyCmdModel', (object,), {})()
      dummyCmdObj.id = -1
      return (
          cmd,
          self._executeCommand(
            cmd,
            dummyCmdObj,
            actionQ=actionQ,
            forceSync=forceSync,
            runMode=Command.RUN_MODE_SIMPLE,
            )
          )
    else:
      cmdModel = Command.objects.get(app=appName, name=cmdName)
      cmd = self.getCmdComplex(cmdModel, args, kwargs)
    return (cmd, self._executeCommand(cmd, cmdModel, actionQ, forceSync))
