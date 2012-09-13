# -*- coding: utf-8 -*-
#!/usr/bin/env python
##### System wide lib #####

##### Theory lib #####
from theory.adapter import BaseUIAdapter
from theory.model import Command, Adapter
from theory.utils.importlib import  import_class

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
    return setattr(o, k, v)

  def _dictAssign(self, o, k, v):
    o[k] = v
    return o

  def _getCmdForAssignment(self, cmdModel):
    cmdKlass = import_class(cmdModel.classImportPath)
    cmd = cmdKlass()

    if(cmdModel.runMode==cmdModel.RUN_MODE_ASYNC):
      assignFxn = self._dictAssign
      storage = {}
    else:
      #assignFxn = lambda o, k, v: setattr(o, k, v)
      assignFxn = self._objAssign
      storage = cmd

    return (cmd, assignFxn, storage)

  def _propertiesAssign(self, adapter, assignFxn, storage, kwargs):
    for k,v in kwargs.iteritems():
      try:
        v = getattr(adapter, property)
        storage = assignFxn(storage, k, v)
      except AttributeError:
        try:
          v = getattr(adapter, "_" + property)
          storage = assignFxn(storage, k, v)
        except AttributeError:
          pass
    return storage

  def getCmdForReactor(self, cmdModel, *args, **kwargs):
    (cmd, assignFxn, storage) = self._getCmdForAssignment(cmdModel)
    cmdArgs = [i for i in cmdModel.param if(not i.isOptional)]
    if(args!=[]):
      for i in range(len(cmdArgs)):
        try:
          assignFxn(storage, cmdArgs[i].name, args[i])
        except IndexError:
          # This means the number of param given unmatch the number of param register in *.command
          raise CommandSyntaxError
    if(kwargs!={}):
      for k,v in kwargs.iteritems():
        storage = assignFxn(storage, k, v)

    return (cmd, storage)

  # TODO: should be replaced later on. At least inheritance case should be
  # considered
  def _naivieAdapterMatching(self, adapterNameLst1, adapterNameLst2):
    for i in adapterNameLst1:
      if(i in adapterNameLst2):
        return i
    return None

  def bridge(self, headClass, tailModel):
    (tailClass, assignFxn, storage) = self._getCmdForAssignment(tailModel)
    commonAdapterName = self._probeAdapter(headClass, tailClass)

    (adapterModel, adapter) = self.adaptFromCmd(commonAdapterName, headClass)
    #if(adapter.hasattr(isDisplayWidgetCompatable) and adapter.isDisplayWidgetCompatable):
    if(issubclass(BaseUIAdapter, adapter)):
      pass

    return (tailClass, self._propertiesAssign(adapter, assignFxn, storage, adapterModel))

  # TODO: to support fall back
  def _probeAdapter(self, headClass, tailClass):
    return self._naivieAdapterMatching(headClass.gongs, tailClass.notations)

  def adaptFromCmd(self, adapterName, cmd):
    try:
      adapterModel = Adapter.objects.get(name=adapterName)
    except Adapter.DoesNotExist:
      adapterModel = None

    adapter = None
    if(adapterModel!=None):
      adapterKlass = import_class(adapterModel.importPath)
      adapter = adapterKlass()
      adapter = self._assignAdapterProperties(adapterModel.property, adapter, cmd)
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
