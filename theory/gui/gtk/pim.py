#!/usr/bin/env python3

# Get it from https://github.com/aeosynth/Pim/blob/master/pim
# Copyright (c) 2010 James Campos
# Pim is released under the MIT license.

### TODO ###
# resolve scrollbar issue
# hide pointer in fullscreen
# status text
# better shift masking
# rotating
# pim.desktop
# mouse panning / keybinds
# fit width / height
# marking (echo $current >> pim-marked)

### Thanks ###
# alterecco, for making [visible](http://drop.dotright.net/visible) (dead),
#   and inspiring me to make this program.


### Pim ###
# A Python image viewer with vim-like keybindings.
# v0.2.0

from optparse import OptionParser
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import GLib
from gi.repository import Gtk
from gi.repository import Gdk
from gi.repository.GdkPixbuf import Pixbuf


class Pim(object):
  _fitWidthByDefault = True
  _fullscreen = True

  def __init__(self, additionalBinds=[], fileSelectChangeCallbackFxn=None):
    self.slideshow = False
    self.slideshowDelay = 5
    self._fileIndex = 0
    self._zoomLock = False
    self.fileLst = []
    self._selectedFileDict = {}

    self.binds = [
      #(modifer, key, function, args)
      #supported modifiers: Gdk.SHIFT_MASK, Gdk.CONTROL_MASK, Gdk.MOD1_MASK (alt key)
      (0,              Gdk.KEY_q,     self.quit),
      (0,              Gdk.KEY_f,     self.toggleFullscreen),

      #if True, scroll in the horizontal direction.
      (0,              Gdk.KEY_Left,  self.scroll, Gtk.ScrollType.STEP_BACKWARD, True),
      (0,              Gdk.KEY_Down,  self.scroll, Gtk.ScrollType.STEP_FORWARD, False),
      (0,              Gdk.KEY_Up,    self.scroll, Gtk.ScrollType.STEP_BACKWARD, False),
      (0,              Gdk.KEY_Right, self.scroll, Gtk.ScrollType.STEP_FORWARD, True),

      (0,              Gdk.KEY_g,     self.scroll, Gtk.ScrollType.START, False),
      (Gdk.ModifierType.SHIFT_MASK, Gdk.KEY_G,     self.scroll, Gtk.ScrollType.END, False),

      (0,              0x02d,     self.zoomDelta, -.5),
      (0,              0x03d,     self.zoomDelta, +.5),
      (0,              Gdk.KEY_e,     self.toggleSlideshow),
      (0,              Gdk.KEY_z,     self.toggleZoomLock),

      (Gdk.ModifierType.SHIFT_MASK, Gdk.KEY_1,    self.zoomTo, 1),
      (Gdk.ModifierType.SHIFT_MASK, Gdk.KEY_2,    self.zoomTo, 2),
      (Gdk.ModifierType.SHIFT_MASK, Gdk.KEY_3,    self.zoomTo, 3),
      #back to fullscreen
      (Gdk.ModifierType.SHIFT_MASK, Gdk.KEY_5,    self.zoomTo, 0),

      (0,              Gdk.KEY_space, self.toggleFileSelection),

      (Gdk.ModifierType.SHIFT_MASK, Gdk.KEY_Right, self.moveFileIndex, 1),
      (Gdk.ModifierType.SHIFT_MASK, Gdk.KEY_Left, self.moveFileIndex, -1),
      (Gdk.ModifierType.SHIFT_MASK, Gdk.KEY_Down,  self.scroll, Gtk.ScrollType.PAGE_FORWARD, False),
      (Gdk.ModifierType.SHIFT_MASK, Gdk.KEY_Up,    self.scroll, Gtk.ScrollType.PAGE_BACKWARD, False),
      ]
    for i in additionalBinds:
      i[1] = getattr(keys, i[1])
      self.binds.append(i)

    self.fileSelectChangeCallbackFxn = fileSelectChangeCallbackFxn

  @property
  def fitWidthByDefault(self):
    return self._fitWidthByDefault

  @fitWidthByDefault.setter
  def fitWidthByDefault(self, fitWidthByDefault):
    self._fitWidthByDefault = fitWidthByDefault

  @property
  def fullscreen(self):
    return self._fullscreen

  @fullscreen.setter
  def fullscreen(self, fullscreen):
    self._fullscreen = fullscreen

  @property
  def selectedFileLst(self):
    return self._selectedFileDict.values()

  @property
  def selectedIdxLst(self):
    return self._selectedFileDict.keys()

  def toggleFileSelection(self):
    if self._fileIndex not in self._selectedFileDict:
      self._selectedFileDict[self._fileIndex] = self.fileLst[self._fileIndex]
    else:
      del self._selectedFileDict[self._fileIndex]
    self.updateTitle()

  def toggleZoomLock(self):
    self._zoomLock = not self._zoomLock


  def quit(self):
    self.win.destroy()


  def scroll(self, scrolltype, horizontal):
    isPageEnd = False

    scrollUpper = self.scrolledWin.get_vadjustment().get_upper()
    scrollSize = self.scrolledWin.get_vadjustment().get_page_size()
    scrollEnd = scrollUpper - scrollSize
    scrollCurrent = self.scrolledWin.get_vadjustment().get_value()

    isPageEnd = (scrollEnd == scrollCurrent)
    if(isPageEnd and (scrolltype==Gtk.ScrollType.STEP_FORWARD or scrolltype==Gtk.ScrollType.PAGE_FORWARD)):
      self.moveFileIndex(1)
    else:
      self.scrolledWin.emit('scroll-child', scrolltype, horizontal)


  def toggleSlideshow(self):
    self.slideshow = not self.slideshow
    if self.slideshow:
      self.timerId = Glib.timeout_add_seconds(self.slideshowDelay, self.moveFileIndex, 1)
    else:
      Glib.source_remove(self.timerId)
    self.updateTitle()


  def toggleFullscreen(self):
    self.fullscreen = not self.fullscreen
    if self.fullscreen:
      self.win.fullscreen()
      self.zoomPercent = self.getFullscreenZoomPercent()
    else:
      self.win.unfullscreen()
      self.zoomPercent = 1
    self.updateImage()


  def getFullscreenZoomPercent(self):
    pboWidth = self.pixbufOriginal.get_width()
    pboHeight = self.pixbufOriginal.get_height()
    pbRatio = float(pboWidth) / float(pboHeight)

    if(self._fitWidthByDefault):
      return float(self.sWidth) / float(pboWidth)
    if pbRatio > self.sRatio:
      #pixbuf is proportionally wider than screen
      return float(self.sWidth) / float(pboWidth)
    else:
      return float(self.sHeight) / float(pboHeight)


  def updateImage(self):
    ''' Show the final image '''

    pboWidth = self.pixbufOriginal.get_width()
    pboHeight = self.pixbufOriginal.get_height()
    if self.zoomPercent is 1:
      pixbufFinal = self.pixbufOriginal
      pbfWidth = pboWidth
      pbfHeight = pboHeight
    else:
      pbfWidth = int(pboWidth * self.zoomPercent)
      pbfHeight = int(pboHeight * self.zoomPercent)
      pixbufFinal = self.pixbufOriginal.scale_simple(
          pbfWidth, pbfHeight, 2)

    self.updateTitle()
    if not self.fullscreen:
      self.resizeWindow(pbfWidth, pbfHeight)


  def resizeWindow(self, pbfWidth, pbfHeight):
    #this doesn't work well with the scrollbars. I don't know if I just need to call some random function or if it's a Gtk bug.
    #http://www.Gtkforums.com/about6831.html
    winWidth = pbfWidth if pbfWidth < self.sWidth else self.sWidth
    winHeight = pbfHeight if pbfHeight < self.sHeight else self.sHeight

    self.win.resize(winWidth, winHeight)


  def updateTitle(self):
    self.win.set_title(
        "pim %d/%d %d%% %s%s%s" % (
          self._fileIndex,
          len(self.fileLst),
          self.zoomPercent * 100,
          self.fileLst[self._fileIndex],
          ' [slideshow]' if self.slideshow else '',
          '[selected]' if self._fileIndex in self._selectedFileDict else '',
          )
        )


  def zoomDelta(self, delta):
    self.zoomPercent = self.zoomPercent + delta
    self.updateImage()


  def zoomTo(self, percent):
    self.zoomPercent = percent if percent else self.getFullscreenZoomPercent()
    self.updateImage()


  def moveFileIndex(self, delta):
    self._fileIndex = (self._fileIndex + delta) % len(self.fileLst)

    path = self.fileLst[self._fileIndex]
    self.pixbufOriginal = Pixbuf.new_from_file(path)
    if not self._zoomLock:
      if self.fullscreen:
        self.zoomPercent = self.getFullscreenZoomPercent()
      else:
        self.zoomPercent = 1
    self.updateImage()
    self.image.set_from_pixbuf(self.pixbufOriginal)

    self.scroll(Gtk.ScrollType.START, False)
    self.scroll(Gtk.ScrollType.START, True)

    if self.fileSelectChangeCallbackFxn is not None:
      self.fileSelectChangeCallbackFxn(self._fileIndex)

    return True #for the slideshow


  def handleKeyPress(self, widget, event):
    #ignore everything but shift, control, and alt modifiers
    state = event.state & (Gdk.ModifierType.SHIFT_MASK | Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.MOD1_MASK)
    keyval = event.keyval
    for bind in self.binds:
      if keyval == bind[1] and state == bind[0]:
        funk = bind[2]
        args = bind[3:]
        funk(*args)
        return
    print(event)


  def main(self):
    screen = Gdk.Screen.get_default()
    self.sWidth = screen.get_width()
    self.sHeight = screen.get_height()
    self.sRatio = float(self.sWidth) / float(self.sHeight)

    self.win = Gtk.Window()
    self.win.connect('destroy', Gtk.main_quit)
    self.win.connect("key_press_event", self.handleKeyPress)

    self.scrolledWin = Gtk.ScrolledWindow()
    self.scrolledWin.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
    self.win.add(self.scrolledWin)

    viewport = Gtk.Viewport()
    viewport.modify_bg(Gtk.StateFlags.NORMAL, Gdk.color_parse('#000000'))
    viewport.set_shadow_type(Gtk.ShadowType.NONE)
    self.scrolledWin.add(viewport)

    self.image = Gtk.Image()
    viewport.add(self.image)

    self.moveFileIndex(0)
    self.win.show_all()
    if self.fullscreen:
      self.win.fullscreen()
    Gtk.main()
