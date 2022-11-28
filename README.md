# Timeless Image Viewer
Various image viewers keep disappearing. I needed one that works on Linux and Mac. I could not
find one that suited my purposes. So I wrote my own. This one works for me.

# Installation
The brew command is needed for Mac. I believe most Linux can just do the python3 portion.
```
# mac only
brew install python@3.7

#mac/linux both hooray
python3 -m pip install reusables kivy
```

# Running
This is a CLI-only tool. Put it in your `$PATH`. For example, I have `$HOME/bin` in my path.

```
cd $HOME/bin
ln -s /path/to/timeless_imgview.py ./
```

Now you can run it. You must pass it at least one argument, eg a directory with images in it.

```
timeless_imgview.py imageDir/
timeless_imgview.py */
```

You can also pass it images, and it will display them in the order you gave them.

```
timeless_imgview.py img5.jpg img3.jpg img9.jpg
```

# Using
When in the app, you may navigate images like so:

`; '` - left/right one image
`, .` - randomise images and go through them left/right
`- =` - zoom out/in to the image
`z` - show image 1:1 pixel-wise
`x` - fit the image to your screen
`2` - view image double size
`3` - view image triple size
`del-del` - pressing `DELETE` twice will move the image to `$HOME/.Trash/` folder
`qq` - Pressing Q twice will quit the program (on Mac, so will cmd-Q or cmd-W)

# Image Support
This only supports image formats that Kivy natively supports, like JPG and PNG. Notably, it does
not handle WEBM or JPG2000.

