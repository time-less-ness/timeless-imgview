import os
import sys
import math
import random
import shutil

import numpy as np
import reusables
from PIL import Image as PILImage, ImageOps
from kivy.uix.image import Image
from kivy.core.window import Window
from kivy.loader import Loader
from kivy.logger import Logger
from kivy.graphics.texture import Texture

class MainImage(Image):

    def __init__(self,
            imageSet=None,
            log=None,
            **kwargs):
        self.imageSet = imageSet
        self.zoomMode = 'fit'
        self._texture_cache = {}
        super().__init__(**kwargs)
        self.load_image_with_exif()

        # can be bigger than bounding widget
        self.allow_stretch = True

        # enable texture interpolation for better quality when downscaling
        self.bind(texture=self._on_texture_update)

    def _on_texture_update(self, instance, texture):
        """Enable linear/bicubic interpolation for better quality when downscaling"""
        if texture:
            texture.mag_filter = 'linear'
            texture.min_filter = 'linear'

    def load_with_exif_transpose(self, filepath):
        """
        Load image using PIL, apply EXIF orientation, and return Kivy texture.
        Falls back to None if EXIF processing fails.
        """
        if filepath in self._texture_cache:
            return self._texture_cache[filepath]

        try:
            pil_img = PILImage.open(filepath)
            transposed = ImageOps.exif_transpose(pil_img)

            if transposed.mode != 'RGB':
                if transposed.mode == 'RGBA':
                    background = PILImage.new('RGB', transposed.size, (255, 255, 255))
                    background.paste(transposed, mask=transposed.split()[3])
                    transposed = background
                else:
                    transposed = transposed.convert('RGB')

            img_array = np.array(transposed)
            texture = Texture.create(
                size=(transposed.size[0], transposed.size[1]),
                colorfmt='rgb'
            )
            texture.blit_buffer(img_array.tobytes(), colorfmt='rgb', bufferfmt='ubyte')
            texture.flip_vertical()

            self._texture_cache[filepath] = texture
            return texture

        except Exception as e:
            Logger.warning(f"EXIF transpose failed for {filepath}: {e}")
            return None

    def load_image_with_exif(self):
        """Load current image with EXIF orientation support."""
        filepath = self.gen_image()
        texture = self.load_with_exif_transpose(filepath)

        if texture:
            self.texture = texture
            self._source = filepath
        else:
            self.source = filepath

    def set_window_pos(self):
        # make sure image doesn't go wonky if it's smaller than
        # the display window - otherwise try to centerish it
        if self.size[0] < Window.size[0]:
            self.size[0] = Window.size[0]
        else:
            deltaX = Window.size[0] - self.size[0]
            self.x = int(deltaX / 2)

        if self.size[1] < Window.size[1]:
            self.size[1] = Window.size[1]
        else:
            deltaY = Window.size[1] - self.size[1]
            self.y = int(deltaY / 2)

    def be_zoom_1_to_1(self):
        self.size = self.texture_size
        self.set_window_pos()

    def be_zoom_fit(self):
        self.size = Window.size
        self.set_window_pos()

    def flip_image_changeType(self, changeType):
        if changeType != self.imageSet['changeType']:
            Logger.debug(f"Flipping from {self.imageSet['changeType']} to {changeType}")
            tmpImg = self.imageSet['orderedList'][self.imageSet['setPos']]
            if changeType == 'ordered':
                Logger.debug("Ordering!")
                self.imageSet['orderedList'].sort(key=lambda x: x['image'])
            elif changeType == 'shuffled':
                Logger.debug("Shuffling!")
                # only need to order them if not already ordered
                if self.imageSet['changeType'] != 'ordered':
                    self.imageSet['orderedList'].sort(key=lambda x: x['image'])
                # shuffling, not totally randomised
                for i in range(len(self.imageSet['orderedList'])):
                    if i < len(self.imageSet['orderedList']) - 20:
                        swapIndex = random.randint(i+1, i+20)
                    else:
                        swapIndex = random.randint(0, len(self.imageSet['orderedList']) - i)
                    self.imageSet['orderedList'][i], self.imageSet['orderedList'][swapIndex] = self.imageSet['orderedList'][swapIndex], self.imageSet['orderedList'][i]
            else:
                Logger.debug("Randoming!")
                self.imageSet['orderedList'].sort(key=lambda x: random.randint(0,999999999))

            self.imageSet['changeType'] = changeType
            self.imageSet['setPos'] = self.imageSet['orderedList'].index(tmpImg)
            self.load_image_with_exif()

    def next_image(self, changeType, howMany=None):
        self.flip_image_changeType(changeType)

        if howMany == None:
            howMany = 1
        self.imageSet['setPos'] += howMany

        if self.imageSet['setPos'] >= len(self.imageSet['orderedList']):
            self.imageSet['setPos'] = 0

        if self.imageSet['cacheImage'].filename == self.imageSet['orderedList'][self.imageSet['setPos']]['image']:
            Window.set_title(f"TimelessIV - {self.imageSet['cacheImage'].filename}")
            self.texture = self.imageSet['cacheImage'].texture
            self._source = self.imageSet['cacheImage'].filename
        else:
            self.load_image_with_exif()

        if self.zoomMode == 'pan':
            pass
        elif self.zoomMode == 'fit':
            self.be_zoom_fit()

        try:
            cache_path = self.imageSet['orderedList'][self.imageSet['setPos'] + 1]['image']
            self.imageSet['cacheImage'] = self._load_cached_image_with_exif(cache_path)
            self.imageSet['cacheImage'].bind(on_load=self.cacheImage_loaded)
        except:
            pass

        self.pos = [0,0]

    def _load_cached_image_with_exif(self, filepath):
        """Load image for caching with EXIF transpose support."""
        texture = self.load_with_exif_transpose(filepath)
        if texture:
            cache_img = Loader.image(filepath)
            cache_img.texture = texture
            cache_img.filename = filepath
            return cache_img
        else:
            return Loader.image(filepath)

    def prev_image(self, changeType, howMany=None):
        self.flip_image_changeType(changeType)
        self.imageSet['cachedDirection'] = '-'

        if howMany == None:
            howMany = 1
        self.imageSet['setPos'] -= howMany

        if self.imageSet['setPos'] < 0:
            self.imageSet['setPos'] = len(self.imageSet['orderedList']) - 1

        if self.imageSet['cacheImage'].filename == self.imageSet['orderedList'][self.imageSet['setPos']]['image']:
            Window.set_title(f"TimelessIV - {self.imageSet['cacheImage'].filename}")
            self.texture = self.imageSet['cacheImage'].texture
            self._source = self.imageSet['cacheImage'].filename
        else:
            self.load_image_with_exif()

        try:
            cache_path = self.imageSet['orderedList'][self.imageSet['setPos'] - 1]['image']
            self.imageSet['cacheImage'] = self._load_cached_image_with_exif(cache_path)
            self.imageSet['cacheImage'].bind(on_load=self.cacheImage_loaded)
        except:
            pass

        self.pos = [0,0]

    def cacheImage_loaded(self, cacheImage):
        Logger.debug(f"cacheImage_loaded() called with {cacheImage.filename}")
        if cacheImage.texture:
            if self.imageSet['cacheImage'].filename == self.imageSet['orderedList'][self.imageSet['setPos']]['image']:
                try:
                    self.imageSet['cacheImage'].texture = cacheImage.texture
                except:
                    pass

    def gen_image(self):
        # sometimes in cases of deleting/reordering we can get here with an
        # invalid setPos. make it the 1st image in that case
        if self.imageSet['setPos'] < 0 or self.imageSet['setPos'] > len(self.imageSet['orderedList']) - 1:
            self.imageSet['setPos'] = 0

        #Logger.debug(f"Grabbing from {self.imageSet['orderedList'][self.imageSet['setPos']]}")
        tmpImg = self.imageSet['orderedList'][self.imageSet['setPos']]['image']
        Window.set_title(f"TimelessIV - {tmpImg}")
        return tmpImg

