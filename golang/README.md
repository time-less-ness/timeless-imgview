# Timeless Image Viewer (Golang Version)

A lightweight, keyboard-driven image viewer written in Go using the Fyne GUI toolkit.

## Features

- **Command-line driven**: Pass files or directories as arguments
- **Multiple navigation modes**: Sequential, random, and shuffled viewing
- **Keyboard-only control**: Navigate, zoom, and manage images without touching the mouse
- **Image formats**: JPEG, PNG, GIF support via Go's standard library
- **Delete to trash**: Move unwanted images to ~/.Trash
- **Slideshow mode**: Automated viewing with configurable intervals
- **Zoom controls**: Multiple zoom levels and fit-to-window mode
- **User feedback**: On-screen messages show current action and status

## Building

### Prerequisites

- Go 1.19 or later
- macOS with native development tools (Xcode Command Line Tools)

### Build Commands

```bash
# Build for macOS (native architecture)
make mac

# The binary will be at: build/timeless-imageview
```

**Note**: You may see linker warnings like `ld: warning: ignoring duplicate libraries` and `LC_DYSYMTAB`. These are known Go/macOS issues and can be safely ignored - the binary works fine.

## Running

```bash
# View all images in current directory
./build/timeless-imageview .

# View specific files
./build/timeless-imageview img1.jpg img2.png img3.gif

# View all images in subdirectories
./build/timeless-imageview */

# View specific directory
./build/timeless-imageview /path/to/images/
```

### Create an Alias (Recommended)

Add to your shell rc file (~/.zshrc or ~/.bashrc):

```bash
alias tivgo='/path/to/timeless-imgview/golang/build/timeless-imageview'
```

Then use it like:
```bash
tivgo .
tivgo *.jpg
```

## Keyboard Controls

### Navigation
- **Arrow keys** - Scroll/pan around zoomed images
- **; :** - Previous image (Shift+; for 10 back)
- **' "** - Next image (Shift+' for 10 forward)
- **, .** - Previous/next in random mode
- **[ ]** - Previous/next in shuffled mode
- **Page Up/Down** - Previous/next image (ordered)
- **Home/End** - Jump to first/last image

### Zoom
- **-** - Zoom out (90%)
- **=** - Zoom in (110%)
- **z** or **1** - View at 1:1 pixel ratio (100%)
- **x** - Fit image to window
- **2, 3, 4** - View at 2x, 3x, 4x size

### Slideshow
- **s** - Toggle slideshow (20 second interval)
- **S** - Toggle slideshow (40 second interval)

### Other
- **Delete** - Move current image to ~/.Trash
- **q** - Quit application

## Implementation Notes

### Why Fyne?

This implementation uses **Fyne v2** (https://fyne.io/) as the GUI toolkit because:

1. **Large, active community**: 24.8k+ GitHub stars, well-maintained
2. **Cross-platform**: Single codebase for macOS, Linux, Windows
3. **Native image support**: Built-in JPEG, PNG, GIF handling
4. **Simple API**: Easy-to-use, idiomatic Go
5. **Rich documentation**: Extensive examples and community support

### Status Compared to Python Version

**Implemented:**
- Command-line argument parsing (files and directories)
- All keyboard navigation modes (ordered, random, shuffled)
- Full zoom functionality (fit, 1:1, 2x, 3x, 4x, incremental)
- Delete to trash
- User feedback overlay messages
- Slideshow mode with configurable intervals

**Not Yet Implemented:**
- Config file support (~/.tiviewrc for settings persistence)
- Move/copy to custom destinations (ma, mb, mc, etc.)
- Window geometry persistence between runs
- Retina display detection and handling
- Ctrl modifiers for larger skip amounts (50 images)

**Known Limitations:**
- Fyne's scroll handling differs from Kivy - progressive scrolling acceleration not implemented
- Cross-compilation requires native build environments due to C dependencies
- Fullscreen mode not implemented (was buggy in Python version anyway)

## Project Structure

```
golang/
├── main.go           # Main application and ImageViewer implementation
├── go.mod            # Go module definition
├── go.sum            # Dependency checksums
├── Makefile          # Build automation
├── README.md         # This file
└── build/            # Build output directory
    └── timeless-imageview
```

## Development

```bash
# Format code
make fmt

# Run tests (when added)
make test

# Clean build artifacts
make clean
```
