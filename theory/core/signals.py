from theory.dispatch import Signal

requestStarted = Signal()
requestFinished = Signal()
gotRequestException = Signal(providingArgs=["request"])
