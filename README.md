# Timeless Image Viewer
Various good CLI image viewers keep disappearing. I needed one that works on
Linux and Mac. I could not find one that suited my purposes. So I wrote my own.
This one works for me.

# Features
* You can pass in a list of files on the commandline, and it will show them to you
  in that order.
* You can randomly look through the list of files passed in on the commandline.
* If you pass in naked directories to the commandline, it will pull all JPGs and
  PNGs (the two filetypes it knows how to display) from those directories, and
  put into the list of files to display.
* You can zoom and scroll around the image with keyboard only.
* Delete files (moves into ~/.Trash).
* Whatever window size you set for a given directory, it remembers that for the future.

# Installation
The brew command is needed for Mac. I believe most Linux can just do the python3 portion.
```
# mac only
brew install python@3.11

# mac/linux both
cd $DIR_WHERE_YOU_CHECKED_OUT_IMAGE_VIEWER
python3 -m venv venv
. venv/bin/activate
pip install reusables kivy
```

# Running
This is a CLI-only tool. It must be run inside the Python venv you created above. The
easiest way to do this is create an `alias` in your shell rcfile:

```
alias tiv='. $DIR_WHERE_YOU_CHECKED_OUT_IMAGE_VIEWER/venv/bin/activate && $DIR_WHERE_YOU_CHECKED_OUT_IMAGE_VIEWER/timeless_imgview.py'
```

Now you can run it. You should pass it an argument, eg a directory with images in it.
Some ways you might want to invoke this:

```
# view all images in current directory (but not subdirectories)
tiv .

# view all images in all subdirectories (but not current directory)
tiv */

# view all images in /path/to/imageDir/
tiv /path/to/imageDir/

# view only JPGs in all subdirectories
tiv */*.jpg

# pass it images, and it will display them in the order you gave them.
tiv img4 img3 img2 img1 img9 img8 img7

# view all images with filenames containing boats/snow, two methods
tiv $( ls -a1R | egrep -i 'boats|snow' )
tiv $( find . -iname '*.jpg' | egrep -i 'boats|snow' )

# images with file size 150k or less
tiv $( find . -size -150k -name '*.jpg' )

# view images sorted by filesize (helps to find dups, for example)
tiv $( ls -al Montages/*.jpg | awk '{print $5" "$9}' | sort -n | awk '{print $2}' )
```

# Using
When in the app, you may navigate images like so:

 * `arrow keys` - scroll around the image if larger than fit to screen
 * `; '` - Left/right one image (hold shift for 10, Ctrl for 50 images).
 * `, .` - Randomise images and go through them left/right.
 * `[ ]` - Shuffle images and go through left/right
 * `- =` - Zoom out/in to the image.
 * `z` - Show image 1:1 pixel-wise.
 * `x` - Fit the image to your screen.
 * `s` - Begin a slideshow, showing a new image every 40s, shift-S for 20s.
 * `f` - Fullscreen mode (this is buggy).
 * `2`, `3`, `4` - View image double, triple, quadruple size.
 * `del-del` - Pressing `DELETE` twice will move the image to `$HOME/.Trash/` folder.
 * `qq` - Pressing Q twice will quit the program (on Mac, so will cmd-Q or cmd-W).
 * `ma` - Move to location `a` defined in config, case insensitive. Can define 25 other locations attached to letters `b-z`.

# Image Support
This only supports image formats that Kivy natively supports, like JPG and PNG. Notably, it cannot
handle WEBM or JPG2000.

# FAQ
**Q** It stopped working! Help?

**A** Yeah, Homebrew keeps breaking my Python whenever I upgrade or install something else. Go
through the installation instructions again. If you know how to fix this, submit a PR. I think
Linux has this problem less often. Now that the instructions are updated to use `venv` I suspect
this will be less of a problem.
