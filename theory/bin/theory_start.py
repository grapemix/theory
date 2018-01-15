# -*- coding: utf-8 -*-
#!/usr/bin/env python
from optparse import OptionParser

if __name__ == "__main__":
  parser = OptionParser()
  parser.add_option("-c", "--celery", dest="celery",
                    action="store_true", default=False,
                    help="start celery daemon")
  parser.add_option("--reactor", dest="reactor",
                    action="store_true", default=False,
                    help="start reactor daemon")
  (options, args) = parser.parse_args()

  if(options.celery):
    from theory.core.loader.backendLoader import startCelery
    startCelery()
  elif(options.reactor):
    from theory.core.loader.reactorLoader import wakeup
    wakeup(None)
  else:
    from theory.core.loader.guiLoader import wakeup
    wakeup(None)
