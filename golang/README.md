# Timeless Image Viewer (Golang Version)

A simple image viewer written in Go using the Fyne UI toolkit.

## Features

- View and navigate through images in a directory
- Zoom in/out and fit to window
- Support for panning around images
- Multiple navigation modes (ordered, shuffled, random)
- Slideshow functionality
- Move, copy, and delete images
- Configuration saved between sessions

## Requirements

- Go 1.16 or later
- Fyne v2.3.5 or later

## Installation

1. Install Go if not already installed: https://golang.org/doc/install
2. Install Fyne dependencies: https://developer.fyne.io/started/
3. Clone this repository
4. Run `go mod tidy` to download dependencies
5. Build with `go build -o timeless-imgview`

## Usage

```
./timeless-imgview [directory or image files]
```

If no arguments are provided, the current directory is used.

## Keyboard Controls

- Arrow keys: Pan image
- PageDown/PageUp: Next/previous image (ordered)
- Home/End: First/last image
- +/=: Zoom in
- -/_: Zoom out
- 1/z: Zoom 1:1
- 2/3/4: Zoom to 2x/3x/4x
- x: Fit to window
- f: Toggle fullscreen
- s: Toggle slideshow
- ['/"]: Next image (ordered)
- [;/:]: Previous image (ordered)
- [: Previous image (shuffled)
- ]: Next image (shuffled)
- ,: Previous image (random)
- .: Next image (random)
- Delete: Delete current image
- m then key: Move image to configured destination
- c then key: Copy image to configured destination
- q then q: Quit application

## Configuration

Configuration is stored in `~/.tiviewrc.json` and includes:

- Image destination directories (for move/copy operations)
- UI settings (feedback colors, font size)
- Slideshow interval
- Last window size and position