# here're the prereqs

## #old mac
## brew install python3 pango sdl2 sdl2_ttf sdl2_mixer sdl2_image sdl2_gfx gstreamer   #mac - also python3 dev?
## brew install python3 pango sdl sdl_image sdl_mixer sdl_ttf portmidi
##everything
#pip3 install docutils pygments kivy.deps.sdl2 kivy.deps.glew kivy.deps.gstreamer
#pip3 install pygame wheel setuptools reusables kivy #both

# I think only the following is needed
# __________________________________________________
#
#new mac - if you don't do this you get weird errors or behaviours even on OSX Monterey
brew install pyenv
brew install python@3.7      #<--trying this now

#mac/linux both hooray
python3 -m pip install reusables kivy

