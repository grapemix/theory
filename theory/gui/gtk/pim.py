#!/usr/bin/env python2

# Get it from https://github.com/aeosynth/Pim/blob/master/pim
# Copyright (c) 2010 James Campos
# Pim is released under the MIT license.

# Dependencies: python2, pygtk
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
# set as wallpaper
# animated gifs
# python3

### Thanks ###
# alterecco, for making [visible](http://drop.dotright.net/visible) (dead),
#   and inspiring me to make this program.


### Pim ###
# A Python image viewer with vim-like keybindings.
# v0.2.0

from optparse import OptionParser
from gi.repository import GLib as glib
from gi.repository import Gtk as gtk
from gi.overrides import keysyms as keys
from gi.repository import Gdk as gdk
from gi.repository.GdkPixbuf import Pixbuf
#import glib
#import gtk
#from gtk import keysyms as keys
#from gtk import gdk


class Pim(object):
  _fitWidthByDefault = True
  _fullscreen = True

  def __init__(self):
    self.slideshow = False
    self.slideshowDelay = 5
    self._fileIndex = 0
    self._zoomLock = False
    self.fileLst = []
    self._selectedFileDict = {}

    self.binds = (
      #(modifer, key, function, args)
      #supported modifiers: gdk.SHIFT_MASK, gdk.CONTROL_MASK, gdk.MOD1_MASK (alt key)
      (0,              keys.q,     self.quit),
      (0,              keys.f,     self.toggleFullscreen),

      #if True, scroll in the horizontal direction.
      (0,              keys.Left,  self.scroll, gtk.ScrollType.STEP_BACKWARD, True),
      (0,              keys.Down,  self.scroll, gtk.ScrollType.STEP_FORWARD, False),
      (0,              keys.Up,    self.scroll, gtk.ScrollType.STEP_BACKWARD, False),
      (0,              keys.Right, self.scroll, gtk.ScrollType.STEP_FORWARD, True),

      (0,              keys.g,     self.scroll, gtk.ScrollType.START, False),
      (gdk.ModifierType.SHIFT_MASK, keys.G,     self.scroll, gtk.ScrollType.END, False),

      (0,              0x02d,     self.zoomDelta, -.5),
      (0,              0x03d,     self.zoomDelta, +.5),
      (0,              keys.e,     self.toggleSlideshow),
      (0,              keys.z,     self.toggleZoomLock),

      (0,              keys._1,    self.zoomTo, 1),
      (0,              keys._2,    self.zoomTo, 2),
      (0,              keys._3,    self.zoomTo, 3),
      #back to fullscreen
      (0,              keys._5,    self.zoomTo, 0),

      (0,              keys.space, self.toggleFileSelection),

      (gdk.ModifierType.SHIFT_MASK, keys.Right, self.moveFileIndex, 1),
      (gdk.ModifierType.SHIFT_MASK, keys.Left, self.moveFileIndex, -1),
      (gdk.ModifierType.SHIFT_MASK, keys.Down,  self.scroll, gtk.ScrollType.PAGE_FORWARD, False),
      (gdk.ModifierType.SHIFT_MASK, keys.Up,    self.scroll, gtk.ScrollType.PAGE_BACKWARD, False),
      )

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
    if(not self._selectedFileDict.has_key(self._fileIndex)):
      self._selectedFileDict[self._fileIndex] = self.fileLst[self._fileIndex]
    else:
      del self._selectedFileDict[self._fileIndex]
    self.updateTitle()

  def toggleZoomLock(self):
    self._zoomLock = not self._zoomLock


  def quit(self):
    #gtk.main_quit()
    self.win.destroy()


  def scroll(self, scrolltype, horizontal):
    isPageEnd = False

    scrollUpper = self.scrolledWin.get_vadjustment().get_upper()
    scrollSize = self.scrolledWin.get_vadjustment().get_page_size()
    scrollEnd = scrollUpper - scrollSize
    scrollCurrent = self.scrolledWin.get_vadjustment().get_value()

    isPageEnd = (scrollEnd == scrollCurrent)
    if(isPageEnd and (scrolltype==gtk.ScrollType.STEP_FORWARD or scrolltype==gtk.ScrollType.PAGE_FORWARD)):
      self.moveFileIndex(1)
    else:
      self.scrolledWin.emit('scroll-child', scrolltype, horizontal)


  def toggleSlideshow(self):
    self.slideshow = not self.slideshow
    if self.slideshow:
      self.timerId = glib.timeout_add_seconds(self.slideshowDelay, self.moveFileIndex, 1)
    else:
      glib.source_remove(self.timerId)
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
    #this doesn't work well with the scrollbars. I don't know if I just need to call some random function or if it's a gtk bug.
    #http://www.gtkforums.com/about6831.html
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
          '[selected]' if self._selectedFileDict.has_key(self._fileIndex) else '',
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

    self.scroll(gtk.ScrollType.START, False)
    self.scroll(gtk.ScrollType.START, True)

    return True #for the slideshow


  def handleKeyPress(self, widget, event):
    #ignore everything but shift, control, and alt modifiers
    state = event.state & (gdk.ModifierType.SHIFT_MASK | gdk.ModifierType.CONTROL_MASK | gdk.ModifierType.MOD1_MASK)
    keyval = event.keyval
    for bind in self.binds:
      if keyval == bind[1] and state == bind[0]:
        funk = bind[2]
        args = bind[3:]
        funk(*args)
        return
    print event


  def main(self):
    screen = gdk.Screen.get_default()
    self.sWidth = screen.get_width()
    self.sHeight = screen.get_height()
    self.sRatio = float(self.sWidth) / float(self.sHeight)

    self.win = gtk.Window()
    self.win.connect('destroy', gtk.main_quit)
    self.win.connect("key_press_event", self.handleKeyPress)

    self.scrolledWin = gtk.ScrolledWindow()
    self.scrolledWin.set_policy(gtk.PolicyType.AUTOMATIC, gtk.PolicyType.AUTOMATIC)
    self.win.add(self.scrolledWin)

    viewport = gtk.Viewport()
    viewport.modify_bg(gtk.StateFlags.NORMAL, gdk.color_parse('#000000'))
    viewport.set_shadow_type(gtk.ShadowType.NONE)
    self.scrolledWin.add(viewport)

    self.image = gtk.Image()
    viewport.add(self.image)

    self.moveFileIndex(0)
    self.win.show_all()
    if self.fullscreen:
      self.win.fullscreen()
    gtk.main()
