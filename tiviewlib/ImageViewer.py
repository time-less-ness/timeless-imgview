import os
import sys
import math
import random
import reusables
import shutil
import time;

from kivy.uix.floatlayout import FloatLayout
from kivy.uix.scrollview import ScrollView
from kivy.core.window import Window
from kivy.clock import Clock
from kivy.loader import Loader
from kivy.app import App
from tiviewlib.MainImage import MainImage
#from tiviewlib.kivy_hover import MouseOver

class ImageViewer(FloatLayout):

    def __init__(self,
            delete_dir=f"{os.environ['HOME']}/.Trash",
            deviceRes=None,
            log=None,
            **kwargs):
        super().__init__(**kwargs)
        self.log = log

        # setup fullscreen status and device resolution
        if deviceRes != None:
            self.deviceRes = deviceRes
        else:
            self.deviceRes = [800, 600]
        self.fullscreen_mode = False
        # zoom of window itself
        self.windowZoom = 1
        self.imgZoom = 1

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
        self.image = MainImage(imageSet=self.imageSet, log=self.log)
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
        # such as Q/Esc to quit, or Del to delete
        self.lastQuitPressTimestamp = 0
        self.lastDelPressTimestamp = 0

        # now that image loaded, also load cached next
        try:
            self.imageSet['cacheImage'] = Loader.image(self.imageSet['orderedList'][self.imageSet['setPos'] + 1]['image'])
            self.imageSet['cacheImage'].bind(on_load=self.image.cacheImage_loaded)
        except:
            # i guess we only had 1 image?
            pass

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
                    self.log.error(f"Couldn't collect images from {dirName}")
                self.log.debug(f"Collected files from {dirName} - total so far: {len(self.imageSet['orderedList'])}")
            elif os.path.isfile(inArg):
                toSort = False
                data = {'image': inArg, 'created': 0}
                self.imageSet['orderedList'].append(data)
            else:
                self.log.error(f"Input {inArg} is neither file nor directory. Ignoring.")

        # they come in some random order, so put them in filename order
        if toSort:
            self.imageSet['orderedList'].sort(key=lambda x: x['image'])

    def on_size(self, obj, size):
        """Make sure all children sizes adjust properly"""
        #self.log.debug(f"Resizing image itself to {size[0]}x{size[1]}, obj={obj}")
        self.image.size_hint_x = None
        self.image.size_hint_y = None
        self.image.width = size[0]
        self.image.height = size[1]
        self.image.xpos = 0
        self.image.ypos = 0

        self.sv.width = size[0]
        self.sv.height = size[1]

    def delete_image(self):
        img = self.imageSet['orderedList'][self.imageSet['setPos']]
        self.imageSet['orderedList'].remove(img)
        del_name = img['image']
        shutil.move(img['image'], self.imageSet['del_dir'])
        self.change_to_image(self.imageSet['setPos'])

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
        # all keyboard events cancel the slideshow
        if self.slideshowEvent:
            Clock.unschedule(self.slideshowEvent, all=True)
            self.slideshowEvent = None

        # keyboard events hide the cursor
        Window.show_cursor = False

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
        elif keycode[1] == 's':
            # pull one random image, then schedule more on interval
            self.image.next_image('random')
            self.slideshowEvent = Clock.schedule_interval(self.slideshowNextImage, self.slideshowInterval)
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
            self.log.debug(f"Rotate -90")
            self.image.rotation = -90
        elif text == "]":
            self.log.debug(f"Rotate +90")
            self.image.rotation = 90
        ## # SORTING -----
        ## elif text in ('1', '!') and 'shift' in modifiers:
        ##     # view images in alpha order
        ##     tmpImg = self.imageSet['orderedList'][self.imageSet['setPos']]
        ##     self._get_images()
        ##     self.imageSet['orderedList'].sort(key=lambda x: x['image'])
        ##     self.imageSet['setPos'] = self.imageSet['orderedList'].index(tmpImg)
        ##     self.image.gen_image()
        ##     self.image.reload()
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
        # IMAGE COPY/MOVE/DELETE -----
        elif keycode[1] == 'delete':
            currTs = time.time()
            if currTs - self.lastDelPressTimestamp < 1:
                self.log.debug(f"Delete image")
                self.delete_image()
            else:
                self.lastDelPressTimestamp = currTs
        elif text == 'c' and 'control' in modifiers:
            # TODO
            self.log.debug(f"Copy image")
        elif text == 'x' and 'control' in modifiers:
            # TODO
            self.log.debug(f"Move image")
        # WINDOW MANIPULATIONS ----
        elif text == 'f':
            if self.fullscreen_mode == False:
                self.fullscreen_mode = True
                Window.borderless = True
                Window.size = (self.deviceRes[0], self.deviceRes[1])
                self.size = Window.size
            else:
                self.fullscreen_mode = False
                Window.borderless = False
                Window.fullscreen = False
                Window.size = (int(self.deviceRes[0] * self.windowZoom), int(self.deviceRes[1] * self.windowZoom))
                self.size = Window.size
        # QUIT ----
        elif text == 'Q' or text == 'q':
            currTs = time.time()
            if currTs - self.lastQuitPressTimestamp < 1:
                # shut it down
                App.get_running_app().stop()
            else:
                self.lastQuitPressTimestamp = currTs
        return True
