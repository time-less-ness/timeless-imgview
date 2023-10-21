#!/usr/bin/env python3.11

import configparser
import logging
import os
import reusables
import re
import subprocess
from kivy.app import App
from kivy.uix.widget import Widget
from kivy.core.window import Window
from kivy.uix.gridlayout import GridLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.utils import platform
from tiviewlib.ImageViewer import ImageViewer

#log = reusables.get_logger('pyview', level=logging.DEBUG)
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

log.debug(f"Got deviceRes={deviceRes}")

# pull this from settings file to keep track of preference from run-to-run
# TODO: if we pass in --size, don't override that
config_filename = os.path.expanduser('~/.tivewrc')
config = configparser.ConfigParser()
if config.read(config_filename) == []:
    f = open(config_filename, "w")
    f.write("[ReadOnlySettings]\n")
    f.write("NoSuchSettingYet = True\n")
    f.write("\n")
    f.write("[LastRun]\n")
    f.write("lastgeom = 1920x1080+0,0\n")
    f.close()
config.read(config_filename)
log.debug(f"Got config={config}")

# read size from directory
try:
    window_geom = config.get('LastRun', f'{os.getcwd()}--geom')
except:
    window_geom = config.get('LastRun', f'lastgeom')

# try parsing stuff, but assume it'll get f'd somehow
try:
    [wsz,wpos] = window_geom.split("+")
    Window.size = [int(n) for n in wsz.split('x')]
    Window.left = int(wpos.split(',')[0])
    Window.top = int(wpos.split(',')[1])
except:
    Window.size = [1920, 1080]
    Window.left = 0
    Window.top = 0

# hide cursur unless move mouse
def on_motion(self, etype, me):
    # will receive all motion events.
    Window.show_cursor = True
Window.bind(on_motion=on_motion)

# doesn't do anything, but i guess for thumbnails
class AlbumView(GridLayout):
    """
    One day this will be for thumbnails
    """
    def __int__(self, **kwargs):
        super().__init__(**kwargs)


class MainWindow(FloatLayout):
    """
    This makes the window
    """
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.image_view = ImageViewer(deviceRes=deviceRes, log=log)
        self.add_widget(self.image_view)

    def on_enter(self):
        Window.show_cursor = True


class TimelessImageView(App):
    """
    Initialise and make the MainWindow
    """
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # TODO: make 1st image change titlebar - apparently hard as fuck
        self.title = "Timeless Image View"

    def build(self):
        return MainWindow()


if __name__ == '__main__':
    TimelessImageView().run()
    log.info(f'Writing Configuration into {config_filename}!')
    output_geom = f"{str(Window.size[0])}x{str(Window.size[1])}+{str(Window.left)},{str(Window.top)}"
    config.set('LastRun', f'{os.getcwd()}--geom', output_geom)
    config.set('LastRun', f'lastgeom', output_geom)
    with open(config_filename, 'w') as configfile:
        config.write(configfile)

