# -*- coding: utf-8 -*-
#!/usr/bin/env python
##### System wide lib #####
import json

##### Theory lib #####
from theory.adapter import BaseUIAdapter
from theory.core.exceptions import CommandSyntaxError
from theory.model import Adapter, AdapterBuffer, Command
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
    #return setattr(o, k, v)

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
      #assignFxn = lambda o, k, v: setattr(o, k, v)
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
    cmd.paramForm.fillInitFields(cmdModel, args, kwargs)
    cmd.paramForm.is_valid()
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
    cmdParam = [i.name for i in tailModel.param]
    for i in adapterModel.property:
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
      adapter.render()

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
    abm = AdapterBuffer(fromCmd=firstCmdModel, toCmd=tailModel, adapter=adapterModel, data=jsonData)
    abm.save()

    return jsonData

  def bridgeFromDb(self, adapterBufferModel, callbackFxn, uiParam={}):
    jsonData = json.loads(adapterBufferModel.data)
    adapterModel = adapterBufferModel.adapter
    adapterKlass = importClass(adapterModel.importPath)
    adapter = adapterKlass()
    for k,v in jsonData.iteritems():
      setattr(adapter, k, v)

    adapter.fromDb()

    propertyLst = self._naivieAdapterPropertySelection(adapterModel, adapterBufferModel.toCmd)
    if(hasattr(adapter, "render")):
      adapter.render(uiParam=uiParam)
      adapter.bridge = self
      self.propertyLst = propertyLst
      self.adapterBufferModel = adapterBufferModel
      self.callbackFxn = callbackFxn
    else:
      dataDict = self._propertiesAssign(adapter, \
          self._dictAssign, \
          {}, \
          propertyLst)

      callbackFxn(self.getCmdComplex(adapterBufferModel.toCmd, [], dataDict))

  def bridgeFromUIAdapter(self, adapter):
    dataDict = self._propertiesAssign(adapter, \
        self._dictAssign, \
        {}, \
        self.propertyLst)

    cmd = self.getCmdComplex(self.adapterBufferModel.toCmd, [], dataDict)
    self.callbackFxn(cmd)

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
    if(adapterModel!=None):
      adapterKlass = importClass(adapterModel.importPath)
      adapter = adapterKlass()
      #adapter = self._assignAdapterProperties(adapterModel.property, adapter, cmd)
      adapter = self._assignAdapterPropertiesFromCmd(adapterModel.property, adapter, cmd)
    return (adapterModel, adapter)

  def _adaptToCmd(self, adapterModel, adapter, cmd):
    if(adapterModel!=None and adapter!=None and cmd!=None):
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
    """This fxn """
    form = cmd.paramForm
    if(form.is_valid()):
      formData = form.clean()
      for property in properties:
        try:
          setattr(adapter, property, cmd.paramForm.clean_data[property])
        except AttributeError:
          try:
            setattr(adapter, property, getattr(cmd, property))
          except AttributeError:
            try:
              setattr(adapter, property, getattr(cmd, "_" + property))
            except AttributeError:
              pass
    else:
      # TODO: somehow show/log/raise errors
      print form.errors
    return adapter

  def _execeuteCommand(self, cmd, cmdModel, uiParam={}, forceSync=False):
    if(cmdModel.runMode==cmdModel.RUN_MODE_ASYNC):
      if(forceSync):
        cmd.run(paramFormData=cmd.paramForm.toPython())
      else:
        cmd.delay(paramFormData=cmd.paramForm.toPython())
    else:
      if(not cmd.paramForm.is_valid()):
        return False
      cmd._uiParam = uiParam
      cmd.run()
    return True


  def execeuteEzCommand(
      self,
      appName,
      cmdName,
      args,
      kwargs,
      uiParam={},
      forceSync=False
      ):
    cmdModel = Command.objects.get(app=appName, name=cmdName)
    cmd = self.getCmdComplex(cmdModel, args, kwargs)
    return (cmd, self._execeuteCommand(cmd, cmdModel, uiParam, forceSync))
