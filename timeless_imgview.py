#!/usr/bin/env python3.11

import configparser
#import logging
import os
import reusables
import re
import subprocess
from kivy.app import App
from kivy.logger import Logger, LOG_LEVELS
from kivy.core.window import Window
from kivy.uix.widget import Widget
from kivy.uix.gridlayout import GridLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.utils import platform
from tiviewlib.ImageViewer import ImageViewer

#Logger.setLevel(LOG_LEVELS["debug"])
Logger.setLevel(LOG_LEVELS["info"])

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

Logger.debug(f"Got deviceRes={deviceRes}")

# pull this from settings file to keep track of preference from run-to-run
# TODO: if we pass in --size, don't override that
config_filename = os.path.expanduser('~/.tiviewrc')
config = configparser.ConfigParser()
if config.read(config_filename) == []:
    f = open(config_filename, "w")
    f.write("[ReadOnlySettings]\n")
    f.write("dest-a = ~/AI-Images\n")
    f.write("dest-d = ~/AI-Documents\n")
    f.write("dest-f = ~/Family-Photos\n")
    f.write("dest-w = ~/Work-Photos\n")
    f.write("dest-t = /tmp\n")
    f.write("\n")
    f.write("[UI]\n")
    f.write("feedback-fg = 0.85,0.85,0.85,0.8\n")
    f.write("feedback-bg = 0.05,0.05,0.05,0.7\n")
    f.write("feedback-fontsize = 32\n")
    f.write("\n")
    f.write("[LastRun]\n")
    f.write("lastgeom = 1920x1080+0,0\n")
    f.close()
config.read(config_filename)
Logger.debug(f"Got config={config}")

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
        self.image_view = ImageViewer(appConfig=config, deviceRes=deviceRes)
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
    Logger.info(f'Writing Configuration into {config_filename}!')
    if "Retina" in resStr:
        # iMac27in Retina and mbp16in
        # for some reason you have to divide window width/height by two, but not the location
        output_geom = f"{str(int(Window.size[0]/2))}x{str(int(Window.size[1]/2))}+{str(int(Window.left))},{str(int(Window.top))}"
    else:
        output_geom = f"{str(Window.size[0])}x{str(Window.size[1])}+{str(Window.left)},{str(Window.top)}"
    # re-read in case another version overwrote
    config.read(config_filename)
    config.set('LastRun', f'{os.getcwd()}--geom', output_geom)
    config.set('LastRun', f'lastgeom', output_geom)
    with open(config_filename, 'w') as configfile:
        config.write(configfile)

