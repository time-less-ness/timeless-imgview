import os
import sys
import math
import random
import reusables
import shutil
import time;

from kivy.uix.button import Button
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.scrollview import ScrollView
from kivy.core.window import Window
from kivy.clock import Clock
from kivy.loader import Loader
from kivy.logger import Logger
from kivy.app import App
from tiviewlib.MainImage import MainImage
#from tiviewlib.kivy_hover import MouseOver

class ImageViewer(FloatLayout):

    def __init__(self,
            delete_dir=f"{os.environ['HOME']}/.Trash",
            deviceRes=None,
            appConfig=None,
            **kwargs):
        super().__init__(**kwargs)

        # setup fullscreen status and device resolution
        if deviceRes != None:
            self.deviceRes = deviceRes
        else:
            self.deviceRes = [800, 600]
        self.fullscreen_mode = False
        # zoom of window itself
        self.windowZoom = 1
        self.imgZoom = 1

        if appConfig != None:
            self.appConfig = appConfig

        # Capture keyboard input
        self._keyboard = Window.request_keyboard(self._keyboard_closed, self)
        self._keyboard.bind(on_key_down=self._on_keyboard_down)
        self._keyboard.bind(on_key_up=self._on_keyboard_up)

       # imageSet=Metadata about images
        self.imageSet = {}
        self.imageSet['del_dir'] = delete_dir
        self.imageSet['setPos'] = 0
        self.imageSet['changeType'] = 'ordered'
        self.imageSet['orderedList'] = []

        # make trash dir, init random seed, get list of images to view
        os.makedirs(self.imageSet['del_dir'], exist_ok=True)
        random.seed()
        self._get_images()

        # Define widgets used so we can reference them elsewhere
        self.image = MainImage(imageSet=self.imageSet)
        self.sv = ScrollView(size=Window.size)
        self.sv.scroll_x = 0.5
        self.sv.scroll_y = 0.5
        self.sv.add_widget(self.image)
        self.add_widget(self.sv)

        # deal with resizing
        self.bind(pos=self.on_size, size=self.on_size)

        # progressive scrolling - up down left right
        self.scrollingDir = [False, False, False, False]
        self.scrollPix = 1
        self.progressiveSpeed = 2
        self.progressiveReset = 20
        self.scrollEvent = None
        # just over 100x/sec
        self.scrollScheduleInterval = 0.008

        # slideshow event
        self.slideshowEvent = None
        self.slideshowInterval = 40

        # for scary actions, you double-tap the command,
        # such as Q/Esc to quit, or Del to delete, or m+X to move
        self.lastScaryTimestamp = 0
        self.previousKey = ''
        self.currKey = ''

        # for maximising and unmaximising
        self.unmaxSize = None
        self.winTop = None
        self.winLeft = None

        # user feedback font settings
        try:
            self.user_feedback_font_size = int(self.appConfig.get("UI", "feedback-fontsize"))
            self.user_feedback_fg = [float(i) for i in self.appConfig.get("UI", "feedback-fg").split(",")]
            self.user_feedback_bg = [float(i) for i in self.appConfig.get("UI", "feedback-bg").split(",")]
        except:
            self.user_feedback_font_size = 28
            self.user_feedback_fg = (0.95, 0.95, 0.95, 0.8)
            self.user_feedback_bg = (0.05, 0.05, 0.05, 0.8)

        # now that image loaded, also load cached next
        try:
            self.imageSet['cacheImage'] = Loader.image(self.imageSet['orderedList'][self.imageSet['setPos'] + 1]['image'])
            self.imageSet['cacheImage'].bind(on_load=self.image.cacheImage_loaded)
        except:
            # i guess we only had 1 image?
            pass

        # a place to put messages
        self.info_button = Button(text='timeless image viewer',
                                  font_name = "Times New Roman",
                                  font_size = self.user_feedback_font_size,
                                  size_hint=(1.0, 0.075),
                                  pos_hint={'x':0, 'y':.1},
                                  color = self.user_feedback_fg,
                                  background_color = self.user_feedback_bg
                                  )
        self.add_widget(self.info_button)
        Clock.schedule_once(self.user_feedback_clear, 1)

    def _get_images(self):
        self.imageSet['orderedList'] = []

        # might get a file or dir as argv
        toSort = False
        for inArg in sys.argv[1:]:
            toSort = True
            if os.path.isdir(inArg):
                dirName = inArg
                # append a / for dirName
                if dirName[-1] != '/':
                    dirName += '/'
                try:
                    for imgName in os.listdir(dirName):
                        # until JPEG2000 support is hacked in, don't include those
                        # also animated GIF seems to kill me
                        #if imgName.lower().endswith(("jpeg", "jpg", "png", "gif", "jp2")):
                        # endswith can be a string or tuple of strings
                        if imgName.lower().endswith(("jpeg", "jpg", "png")):
                            data = {'image': dirName + imgName, 'created': 0}
                            self.imageSet['orderedList'].append(data)
                except:
                    Logger.error(f"Couldn't collect images from {dirName}")
                Logger.debug(f"Collected files from {dirName} - total so far: {len(self.imageSet['orderedList'])}")
            elif os.path.isfile(inArg):
                toSort = False
                data = {'image': inArg, 'created': 0}
                self.imageSet['orderedList'].append(data)
            else:
                Logger.error(f"Input {inArg} is neither file nor directory. Ignoring.")

        # they come in some random order, so put them in filename order
        if toSort:
            self.imageSet['orderedList'].sort(key=lambda x: x['image'])

    def on_size(self, obj, size):
        """Make sure all children sizes adjust properly"""
        #Logger.debug(f"Resizing image itself to {size[0]}x{size[1]}, obj={obj}")
        self.image.size_hint_x = None
        self.image.size_hint_y = None
        self.image.width = size[0]
        self.image.height = size[1]
        self.image.xpos = 0
        self.image.ypos = 0

        self.sv.width = size[0]
        self.sv.height = size[1]

    def user_feedback(self, text, clearTime=2):
        self.info_button.text = text
        self.info_button.color = self.user_feedback_fg
        self.info_button.background_color = self.user_feedback_bg
        Clock.unschedule(self.user_feedback_clear, all=True)
        Clock.schedule_once(self.user_feedback_clear, clearTime)

    def user_feedback_clear(self, dt):
        self.info_button.text = ''
        self.info_button.color=(0,0,0,0)
        self.info_button.background_color=(0,0,0,0)

    # move or delete image
    def move_image(self, destDir):
        img = self.imageSet['orderedList'][self.imageSet['setPos']]
        if os.path.exists(f"{destDir}/{img['image']}"):
            self.user_feedback(f" ! img={destDir + '/' + img['image']} exists, not moving.")
            Logger.critical(f"img={destDir}/{img['image']} exists! doing nothing.")
        else:
            if "Trash" in destDir:
                Logger.info(f"DELETE img={img['image']} to destDir={destDir}")
                self.user_feedback(f" x> TRASHED")
            else:
                Logger.info(f"Move img={img['image']} to destDir={destDir}")
                self.user_feedback(f" -> MOVED to {destDir}")
            shutil.move(img['image'], destDir)
            self.imageSet['orderedList'].remove(img)
            self.change_to_image(self.imageSet['setPos'])

    # copy an image elsewhere
    def copy_image(self, destDir):
        img = self.imageSet['orderedList'][self.imageSet['setPos']]
        if os.path.exists(f"{destDir}/{img['image']}"):
            Logger.critical(f"img={destDir}/{img['image']} exists! doing nothing.")
            self.user_feedback(f" ! img={destDir + '/' + img['image']} exists, not copying.")
        else:
            Logger.info(f"Copy img={img['image']} to destDir={destDir}")
            shutil.copy(img['image'], destDir)
            self.user_feedback(f" >> COPIED to destDir={destDir}")

    def reset_scrollpos(self):
        self.sv.scroll_x = 0
        self.sv.scroll_y = 0

    def change_to_image(self, image_pos):
        self.imageSet['setPos'] = image_pos
        self.image.source = self.image.gen_image()
        self.image.reload()

    def _keyboard_closed(self):
        self._keyboard.unbind(on_key_down=self._on_keyboard_down)
        self._keyboard = None

    def calc_scroll_amt(self, direction, modifiers):
        # modify how much we scroll with keys
        if self.scrollingDir[direction] == True:
            self.scrollPix += self.progressiveSpeed
        else:
            self.scrollPix = self.progressiveReset

        if 'shift' in modifiers:
            tX = int(self.scrollPix / 2) + 1
        elif 'ctrl' in modifiers:
            tX = int(self.scrollPix / 5) + 1
        elif 'alt' in modifiers:
            tX = int(self.scrollPix / 18) + 1
        else:
            tX = self.scrollPix

        # now record which way are we scrolling
        self.scrollingDir = [False, False, False, False]
        self.scrollingDir[direction] = True

        return self.sv.convert_distance_to_scroll(tX, tX)

    def _on_keyboard_up(self, keyboard, keycode):
        # unschedule the keep-on-scrolling f()
        Clock.unschedule(self.scrollEvent, all=True)
        self.scrollEvent = None
        self.scrollPix = self.progressiveReset

    def keep_on_scrollin(self, dx):
        if self.scrollingDir[0] == True:
            self.sv.scroll_y += self.scrollAmount[1]
        elif self.scrollingDir[1] == True:
            self.sv.scroll_y -= self.scrollAmount[1]
        elif self.scrollingDir[2] == True:
            self.sv.scroll_x -= self.scrollAmount[0]
        elif self.scrollingDir[3] == True:
            self.sv.scroll_x += self.scrollAmount[0]

    def slideshowNextImage(self, dx):
        self.image.next_image('random')

    def _on_keyboard_down(self, keyboard, keycode, text, modifiers):
        #Logger.debug(f"keypress - keycode={keycode}, text={text}, modifiers={modifiers}")
        # all keyboard events cancel the slideshow
        if self.slideshowEvent:
            Clock.unschedule(self.slideshowEvent, all=True)
            self.slideshowEvent = None

        # keyboard events hide the cursor
        Window.show_cursor = False

        # list of potential doublekeys
        doubleKeycodes = {'c': "Copy File", 'q': "Quit Viewer", 'm': "Move File", 'delete': "Trash File"}

        # is this an initial press after some delay, or a quick successor?
        if (keycode[0] >= 97 and keycode[0] <= 122) or (keycode[0] >= 48 and keycode[0] <= 57) or (keycode[1] in ['delete']):
            # is this a potential double-key combo?
            currTs = time.time()
            if currTs - self.lastScaryTimestamp < 1:
                Logger.debug(f"Scary Action Enacted! - previousKey={self.previousKey}")
                self.currKey = keycode[1]
            elif (keycode[1] in doubleKeycodes.keys()):
                self.user_feedback(f"About to {doubleKeycodes[keycode[1]]}?", 1)
                Logger.debug(f"Scary Action Soon? - {doubleKeycodes[keycode[1]]}")
                self.lastScaryTimestamp = currTs
                self.previousKey = keycode[1]
                self.currKey = ''
            else:
                self.previousKey = ''
                self.currKey = ''
                self.lastScaryTimestamp = 0
        else:
            self.previousKey = ''
            self.currKey = ''
            self.lastScaryTimestamp = 0

        # KEY COMBO ITEMS ----
        if (self.currKey != '' and self.previousKey in doubleKeycodes.keys()):
            if (self.previousKey == 'm'):
                # move the item somewhere
                try:
                    fileDest = self.appConfig.get("ReadOnlySettings", f"dest-{self.currKey}")
                    self.move_image(os.path.expanduser(fileDest))
                except:
                    Logger.info(f"Tried to move to location with no keybinding={self.currKey}")
                    self.user_feedback(f"!!! Config file does not have a destination for key {self.currKey}", 3)
            elif (self.previousKey == 'c'):
                # copy the item somewhere
                try:
                    fileDest = self.appConfig.get("ReadOnlySettings", f"dest-{self.currKey}")
                    self.copy_image(os.path.expanduser(fileDest))
                except:
                    Logger.info(f"Tried to move to location with no keybinding={self.currKey}")
                    self.user_feedback(f"!!! Config file does not have a destination for key {self.currKey}", 3)
            elif self.currKey == 'q' and self.previousKey == 'q':
                # shut it down
                Logger.debug(f"Qx2, quitting! - currKey={self.currKey}, previousKey={self.previousKey}")
                App.get_running_app().stop()
            elif self.currKey == 'delete' and self.previousKey == 'delete':
                self.move_image(self.imageSet['del_dir'])

            self.previousKey = ''
            self.currKey = ''
            self.lastScaryTimestamp = 0
            return True

        # PANNING ----
        if keycode[1] == 'up':
            self.scrollAmount = self.calc_scroll_amt(0, modifiers)
            if self.scrollEvent == None:
                self.scrollEvent = Clock.schedule_interval(self.keep_on_scrollin, self.scrollScheduleInterval)
        elif keycode[1] == 'down':
            self.scrollAmount = self.calc_scroll_amt(1, modifiers)
            if self.scrollEvent == None:
                self.scrollEvent = Clock.schedule_interval(self.keep_on_scrollin, self.scrollScheduleInterval)
        elif keycode[1] == 'left':
            self.scrollAmount = self.calc_scroll_amt(2, modifiers)
            if self.scrollEvent == None:
                self.scrollEvent = Clock.schedule_interval(self.keep_on_scrollin, self.scrollScheduleInterval)
        elif keycode[1] == 'right':
            self.scrollAmount = self.calc_scroll_amt(3, modifiers)
            if self.scrollEvent == None:
                self.scrollEvent = Clock.schedule_interval(self.keep_on_scrollin, self.scrollScheduleInterval)
        # SLIDESHOW -----
        elif text == 's':
            # pull one random image, then schedule more on interval
            self.image.next_image('random')
            self.slideshowEvent = Clock.schedule_interval(self.slideshowNextImage, self.slideshowInterval)
            self.user_feedback(f"Starting slideshow with interval of {self.slideshowInterval} seconds.", 2)
        # IMAGE CHANGING -----
        elif keycode[1] == 'pagedown':
            self.image.next_image('ordered')
        elif keycode[1] == 'pageup':
            self.image.prev_image('ordered')
        elif keycode[1] == 'home':
            self.image.imageSet['setPos'] = 0
            self.image.source = self.image.gen_image()
        elif keycode[1] == 'end':
            self.image.imageSet['setPos'] = len(self.image.imageSet['orderedList']) - 1
            self.image.source = self.image.gen_image()
        elif text in ("'", '"'):
            if 'ctrl' in modifiers:
                self.image.next_image('ordered', 50)
            elif 'shift' in modifiers:
                self.image.next_image('ordered', 10)
            else:
                self.image.next_image('ordered')
        elif text in (';', ':'):
            if 'ctrl' in modifiers:
                self.image.prev_image('ordered', 50)
            elif 'shift' in modifiers:
                self.image.prev_image('ordered', 10)
            else:
                self.image.prev_image('ordered')
        elif text == ".":
            self.image.next_image('random')
        elif text == ',':
            self.image.prev_image('random')
        # ROTATING -----
        elif text == "[":
            Logger.debug(f"Rotate -90")
            self.image.rotation = -90
        elif text == "]":
            Logger.debug(f"Rotate +90")
            self.image.rotation = 90
        # ZOOMING -----
        elif text in ("-", "_"):
            if 'shift' in modifiers:
                self.windowZoom -= 0.1
                Window.size = (int(self.deviceRes[0] * self.windowZoom), int(self.deviceRes[1] * self.windowZoom))
                self.size = Window.size
            else:
                self.imgZoom *= 0.9
                self.image.size[0] = self.image.texture_size[0] * self.imgZoom
                self.image.size[1] = self.image.texture_size[1] * self.imgZoom
                self.image.zoomMode = 'pan'
                self.image.set_window_pos()
        elif text in ("=", "+"):
            if 'shift' in modifiers:
                self.windowZoom += 0.1
                Window.size = (int(self.deviceRes[0] * self.windowZoom), int(self.deviceRes[1] * self.windowZoom))
                self.size = Window.size
            else:
                self.imgZoom *= 1.1
                self.image.size[0] = self.image.texture_size[0] * self.imgZoom
                self.image.size[1] = self.image.texture_size[1] * self.imgZoom
                self.image.zoomMode = 'pan'
                self.image.set_window_pos()
        elif text == '2':
            self.imgZoom = 2
            self.image.size[0] = self.image.texture_size[0] * self.imgZoom
            self.image.size[1] = self.image.texture_size[1] * self.imgZoom
            self.image.zoomMode = 'pan'
            self.image.set_window_pos()
        elif text == '3':
            self.imgZoom = 3
            self.image.size[0] = self.image.texture_size[0] * self.imgZoom
            self.image.size[1] = self.image.texture_size[1] * self.imgZoom
            self.image.zoomMode = 'pan'
            self.image.set_window_pos()
        elif text == '4':
            self.imgZoom = 4
            self.image.size[0] = self.image.texture_size[0] * self.imgZoom
            self.image.size[1] = self.image.texture_size[1] * self.imgZoom
            self.image.zoomMode = 'pan'
            self.image.set_window_pos()
        elif text in ('z', '1'):
            # view 1:1
            self.imgZoom = 1
            self.image.zoomMode = 'pan'
            self.image.set_window_pos()
            self.image.be_zoom_1_to_1()
        elif text == 'x':
            # fit image to window - TODO: what should self.imgZoom be?
            self.imgZoom = 1
            self.image.zoomMode = 'fit'
            self.image.be_zoom_fit()
            self.sv.scroll_x = 0.5
            self.sv.scroll_y = 0.5
        # WINDOW MANIPULATIONS ----
        elif text == 'f':
            if self.fullscreen_mode == False:
                self.fullscreen_mode = True
                self.unmaxSize = Window.size
                self.winLeft = Window.left
                self.winTop = Window.top
                Window.top = 0
                Window.left = 0
                Window.borderless = True
                Window.maximize()
            else:
                self.fullscreen_mode = False
                Window.borderless = False
                Window.size = self.unmaxSize
                Window.top = self.winTop
                Window.left = self.winLeft

        return True
