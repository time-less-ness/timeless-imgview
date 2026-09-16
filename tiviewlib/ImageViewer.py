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
from kivy.uix.widget import Widget
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
        # Kivy's effect_x/effect_y (used for touch/mouse-drag panning) recompute
        # their bounds on every viewport size change (zoom, new image, resize)
        # and silently force scroll_x/scroll_y toward an edge as a side effect -
        # sometimes landing exactly on 0 or 1, which looks broken but passes our
        # own out-of-bounds check, so spring_back_scroll() never catches it.
        # This app is keyboard-only, so disable the effects entirely and let
        # our own code be the only thing that ever sets scroll_x/scroll_y.
        self.sv = ScrollView(size=Window.size, effect_x=None, effect_y=None)
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
        self.springbackEvent = None

        # slideshow event
        self.slideshowEvent = None
        try:
            self.slideshowInterval = int(self.appConfig.get("UI", "slideshow-interval"))
        except:
            self.slideshowInterval = 20

        # metadata display timer
        self.metadataEvent = None

        # annotate (caption/tags) state
        self.annotate_mode = False
        self.annotate_text = ''
        self.last_annotation_text = ''

        # search state
        self.search_mode = False
        self.search_text = ''
        self.search_start_pos = 0
        self.search_event = None
        self.search_groups = []
        self.search_selected = 0

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

        # annotate (caption/tags) text entry box - same look as metadata_outer
        self.annotate_outer = BoxLayout(orientation='vertical',
                                       size_hint=(0.9, None),
                                       pos_hint={'center_x': 0.5, 'center_y': .5},
                                       padding=20,
                                       spacing=10)
        self.annotate_outer.bind(minimum_height=self.annotate_outer.setter('height'))
        with self.annotate_outer.canvas.before:
            Color(*self.user_feedback_bg)
            self.annotate_bg = Rectangle(pos=self.annotate_outer.pos, size=self.annotate_outer.size)
        self.annotate_outer.bind(pos=lambda *x: setattr(self.annotate_bg, 'pos', self.annotate_outer.pos),
                                size=lambda *x: setattr(self.annotate_bg, 'size', self.annotate_outer.size))

        self.annotate_header = Label(text='', font_name="Times New Roman",
                                    font_size=self.user_feedback_font_size,
                                    halign='center', valign='middle',
                                    size_hint_y=None,
                                    height=self.user_feedback_font_size * 1.5,
                                    color=self.user_feedback_fg)
        self.annotate_header.bind(size=lambda *x: setattr(self.annotate_header, 'text_size', self.annotate_header.size))
        self.annotate_outer.add_widget(self.annotate_header)

        self.annotate_input = Label(text='', font_name="Times New Roman",
                                   font_size=self.user_feedback_font_size,
                                   halign='left', valign='middle',
                                   size_hint_y=None,
                                   color=self.user_feedback_fg)
        self.annotate_input.bind(width=lambda *x: setattr(self.annotate_input, 'text_size', (self.annotate_input.width, None)))
        self.annotate_input.bind(texture_size=lambda *x: setattr(self.annotate_input, 'height', self.annotate_input.texture_size[1]))
        self.annotate_outer.add_widget(self.annotate_input)

        self.add_widget(self.annotate_outer)
        self.annotate_outer.opacity = 0

        # search-for-images: two separate boxes, each ~90% of the window
        # tall - left is instructions + the typed text, right is a single
        # column of up to 20 results
        search_row_h = self.user_feedback_font_size * 1.4

        self.search_left_outer = BoxLayout(orientation='vertical',
                                          size_hint=(0.2, 0.9),
                                          pos_hint={'x': 0.03, 'center_y': 0.5},
                                          padding=20,
                                          spacing=10)
        with self.search_left_outer.canvas.before:
            Color(*self.user_feedback_bg)
            self.search_left_bg = Rectangle(pos=self.search_left_outer.pos, size=self.search_left_outer.size)
        self.search_left_outer.bind(pos=lambda *x: setattr(self.search_left_bg, 'pos', self.search_left_outer.pos),
                                   size=lambda *x: setattr(self.search_left_bg, 'size', self.search_left_outer.size))

        self.search_header = Label(text='', font_name="Times New Roman",
                                  font_size=self.user_feedback_font_size,
                                  halign='left', valign='top',
                                  size_hint_y=None,
                                  height=search_row_h * 2,
                                  color=self.user_feedback_fg)
        self.search_header.bind(size=lambda *x: setattr(self.search_header, 'text_size', self.search_header.size))
        self.search_left_outer.add_widget(self.search_header)

        self.search_input = Label(text='', font_name="Times New Roman",
                                 font_size=self.user_feedback_font_size,
                                 halign='left', valign='top',
                                 size_hint_y=None,
                                 height=search_row_h,
                                 color=self.user_feedback_fg)
        self.search_input.bind(size=lambda *x: setattr(self.search_input, 'text_size', self.search_input.size))
        self.search_left_outer.add_widget(self.search_input)

        # flexible spacer - without it BoxLayout anchors the fixed-height
        # header/input to the BOTTOM of this much-taller-than-content box
        self.search_left_outer.add_widget(Widget())

        self.add_widget(self.search_left_outer)
        self.search_left_outer.opacity = 0

        # Search Right Box
        self.search_right_outer = BoxLayout(orientation='vertical',
                                           size_hint=(0.73, 0.9),
                                           pos_hint={'right': 0.97, 'center_y': 0.5},
                                           padding=20,
                                           spacing=10)
        with self.search_right_outer.canvas.before:
            Color(*self.user_feedback_bg)
            self.search_right_bg = Rectangle(pos=self.search_right_outer.pos, size=self.search_right_outer.size)
        self.search_right_outer.bind(pos=lambda *x: setattr(self.search_right_bg, 'pos', self.search_right_outer.pos),
                                    size=lambda *x: setattr(self.search_right_bg, 'size', self.search_right_outer.size))

        self.search_results_col = Label(text='', font_name="Times New Roman",
                                       font_size=self.user_feedback_font_size,
                                       halign='left', valign='top',
                                       markup=True,
                                       color=self.user_feedback_fg)
        self.search_results_col.bind(size=lambda *x: setattr(self.search_results_col, 'text_size', self.search_results_col.size))
        self.search_right_outer.add_widget(self.search_results_col)

        self.add_widget(self.search_right_outer)
        self.search_right_outer.opacity = 0

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
                        # Comment for example is often too long which causees keys and values to not line up
                        # 120 characters feels about right to prevent this problem. longterm fix: make keys
                        # and values be some group so long values wrapping don't cause mis-alignment
                        values.append(value.strip()[0:120])

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

    def read_exif_comment(self, filepath):
        """Read current EXIF UserComment ('Comment') for annotate prefill"""
        try:
            result = subprocess.run(
                ['exiftool', '-UserComment', '-s3', filepath],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception as e:
            Logger.error(f"Error reading UserComment: {str(e)}")
        return ''

    def write_exif_comment(self, filepath, text):
        """Write text into EXIF UserComment ('Comment' / 'Caption or Tags')"""
        try:
            result = subprocess.run(
                ['exiftool', '-overwrite_original', f'-UserComment={text}', filepath],
                capture_output=True, text=True, timeout=5
            )
            return result.returncode == 0
        except Exception as e:
            Logger.error(f"Error writing UserComment: {str(e)}")
            return False

    def start_annotate(self, prefill_from_exif):
        """Open the Caption or Tags entry box, prefilled from EXIF or last-typed text"""
        img = self.imageSet['orderedList'][self.imageSet['setPos']]
        current_file = img['image']
        if prefill_from_exif:
            self.annotate_text = self.read_exif_comment(current_file)
        else:
            self.annotate_text = self.last_annotation_text
        self.annotate_mode = True
        self.annotate_header.text = 'Caption or Tags  (Enter=save, Esc=cancel)'
        self.annotate_input.text = self.annotate_text + '|'
        self.annotate_outer.opacity = 1

        # hide other overlays, same as the any-keypress metadata-dismiss logic
        Clock.unschedule(self.giant_info_clear, all=True)
        self.giant_info_clear(0)
        if self.metadataEvent:
            Clock.unschedule(self.metadataEvent)
            self.metadataEvent = None
        self.metadata_outer.opacity = 0

    def commit_annotate(self):
        """Save the typed Caption/Tags text into EXIF and close the box"""
        img = self.imageSet['orderedList'][self.imageSet['setPos']]
        current_file = img['image']
        ok = self.write_exif_comment(current_file, self.annotate_text)
        self.last_annotation_text = self.annotate_text
        self.annotate_mode = False
        self.annotate_outer.opacity = 0
        if ok:
            self.user_feedback('Caption/Tags saved', 2)
        else:
            self.user_feedback('Failed to save Caption/Tags (exiftool error)', 3)

    def cancel_annotate(self):
        """Close the box without writing EXIF, remembering what was typed"""
        self.last_annotation_text = self.annotate_text
        self.annotate_mode = False
        self.annotate_outer.opacity = 0

    def start_search(self):
        """Open the Search for Images box"""
        self.search_start_pos = self.imageSet['setPos']
        self.search_text = ''
        self.search_groups = []
        self.search_selected = 0
        self.search_mode = True
        self.search_header.text = 'Search for Images\n(Enter=go, Esc=cancel, up/down=select)'
        self.search_input.text = '|'
        self.update_search_results()
        self.search_left_outer.opacity = 1
        self.search_right_outer.opacity = 1
        self.search_file_truncate = 80

        # hide other overlays, same as the any-keypress metadata-dismiss logic
        Clock.unschedule(self.giant_info_clear, all=True)
        self.giant_info_clear(0)
        if self.metadataEvent:
            Clock.unschedule(self.metadataEvent)
            self.metadataEvent = None
        self.metadata_outer.opacity = 0

    def _schedule_search(self):
        if self.search_event:
            Clock.unschedule(self.search_event)
        self.search_event = Clock.schedule_once(self.run_search, 1)

    def compute_search_groups(self, needle):
        """Matching images, collapsed to the first match in each directory
        (a 'group' - eg. all matches under "objects/" vs under "happyPics/"),
        capped at 20 groups. Grouping by directory rather than by list-index
        adjacency matters because a directory can contain nothing but
        matches, so two different directories' matches can otherwise land on
        consecutive indices and wrongly merge into one group"""
        groups = []
        last_dir = None
        for pos, img in enumerate(self.imageSet['orderedList']):
            path = img['image']
            if needle in os.path.basename(path).lower():
                this_dir = os.path.dirname(path)
                if groups and this_dir == last_dir:
                    groups[-1].append(pos)
                else:
                    groups.append([pos])
                last_dir = this_dir
        return [group[0] for group in groups[:20]]

    def update_search_results(self):
        """Render the up-to-20 group results as a single column, highlighting
        whichever one is currently selected/previewed"""
        lines = [''] * 20
        for i, pos in enumerate(self.search_groups):
            path = self.imageSet['orderedList'][pos]['image']
            filename = os.path.basename(path)
            parent = os.path.basename(os.path.dirname(path))
            name = f'{parent}/{filename}' if parent else filename
            # truncate filenames to N characters
            name = name[:self.search_file_truncate]
            lines[i] = f'[b]> {name}[/b]' if i == self.search_selected else f'  {name}'
        self.search_results_col.text = '\n'.join(lines)

    def run_search(self, dt):
        """Debounced: (re)group the matches and preview the first group"""
        self.search_event = None
        if not self.search_text:
            self.search_groups = []
            self.search_selected = 0
            self.update_search_results()
            self.change_to_image(self.search_start_pos)
            return
        needle = self.search_text.lower()
        self.search_groups = self.compute_search_groups(needle)
        self.search_selected = 0
        self.update_search_results()
        if self.search_groups:
            self.change_to_image(self.search_groups[0])
        else:
            self.user_feedback('No match found', 2)

    def search_nav(self, direction):
        """Move the selection up/down the single-column results list and
        preview whatever is now selected"""
        if not self.search_groups or direction not in ('up', 'down'):
            return
        if direction == 'up':
            new_selected = max(0, self.search_selected - 1)
        else:
            new_selected = min(len(self.search_groups) - 1, self.search_selected + 1)
        if new_selected == self.search_selected:
            return
        self.search_selected = new_selected
        self.update_search_results()
        self.change_to_image(self.search_groups[self.search_selected])

    def commit_search(self):
        """Keep the currently previewed image and close the search box"""
        if self.search_event:
            Clock.unschedule(self.search_event)
            self.search_event = None
        self.search_mode = False
        self.search_left_outer.opacity = 0
        self.search_right_outer.opacity = 0

    def cancel_search(self):
        """Close the search box and return to the image viewed before search began"""
        if self.search_event:
            Clock.unschedule(self.search_event)
            self.search_event = None
        self.search_mode = False
        self.search_left_outer.opacity = 0
        self.search_right_outer.opacity = 0
        self.change_to_image(self.search_start_pos)

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
        self.image.load_image_with_exif()

    def _keyboard_closed(self):
        self._keyboard.unbind(on_key_down=self._on_keyboard_down)
        self._keyboard = None

    def calc_scroll_amt(self, direction, modifiers):
        # a fresh key press takes over from any in-progress springback
        if self.springbackEvent:
            Clock.unschedule(self.springbackEvent)
            self.springbackEvent = None

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

        # now record which way are we scrolling - keep any other held
        # direction active too, so eg down+right can scroll diagonally
        self.scrollingDir[direction] = True

        return self.sv.convert_distance_to_scroll(tX, tX)

    def _on_keyboard_up(self, keyboard, keycode):
        dirByKey = {'up': 0, 'down': 1, 'left': 2, 'right': 3}
        if keycode[1] in dirByKey:
            self.scrollingDir[dirByKey[keycode[1]]] = False

        # only stop once every arrow key has been released
        if any(self.scrollingDir):
            return

        # unschedule the keep-on-scrolling f()
        Clock.unschedule(self.scrollEvent, all=True)
        self.scrollEvent = None
        self.scrollPix = self.progressiveReset

        # if the key let us drift past the edge, ease back onto the canvas
        if self.springbackEvent is None and (
                self.sv.scroll_x < 0 or self.sv.scroll_x > 1
                or self.sv.scroll_y < 0 or self.sv.scroll_y > 1):
            self.springbackEvent = Clock.schedule_interval(self.spring_back_scroll, self.scrollScheduleInterval)

    def keep_on_scrollin(self, dx):
        # scroll_x/scroll_y are only meaningful in [0, 1], but let a held key
        # push slightly past that so holding it still gives live feedback even
        # when the image has no room to move. spring_back_scroll() eases it
        # back once the key is released - without this clamp the value can
        # drift arbitrarily far, and a later zoom would jump the image way
        # off-screen and take a long time to creep back into view.
        # these are independent ifs (not elif) so eg down+right can both
        # apply within the same tick and the image can pan diagonally.
        if self.scrollingDir[0] == True:
            self.sv.scroll_y = min(1.5, self.sv.scroll_y + self.scrollAmount[1])
        if self.scrollingDir[1] == True:
            self.sv.scroll_y = max(-0.5, self.sv.scroll_y - self.scrollAmount[1])
        if self.scrollingDir[2] == True:
            self.sv.scroll_x = max(-0.5, self.sv.scroll_x - self.scrollAmount[0])
        if self.scrollingDir[3] == True:
            self.sv.scroll_x = min(1.5, self.sv.scroll_x + self.scrollAmount[0])

    def _spring_axis_step(self, axis):
        """Ease scroll_x/scroll_y back to [0, 1]. If the image is entirely
        off-screen on this axis, jump straight to half-visible first - easing
        by 50%/tick would otherwise stay invisible for a long time before any
        pixel of the image re-enters the viewport."""
        current = getattr(self.sv, f'scroll_{axis}')
        target = min(1, max(0, current))
        if current == target:
            return True

        if axis == 'x':
            view_span = Window.size[0]
            near_edge, far_edge = self.image.x, self.image.x + self.image.width
            scroll_span = self.image.width - view_span
        else:
            view_span = Window.size[1]
            near_edge, far_edge = self.image.y, self.image.y + self.image.height
            scroll_span = self.image.height - view_span

        if scroll_span > 0 and (far_edge < 0 or near_edge > view_span):
            edge = far_edge if far_edge < 0 else near_edge
            pixel_delta = (view_span / 2) - edge
            new_value = current - (pixel_delta / scroll_span)
        else:
            new_value = current + (target - current) * 0.5
            if abs(new_value - target) < 0.002:
                new_value = target

        setattr(self.sv, f'scroll_{axis}', new_value)
        return new_value == target

    def spring_back_scroll(self, dt):
        x_done = self._spring_axis_step('x')
        y_done = self._spring_axis_step('y')
        if x_done and y_done:
            Clock.unschedule(self.springbackEvent)
            self.springbackEvent = None

    def slideshowNextImage(self, dx):
        self.image.next_image(self.image.imageSet['changeType'])

    def _on_keyboard_down(self, keyboard, keycode, text, modifiers):
        Logger.debug(f"keypress - keycode={keycode}, text={text}, modifiers={modifiers}")

        # keyboard events hide the cursor
        Window.show_cursor = False

        # ANNOTATE TEXT ENTRY ---- swallow all keys while composing a caption
        if self.annotate_mode:
            # bare modifier keys still fire on_key_down (and can carry junk in
            # `text` on some platforms) - never treat them as typed characters
            modifierKeycodes = ('shift', 'rshift', 'ctrl', 'lctrl', 'rctrl',
                                 'alt', 'alt-gr', 'meta', 'lmeta', 'rmeta',
                                 'super', 'capslock', 'numlock', 'screenlock',
                                 'compose', 'pause')
            if keycode[1] == 'escape':
                self.cancel_annotate()
            elif keycode[1] in ('enter', 'numpadenter'):
                self.commit_annotate()
            elif keycode[1] == 'backspace':
                self.annotate_text = self.annotate_text[:-1]
                self.annotate_input.text = self.annotate_text + '|'
            elif text and text.isprintable() and keycode[1] not in modifierKeycodes:
                # letters arrive lowercase in `text` regardless of shift state
                ch = text.upper() if ('shift' in modifiers and text.isalpha()) else text
                self.annotate_text += ch
                self.annotate_input.text = self.annotate_text + '|'
            return True

        # SEARCH TEXT ENTRY ---- swallow all keys while typing a search query
        if self.search_mode:
            modifierKeycodes = ('shift', 'rshift', 'ctrl', 'lctrl', 'rctrl',
                                 'alt', 'alt-gr', 'meta', 'lmeta', 'rmeta',
                                 'super', 'capslock', 'numlock', 'screenlock',
                                 'compose', 'pause')
            if keycode[1] == 'escape':
                self.cancel_search()
            elif keycode[1] in ('enter', 'numpadenter'):
                self.commit_search()
            elif keycode[1] in ('up', 'down', 'left', 'right'):
                self.search_nav(keycode[1])
            elif keycode[1] == 'backspace':
                self.search_text = self.search_text[:-1]
                self.search_input.text = self.search_text + '|'
                self._schedule_search()
            elif text and text.isprintable() and keycode[1] not in modifierKeycodes:
                ch = text.upper() if ('shift' in modifiers and text.isalpha()) else text
                self.search_text += ch
                self.search_input.text = self.search_text + '|'
                self._schedule_search()
            return True

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
        or (keycode[1] in '!@#$%^&*()_+-=[]:;<>?,./"\''):
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
        # ANNOTATE -----
        elif keycode[1] == 'a':
            # `text` stays lowercase 'a' even with shift held, so use modifiers
            self.start_annotate(prefill_from_exif=('shift' not in modifiers))
        # SEARCH -----
        elif text == '/':
            self.start_search()
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
