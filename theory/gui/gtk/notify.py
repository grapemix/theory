from gi.repository import Notify

__all__ = ("getNotify",)

def getNotify(title, content):
  Notify.init(title)
  note = Notify.Notification.new(title, content, "dialog-information")
  note.show ()

