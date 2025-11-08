#!/usr/bin/env python

import configparser
#import logging
import os
import re
import subprocess
from kivy.app import App
from kivy.logger import Logger, LOG_LEVELS
from kivy.core.window import Window
from kivy.uix.gridlayout import GridLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.utils import platform
from tiviewlib.ImageViewer import ImageViewer
from kivy.config import Config

# stop the annoying red dot on right-click
Config.set('input', 'mouse', 'mouse,multitouch_on_demand')

LOG_LEVEL = os.getenv('LOG_LEVEL', 'info')
Logger.setLevel(LOG_LEVELS[LOG_LEVEL])
Logger.info(f"LOG_LEVEL={LOG_LEVEL}, to force to some level, export LOG_LEVEL=info (or debug,..) before starting.")

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
    if (len(resBits) == 0):
        # for some reason sometimes I don't get a res?
        deviceRes = [1920,1080]
    else:
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
    f.write("feedback-fg = 0.85,0.85,0.85,0.9\n")
    f.write("feedback-bg = 0.05,0.05,0.05,0.3\n")
    f.write("feedback-fontsize = 32\n")
    f.write("slideshow-interval = 20\n")
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
    # re-read in case another version overwrote - use fresh ConfigParser to avoid order issues
    fresh_config = configparser.ConfigParser()
    fresh_config.read(config_filename)

    # Read slideshow-interval from the freshly loaded config
    slideshowInterval = fresh_config.get("UI", "slideshow-interval")

    # Implement LRU cache for LastRun geometries (max 50 entries)
    current_cwd_key = f'{os.getcwd().lower()}--geom'

    # Get all existing LastRun entries, preserving order from the file
    existing_entries = []
    if fresh_config.has_section('LastRun'):
        for key, value in fresh_config.items('LastRun'):
            existing_entries.append((key, value))

    # Remove the LastRun section and recreate it with proper order
    fresh_config.remove_section('LastRun')
    fresh_config.add_section('LastRun')

    # 1. Always add 'lastgeom' first (the fallback default)
    fresh_config.set('LastRun', 'lastgeom', output_geom)

    # 2. Add the current CWD at the top of the list (after lastgeom)
    fresh_config.set('LastRun', current_cwd_key, output_geom)

    # 3. Add remaining entries (up to 48 more to reach max of 50 total)
    # Skip the current CWD key and 'lastgeom' if they exist in old entries
    entries_added = 2  # lastgeom and current_cwd_key
    for key, value in existing_entries:
        if entries_added >= 50:
            break
        if key != current_cwd_key and key != 'lastgeom':
            fresh_config.set('LastRun', key, value)
            entries_added += 1

    fresh_config.set('UI', 'slideshow-interval', slideshowInterval)
    with open(config_filename, 'w') as configfile:
        fresh_config.write(configfile)

