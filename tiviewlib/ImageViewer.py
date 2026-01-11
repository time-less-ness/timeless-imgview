import os
import sys
import math
import random
import reusables
import shutil
import time
import subprocess
import numpy as np
from PIL import Image

from kivy.uix.button import Button
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.graphics import Color, Rectangle
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
        try:
            self.slideshowInterval = int(self.appConfig.get("UI", "slideshow-interval"))
        except:
            self.slideshowInterval = 20

        # metadata display timer
        self.metadataEvent = None

        # for scary actions multi-key commands
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
                                  size_hint=(1.0, 0.055),
                                  pos_hint={'x':0, 'y':.01},
                                  color = self.user_feedback_fg,
                                  background_color = self.user_feedback_bg
                                  )
        self.add_widget(self.info_button)
        Clock.schedule_once(self.user_feedback_clear, 1)

        # more massive messages can go here, for eg move-to locations
        self.giant_info_button = Button(text='lots of info would go here',
                                  font_name = "Times New Roman",
                                  font_size = self.user_feedback_font_size,
                                  size_hint=(1.0, 0.75),
                                  pos_hint={'x':0, 'y':.15},
                                  color = self.user_feedback_fg,
                                  background_color = self.user_feedback_bg
                                  )
        self.add_widget(self.giant_info_button)
        Clock.schedule_once(self.giant_info_clear, 1)

        # metadata display with two columns for proper alignment
        self.metadata_outer = BoxLayout(orientation='vertical',
                                       size_hint=(0.9, None),
                                       pos_hint={'center_x': 0.5, 'center_y': .5},
                                       padding=20,
                                       spacing=10)
        self.metadata_outer.bind(minimum_height=self.metadata_outer.setter('height'))
        # Add background to outer container
        with self.metadata_outer.canvas.before:
            Color(*self.user_feedback_bg)
            self.metadata_bg = Rectangle(pos=self.metadata_outer.pos, size=self.metadata_outer.size)
        self.metadata_outer.bind(pos=lambda *x: setattr(self.metadata_bg, 'pos', self.metadata_outer.pos),
                                size=lambda *x: setattr(self.metadata_bg, 'size', self.metadata_outer.size))

        # Header label
        self.metadata_header = Label(text='', font_name="Times New Roman",
                                    font_size=self.user_feedback_font_size,
                                    halign='center', valign='middle',
                                    size_hint_y=None,
                                    height=self.user_feedback_font_size * 1.5,
                                    color=self.user_feedback_fg)
        self.metadata_header.bind(size=lambda *x: setattr(self.metadata_header, 'text_size', self.metadata_header.size))
        self.metadata_outer.add_widget(self.metadata_header)

        # Container for the two-column data
        self.metadata_container = BoxLayout(orientation='horizontal', spacing=20, size_hint_y=None)
        self.metadata_keys = Label(text='', font_name="Times New Roman",
                                   font_size=self.user_feedback_font_size,
                                   halign='right', valign='middle',
                                   size_hint_y=None,
                                   color=self.user_feedback_fg)
        self.metadata_values = Label(text='', font_name="Times New Roman",
                                     font_size=self.user_feedback_font_size,
                                     halign='left', valign='middle',
                                     size_hint_y=None,
                                     color=self.user_feedback_fg)
        # Set text_size with fixed width but unrestricted height (None) to allow multiline
        self.metadata_keys.bind(width=lambda *x: setattr(self.metadata_keys, 'text_size', (self.metadata_keys.width, None)))
        self.metadata_values.bind(width=lambda *x: setattr(self.metadata_values, 'text_size', (self.metadata_values.width, None)))
        # Bind texture_size to height so labels grow with content
        self.metadata_keys.bind(texture_size=lambda *x: setattr(self.metadata_keys, 'height', self.metadata_keys.texture_size[1]))
        self.metadata_values.bind(texture_size=lambda *x: setattr(self.metadata_values, 'height', self.metadata_values.texture_size[1]))
        # Container height should be the max of the two labels
        self.metadata_keys.bind(height=lambda *x: setattr(self.metadata_container, 'height', max(self.metadata_keys.height, self.metadata_values.height)))
        self.metadata_values.bind(height=lambda *x: setattr(self.metadata_container, 'height', max(self.metadata_keys.height, self.metadata_values.height)))
        self.metadata_container.add_widget(self.metadata_keys)
        self.metadata_container.add_widget(self.metadata_values)
        self.metadata_outer.add_widget(self.metadata_container)

        self.add_widget(self.metadata_outer)
        self.metadata_outer.opacity = 0

    def _get_images(self):
        self.imageSet['orderedList'] = []

        # if no args passed in at all, use current directory as location for images
        if sys.argv[1:] == []:
            sys.argv[1:] = ['.']

        # might get a file or dir as argv
        toSort = False
        
        for inArg in sys.argv[1:]:
            if os.path.isdir(inArg):
                toSort = True
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

    def giant_info(self, text, clearTime=2):
        self.giant_info_button.text = text
        self.giant_info_button.color = self.user_feedback_fg
        self.giant_info_button.background_color = self.user_feedback_bg
        Clock.unschedule(self.giant_info_clear, all=True)
        Clock.schedule_once(self.giant_info_clear, clearTime)

    def giant_info_clear(self, dt):
        self.giant_info_button.text = ''
        self.giant_info_button.color=(0,0,0,0)
        self.giant_info_button.background_color=(0,0,0,0)

    def estimate_jpeg_quality(self, image_path):
        """Estimate JPEG quality from quantization tables"""
        try:
            img = Image.open(image_path)
            if img.format != 'JPEG':
                return "N/A (not JPEG)"
            # Access quantization tables (if available)
            qtables = img.quantization
            if qtables:
                # Simplified heuristic: Higher quality JPEGs have smaller quantization values
                avg_q = np.mean([np.mean(table) for table in qtables.values()])
                estimated_quality = max(0, min(100, int(100 - avg_q)))
                return str(estimated_quality)
            return "N/A (no qtables)"
        except Exception as e:
            Logger.error(f"Error estimating JPEG quality: {str(e)}")
            return "N/A (error)"

    def show_exif_metadata(self):
        """Run exiftool on current image and display filtered metadata"""
        img = self.imageSet['orderedList'][self.imageSet['setPos']]
        current_file = img['image']

        try:
            result = subprocess.run(
                f'exiftool "{current_file}" | egrep "Date|Size|Encoding|Megapixel|MIME|Comment"',
                shell=True, capture_output=True, text=True, timeout=5
            )

            if result.returncode == 0 and result.stdout.strip():
                lines = result.stdout.strip().split('\n')
                keys = []
                values = []

                # Add Directory as the first field
                absolute_path = os.path.abspath(current_file)
                directory_path = os.path.dirname(absolute_path)
                directory_name = os.path.basename(directory_path) if directory_path else '.'
                keys.append('Directory')
                values.append(directory_name)

                # Add Filename as the second field
                keys.append('Filename')
                values.append(os.path.basename(current_file))

                # Add Image Quality as the third field
                quality = self.estimate_jpeg_quality(current_file)
                keys.append('Image Quality')
                values.append(quality)

                for line in lines:
                    if ':' in line:
                        key, value = line.split(':', 1)
                        keys.append(key.strip())
                        values.append(value.strip())

                self.metadata_header.text = 'TimelessIV File Info, Press Key to Dismiss'
                self.metadata_keys.text = '\n'.join(keys)
                self.metadata_values.text = '\n'.join(values)
                self.metadata_outer.opacity = 1
                # Unschedule any existing timer before scheduling a new one
                if self.metadataEvent:
                    Clock.unschedule(self.metadataEvent)
                self.metadataEvent = Clock.schedule_once(lambda dt: setattr(self.metadata_outer, 'opacity', 0), 10)
            else:
                self.user_feedback("No metadata found or exiftool not available", 2)
        except subprocess.TimeoutExpired:
            self.user_feedback("Metadata lookup timed out", 2)
        except Exception as e:
            self.user_feedback(f"Error running exiftool: {str(e)}", 2)

    # move or delete image
    def move_image(self, destDir):
        img = self.imageSet['orderedList'][self.imageSet['setPos']]
        if os.path.exists(f"{destDir}/{img['image']}"):
            self.user_feedback(f" ! img={destDir + '/' + img['image']} exists, not moving.")
            Logger.critical(f"img={destDir}/{img['image']} exists! doing nothing.")
        else:
            if "Trash" in destDir:
                Logger.info(f"DELETE img={img['image']} to destDir={destDir}")
                self.user_feedback(f" x> TRASHED into {destDir}")
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
        self.image.next_image(self.image.imageSet['changeType'])

    def _on_keyboard_down(self, keyboard, keycode, text, modifiers):
        Logger.debug(f"keypress - keycode={keycode}, text={text}, modifiers={modifiers}")

        # keyboard events hide the cursor
        Window.show_cursor = False

        # any keypress clears the giant info display and metadata display
        if self.giant_info_button.text != '' or self.metadata_outer.opacity > 0:
            Clock.unschedule(self.giant_info_clear, all=True)
            self.giant_info_clear(0)
            if self.metadataEvent:
                Clock.unschedule(self.metadataEvent)
                self.metadataEvent = None
            self.metadata_outer.opacity = 0
            # only return early (prevent retriggering) if 'i' was pressed
            if text == 'i':
                return True

        # list of potential doublekeys
        doubleKeycodes = {'c': "Copy File", 'm': "Move File", 'q': "Quit Viewer"}

        # is this an initial press after some delay, or a quick successor?
        if (keycode[0] >= 97 and keycode[0] <= 122) \
        or (keycode[0] >= 48 and keycode[0] <= 57) \
        or (keycode[1] in '!@#$%^&*()_+-=\{\}[]:;<>?,./"\''):
            # many keyboard events cancel the slideshow
            if self.slideshowEvent and text != 's':
                Clock.unschedule(self.slideshowEvent, all=True)
                self.slideshowEvent = None

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

                # if moving/copying show destinations
                if keycode[1] in ("c","m"):
                    section_data = '\n'.join(f"{key}: {value}" for key, value in dict(self.appConfig["ReadOnlySettings"]).items())
                    self.giant_info(f"Copying/Moving Destinations:\n\n{section_data}", 10)
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
            if (self.previousKey in ['m', 'c']):
                # move the item somewhere
                try:
                    fileDest = self.appConfig.get("ReadOnlySettings", f"dest-{self.currKey}")
                    self.move_image(os.path.expanduser(fileDest)) if self.previousKey == 'm' else self.copy_image(os.path.expanduser(fileDest))
                    Clock.schedule_once(self.giant_info_clear, 0.1)
                except:
                    Logger.info(f"Location with no keybinding={self.currKey} in config file!")
                    self.user_feedback(f"!!! Config file does not have a destination for key {self.currKey}", 3)

            if (self.previousKey == 'q' and self.currKey == 'q'):
                App.get_running_app().stop()

            self.previousKey = ''
            self.currKey = ''
            self.lastScaryTimestamp = 0
            return True

        # DELETION ----
        if keycode[1] == 'delete':
            self.move_image(self.imageSet['del_dir'])
        if keycode[1] == 'backspace' and 'meta' in modifiers:
            self.move_image(self.imageSet['del_dir'])
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
            if self.slideshowEvent:
                if "shift" in modifiers:
                    self.slideshowInterval = min(math.ceil(self.slideshowInterval * 1.65), 120)
                else:
                    self.slideshowInterval = max(math.floor(self.slideshowInterval * 0.75), 1)

            self.appConfig.set("UI", "slideshow-interval", str(self.slideshowInterval))
            schedTiming = int(self.slideshowInterval)

            # if starting slideshow, pull next image, then schedule more on interval
            if not self.slideshowEvent:
                self.image.next_image(self.image.imageSet['changeType'])
                self.slideshowEvent = Clock.schedule_interval(self.slideshowNextImage, schedTiming)
                self.user_feedback(f"Slideshow started with interval {schedTiming} seconds. Shift-S and s change interval.", 2)
            else:
                Clock.unschedule(self.slideshowEvent, all=True)
                self.slideshowEvent = None
                self.slideshowEvent = Clock.schedule_interval(self.slideshowNextImage, schedTiming)
                self.user_feedback(f"New slideshow interval {schedTiming} seconds. Shift-S and s change interval.", 2)
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
        elif text == "[":
            self.image.prev_image('shuffled')
        elif text == "]":
            self.image.next_image('shuffled')
        elif text == ".":
            self.image.next_image('random')
        elif text == ',':
            self.image.prev_image('random')
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
        # METADATA INFO -----
        elif text == 'i':
            self.show_exif_metadata()
        # # This shit never works and it crashes if window is already fullscreen
        # elif text == 'f':
        #     if self.fullscreen_mode == False:
        #         self.fullscreen_mode = True
        #         self.unmaxSize = Window.size
        #         self.winLeft = Window.left
        #         self.winTop = Window.top
        #         Window.top = 0
        #         Window.left = 0
        #         Window.borderless = True
        #         Window.maximize()
        #     else:
        #         self.fullscreen_mode = False
        #         Window.borderless = False
        #         Window.size = self.unmaxSize
        #         Window.top = self.winTop
        #         Window.left = self.winLeft

        return True
