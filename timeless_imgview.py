#!/usr/bin/env python3.10

import subprocess
import reusables
import logging
import re
from kivy.app import App
from kivy.uix.widget import Widget
from kivy.core.window import Window
from kivy.uix.gridlayout import GridLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.utils import platform
from tiviewlib.ImageViewer import ImageViewer

log = reusables.get_logger('pyview', level=logging.INFO)

deviceRes = [3456, 2234]
resStr = None
if platform == 'linux':
    subProcessCmd = "xdpyinfo  | grep -oP 'dimensions:\s+\K\S+'"
    ps = subprocess.Popen(subProcessCmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    deviceRes = [int(r) for r in ps.communicate()[0].decode().split('x')]
elif platform == 'macosx':
    subProcessCmd = "system_profiler SPDisplaysDataType | grep Resolution | xargs"
    ps = subprocess.Popen(subProcessCmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    resStr = ps.communicate()[0].decode()
    resBits = re.findall(r'\d\d\d+', resStr)
    deviceRes = [int(resBits[0]), int(resBits[1])]

log.info(f"Got deviceRes={deviceRes}")

# TODO pull this from settings file to keep track of
# preference from run-to-run - also, if we pass in --size,
# don't override that
if "Retina" in resStr:
    Window.size = (int(deviceRes[0] / 2), deviceRes[1])
else:
    Window.size = (deviceRes[0], deviceRes[1])
Window.left = 0
Window.top = 0

# hide cursur unless move mouse
def on_motion(self, etype, me):
    # will receive all motion events.
    Window.show_cursor = True
Window.bind(on_motion=on_motion)

# doesn't do anything, but i guess for thumbnails
class AlbumView(GridLayout):

    def __int__(self, **kwargs):
        super().__init__(**kwargs)


class MainWindow(FloatLayout):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.image_view = ImageViewer(deviceRes=deviceRes, log=log)
        self.add_widget(self.image_view)

    def on_enter(self):
        Window.show_cursor = True


class TimelessImageView(App):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # TODO: make 1st image change titlebar - apparently hard as fuck
        self.title = "Timeless Image View"

    def build(self):
        return MainWindow()


if __name__ == '__main__':
    TimelessImageView().run()
