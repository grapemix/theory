# -*- coding: utf-8 -*-
#!/usr/bin/env python
##### System wide lib #####
import os.path
import sys

##### Theory lib #####
from theory.apps.command.baseCommand import AsyncCommand
from theory.gui import field

##### Theory third-party lib #####

##### Local app #####

##### Theory app #####

##### Misc #####

class UpdateUiApi(AsyncCommand):
  """
  update UI Api. You can also run this command by
  `THEORY_SETTINGS_MODULE="YOUR_MODULE" python apps/command/updateUiApi.py`
  you might need to replace "import theory_pb2 as theory__pb2" to
  "import theory.gui.theory_pb2 as theory__pb2" in "gui/theory_pb2_grpc.py"
  """
  name = "updateUiApi"
  verboseName = "updateUiApi"

  typing = False
  ignore_result = False

  _drums = {"Terminal": 1,}

  @property
  def stdOut(self):
    return self._stdOut

  class ParamForm(AsyncCommand.ParamForm):
    pass

  def run(self, *args, **kwargs):
    self._stdOut = "Generating UI api\n"
    from grpc_tools import protoc
    includeRootPathLst = []
    for i in sys.path:
      if i.endswith("site-packages") or i.endswith("dist-packages"):
        includeRootPathLst.append(i + "/grpc_tools/_proto/")
    includeRootPathLst = list(set(includeRootPathLst))

    param = [""]
    for includeRootPath in includeRootPathLst:
      if os.path.isdir(includeRootPath):
        param.append('-I{0}'.format(includeRootPath))
    param.append('-I./gui/')
    param.append('--python_out=./gui/')
    param.append('--grpc_python_out=./gui/')
    param.append('./gui/theory.proto')
    param.append('./gui/grpc_health_check.proto')
    protoc.main(tuple(param))

    #includeRootPath = []
    #for tok in os.path.abspath(__file__).split("/"):
    #  includeRootPath.append(tok)
    #  if tok == "site-packages" or tok == "dist-packages":
    #    break
    #includeRootPath = "/".join(includeRootPath)
    #includeRootPath += "/grpc_tools/_proto/"
    #protoc.main(
    #    (
    #  '',
    #  '-I{0}'.format(includeRootPath),
    #  '-I./gui/',
    #  '--python_out=./gui/',
    #  '--grpc_python_out=./gui/',
    #  './gui/theory.proto',
    #    )
    #)
    self._stdOut += "Done"

if __name__ == '__main__':
  UpdateUiApi().run()
