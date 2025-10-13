package main

import (
	"fmt"
	"image"
	_ "image/gif"
	_ "image/jpeg"
	_ "image/png"
	"log"
	"math/rand"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"time"

	"fyne.io/fyne/v2"
	"fyne.io/fyne/v2/app"
	"fyne.io/fyne/v2/canvas"
	"fyne.io/fyne/v2/container"
	"fyne.io/fyne/v2/driver/desktop"
	"fyne.io/fyne/v2/widget"
)

// ImageViewer holds the state of the image viewer
type ImageViewer struct {
	app            fyne.App
	window         fyne.Window
	images         []string
	currentIndex   int
	currentImage   *canvas.Image
	scroll         *container.Scroll
	feedbackLabel  *widget.Label
	zoomLevel      float32
	changeType     string // "ordered", "random", "shuffled"
	shuffledOrder  []int
	shuffledIndex  int
	trashDir       string
	slideshow      bool
	slideshowTimer *time.Ticker
	slideshowStop  chan bool
	// Cache current image dimensions to avoid repeated decoding
	currentImgWidth  int
	currentImgHeight int
	// Progressive scrolling state
	lastScrollTime   time.Time
	scrollPixels     float32
	scrollResetDelay time.Duration
}

func main() {
	log.SetFlags(log.LstdFlags | log.Lshortfile)

	// Create app
	myApp := app.New()
	myWindow := myApp.NewWindow("Timeless Image Viewer")

	// Create viewer
	viewer := &ImageViewer{
		app:              myApp,
		window:           myWindow,
		zoomLevel:        1.0,
		changeType:       "ordered",
		currentIndex:     0,
		trashDir:         filepath.Join(os.Getenv("HOME"), ".Trash"),
		slideshowStop:    make(chan bool),
		scrollPixels:     10.0,
		scrollResetDelay: 500 * time.Millisecond,
	}

	// Collect images from command line
	viewer.collectImages(os.Args[1:])

	if len(viewer.images) == 0 {
		log.Println("No images found to display")
		os.Exit(1)
	}

	log.Printf("Found %d images to display\n", len(viewer.images))

	// Create UI
	viewer.setupUI()

	// Load first image
	viewer.loadImage(0)

	// Set up keyboard handling
	myWindow.Canvas().SetOnTypedKey(viewer.handleKeyPress)
	myWindow.Canvas().SetOnTypedRune(viewer.handleRunePress)

	// Show and run
	myWindow.Resize(fyne.NewSize(1920, 1080))
	myWindow.ShowAndRun()
}

// collectImages gathers all image files from command line arguments
func (v *ImageViewer) collectImages(args []string) {
	if len(args) == 0 {
		args = []string{"."}
	}

	imageMap := make(map[string]bool)
	shouldSort := false

	for _, arg := range args {
		info, err := os.Stat(arg)
		if err != nil {
			log.Printf("Warning: cannot access %s: %v\n", arg, err)
			continue
		}

		if info.IsDir() {
			shouldSort = true
			entries, err := os.ReadDir(arg)
			if err != nil {
				log.Printf("Warning: cannot read directory %s: %v\n", arg, err)
				continue
			}

			for _, entry := range entries {
				if entry.IsDir() {
					continue
				}
				name := entry.Name()
				lower := strings.ToLower(name)
				if strings.HasSuffix(lower, ".jpg") ||
					strings.HasSuffix(lower, ".jpeg") ||
					strings.HasSuffix(lower, ".png") ||
					strings.HasSuffix(lower, ".gif") {
					fullPath := filepath.Join(arg, name)
					imageMap[fullPath] = true
				}
			}
		} else {
			// It's a file
			imageMap[arg] = true
		}
	}

	// Convert map to slice
	for img := range imageMap {
		v.images = append(v.images, img)
	}

	// Sort if we collected from directories
	if shouldSort {
		sort.Strings(v.images)
	}
}

// setupUI creates the user interface
func (v *ImageViewer) setupUI() {
	// Create image widget
	v.currentImage = canvas.NewImageFromFile("")
	v.currentImage.FillMode = canvas.ImageFillContain
	// Use fastest scaling for better performance with large images
	v.currentImage.ScaleMode = canvas.ImageScaleFastest

	// Create scroll container
	v.scroll = container.NewScroll(v.currentImage)
	v.scroll.Direction = container.ScrollBoth

	// Create feedback label (bottom overlay)
	v.feedbackLabel = widget.NewLabel("")
	v.feedbackLabel.TextStyle = fyne.TextStyle{Bold: true}
	v.feedbackLabel.Hide()

	// Create overlay with image and feedback
	content := container.NewStack(
		v.scroll,
		container.NewVBox(
			widget.NewLabel(""), // spacer
			v.feedbackLabel,
		),
	)

	v.window.SetContent(content)
}

// loadImage loads and displays the image at the given index
func (v *ImageViewer) loadImage(index int) {
	if index < 0 || index >= len(v.images) {
		return
	}

	v.currentIndex = index
	imgPath := v.images[index]

	// Load image to get dimensions and cache them
	file, err := os.Open(imgPath)
	if err != nil {
		log.Printf("Error opening image %s: %v\n", imgPath, err)
		v.showFeedback(fmt.Sprintf("Error loading image: %v", err), 3*time.Second)
		return
	}
	defer file.Close()

	img, _, err := image.Decode(file)
	if err != nil {
		log.Printf("Error decoding image %s: %v\n", imgPath, err)
		v.showFeedback(fmt.Sprintf("Error decoding image: %v", err), 3*time.Second)
		return
	}

	// Cache dimensions for fast zoom operations
	bounds := img.Bounds()
	v.currentImgWidth = bounds.Dx()
	v.currentImgHeight = bounds.Dy()

	// Update the canvas image
	v.currentImage.File = imgPath
	v.currentImage.Refresh()

	// Reset zoom
	v.zoomLevel = 1.0
	v.fitToWindow()

	// Update window title
	v.window.SetTitle(fmt.Sprintf("Timeless Image Viewer - %s (%d/%d)",
		filepath.Base(imgPath), index+1, len(v.images)))

	log.Printf("Loaded image %d/%d: %s [%dx%d]\n",
		index+1, len(v.images), filepath.Base(imgPath),
		v.currentImgWidth, v.currentImgHeight)
}

// fitToWindow scales the image to fit the window
func (v *ImageViewer) fitToWindow() {
	start := time.Now()
	log.Printf("fitToWindow: START")

	// Reset to fit mode - clear any fixed sizing
	v.currentImage.FillMode = canvas.ImageFillContain
	v.currentImage.SetMinSize(fyne.NewSize(0, 0))
	v.zoomLevel = 1.0
	log.Printf("fitToWindow: properties set (%v)", time.Since(start))

	// Only refresh the container - it will cascade to children
	// Use the canvas content tree refresh which is faster
	v.window.Canvas().Content().Refresh()
	log.Printf("fitToWindow: DONE (%v total)", time.Since(start))
}

// setZoom sets the image to a specific zoom level
func (v *ImageViewer) setZoom(zoom float32) {
	start := time.Now()
	log.Printf("setZoom: START zoom=%.2f", zoom)

	v.zoomLevel = zoom

	// Use cached dimensions for fast zoom
	width := float32(v.currentImgWidth) * zoom
	height := float32(v.currentImgHeight) * zoom

	// Set to original fill mode and set explicit size
	v.currentImage.FillMode = canvas.ImageFillOriginal
	v.currentImage.SetMinSize(fyne.NewSize(width, height))
	log.Printf("setZoom: properties set (%v)", time.Since(start))

	// Only refresh the container - it will cascade to children
	v.window.Canvas().Content().Refresh()
	log.Printf("setZoom: DONE (%v total)", time.Since(start))
}

// nextImage advances to the next image based on change type
func (v *ImageViewer) nextImage(changeType string, skip int) {
	v.changeType = changeType

	switch changeType {
	case "ordered":
		newIndex := v.currentIndex + skip
		if newIndex >= len(v.images) {
			newIndex = len(v.images) - 1
		}
		v.loadImage(newIndex)

	case "random":
		if len(v.images) > 1 {
			newIndex := rand.Intn(len(v.images))
			v.loadImage(newIndex)
		}

	case "shuffled":
		if v.shuffledOrder == nil {
			v.initShuffle()
		}
		v.shuffledIndex++
		if v.shuffledIndex >= len(v.shuffledOrder) {
			v.shuffledIndex = 0
		}
		v.loadImage(v.shuffledOrder[v.shuffledIndex])
	}
}

// prevImage goes to the previous image based on change type
func (v *ImageViewer) prevImage(changeType string, skip int) {
	v.changeType = changeType

	switch changeType {
	case "ordered":
		newIndex := v.currentIndex - skip
		if newIndex < 0 {
			newIndex = 0
		}
		v.loadImage(newIndex)

	case "random":
		if len(v.images) > 1 {
			newIndex := rand.Intn(len(v.images))
			v.loadImage(newIndex)
		}

	case "shuffled":
		if v.shuffledOrder == nil {
			v.initShuffle()
		}
		v.shuffledIndex--
		if v.shuffledIndex < 0 {
			v.shuffledIndex = len(v.shuffledOrder) - 1
		}
		v.loadImage(v.shuffledOrder[v.shuffledIndex])
	}
}

// initShuffle creates a shuffled order of indices
func (v *ImageViewer) initShuffle() {
	v.shuffledOrder = make([]int, len(v.images))
	for i := range v.shuffledOrder {
		v.shuffledOrder[i] = i
	}
	rand.Shuffle(len(v.shuffledOrder), func(i, j int) {
		v.shuffledOrder[i], v.shuffledOrder[j] = v.shuffledOrder[j], v.shuffledOrder[i]
	})
	v.shuffledIndex = 0
}

// deleteCurrentImage moves the current image to trash
func (v *ImageViewer) deleteCurrentImage() {
	if v.currentIndex >= len(v.images) {
		return
	}

	imgPath := v.images[v.currentIndex]
	filename := filepath.Base(imgPath)
	trashPath := filepath.Join(v.trashDir, filename)

	// Check if file already exists in trash
	if _, err := os.Stat(trashPath); err == nil {
		v.showFeedback(fmt.Sprintf("File already exists in trash: %s", filename), 3*time.Second)
		return
	}

	// Move to trash
	err := os.Rename(imgPath, trashPath)
	if err != nil {
		v.showFeedback(fmt.Sprintf("Error moving to trash: %v", err), 3*time.Second)
		log.Printf("Error moving %s to trash: %v\n", imgPath, err)
		return
	}

	v.showFeedback(fmt.Sprintf("Moved to trash: %s", filename), 2*time.Second)
	log.Printf("Deleted (moved to trash): %s\n", imgPath)

	// Remove from list
	v.images = append(v.images[:v.currentIndex], v.images[v.currentIndex+1:]...)

	// Load next image or previous if at end
	if v.currentIndex >= len(v.images) {
		v.currentIndex = len(v.images) - 1
	}
	if len(v.images) > 0 {
		v.loadImage(v.currentIndex)
	} else {
		v.showFeedback("No more images", 3*time.Second)
	}
}

// showFeedback displays a temporary message to the user
func (v *ImageViewer) showFeedback(message string, duration time.Duration) {
	v.feedbackLabel.SetText(message)
	v.feedbackLabel.Show()

	go func() {
		time.Sleep(duration)
		// Use fyne.Do to ensure UI operations run on the main thread
		fyne.Do(func() {
			v.feedbackLabel.Hide()
		})
	}()
}

// toggleSlideshow starts or stops the slideshow
func (v *ImageViewer) toggleSlideshow(interval time.Duration) {
	if v.slideshow {
		// Stop slideshow
		v.slideshow = false
		v.slideshowStop <- true
		v.showFeedback("Slideshow stopped", 1*time.Second)
	} else {
		// Start slideshow
		v.slideshow = true
		v.showFeedback(fmt.Sprintf("Slideshow started (%v interval)", interval), 2*time.Second)

		go func() {
			ticker := time.NewTicker(interval)
			defer ticker.Stop()

			for {
				select {
				case <-ticker.C:
					v.nextImage(v.changeType, 1)
				case <-v.slideshowStop:
					return
				}
			}
		}()
	}
}

// updateScrollSpeed calculates progressive scrolling speed
func (v *ImageViewer) updateScrollSpeed() float32 {
	now := time.Now()
	timeSinceLastScroll := now.Sub(v.lastScrollTime)

	// If it's been longer than the reset delay, reset to initial speed
	if timeSinceLastScroll > v.scrollResetDelay {
		v.scrollPixels = 10.0
	} else {
		// Increase scroll speed by 2 pixels, max out at reasonable limit
		v.scrollPixels += 2.0
		if v.scrollPixels > 100.0 {
			v.scrollPixels = 100.0
		}
	}

	v.lastScrollTime = now
	return v.scrollPixels
}

// handleKeyPress handles special key presses (arrows, delete, etc.)
func (v *ImageViewer) handleKeyPress(key *fyne.KeyEvent) {
	// Don't log every keypress - causes slowdown
	// log.Printf("Key pressed: %v\n", key.Name)

	switch key.Name {
	case fyne.KeyLeft:
		scrollDist := v.updateScrollSpeed()
		newOffset := v.scroll.Offset.X - scrollDist
		if newOffset < 0 {
			newOffset = 0
		}
		v.scroll.ScrollToOffset(fyne.NewPos(newOffset, v.scroll.Offset.Y))

	case fyne.KeyRight:
		scrollDist := v.updateScrollSpeed()
		maxX := v.currentImage.Size().Width - v.scroll.Size().Width
		if maxX < 0 {
			maxX = 0
		}
		newOffset := v.scroll.Offset.X + scrollDist
		if newOffset > maxX {
			newOffset = maxX
		}
		v.scroll.ScrollToOffset(fyne.NewPos(newOffset, v.scroll.Offset.Y))

	case fyne.KeyUp:
		scrollDist := v.updateScrollSpeed()
		newOffset := v.scroll.Offset.Y - scrollDist
		if newOffset < 0 {
			newOffset = 0
		}
		v.scroll.ScrollToOffset(fyne.NewPos(v.scroll.Offset.X, newOffset))

	case fyne.KeyDown:
		scrollDist := v.updateScrollSpeed()
		maxY := v.currentImage.Size().Height - v.scroll.Size().Height
		if maxY < 0 {
			maxY = 0
		}
		newOffset := v.scroll.Offset.Y + scrollDist
		if newOffset > maxY {
			newOffset = maxY
		}
		v.scroll.ScrollToOffset(fyne.NewPos(v.scroll.Offset.X, newOffset))

	case fyne.KeyDelete, fyne.KeyBackspace:
		if key.Name == fyne.KeyBackspace {
			// Check for Cmd/Meta modifier
			if desk, ok := v.window.Canvas().(desktop.Canvas); ok {
				_ = desk // On macOS, Cmd+Backspace is delete
			}
		}
		v.deleteCurrentImage()

	case fyne.KeyPageDown:
		v.nextImage("ordered", 1)

	case fyne.KeyPageUp:
		v.prevImage("ordered", 1)

	case fyne.KeyHome:
		v.loadImage(0)

	case fyne.KeyEnd:
		v.loadImage(len(v.images) - 1)
	}
}

// handleRunePress handles character key presses
func (v *ImageViewer) handleRunePress(r rune) {
	start := time.Now()
	log.Printf("handleRunePress: START key=%c", r)

	switch r {
	// Navigation
	case '\'', '"':
		skip := 1
		if r == '"' { // Shift+' is "
			skip = 10
		}
		v.nextImage("ordered", skip)

	case ';', ':':
		skip := 1
		if r == ':' { // Shift+; is :
			skip = 10
		}
		v.prevImage("ordered", skip)

	case '.':
		v.nextImage("random", 1)

	case ',':
		v.prevImage("random", 1)

	case ']':
		v.nextImage("shuffled", 1)

	case '[':
		v.prevImage("shuffled", 1)

	// Zoom
	case '-', '_':
		v.zoomLevel *= 0.9
		v.setZoom(v.zoomLevel)
		v.showFeedback(fmt.Sprintf("Zoom: %.0f%%", v.zoomLevel*100), 1*time.Second)

	case '=', '+':
		v.zoomLevel *= 1.1
		v.setZoom(v.zoomLevel)
		v.showFeedback(fmt.Sprintf("Zoom: %.0f%%", v.zoomLevel*100), 1*time.Second)

	case 'z', '1':
		v.setZoom(1.0)
		log.Printf("handleRunePress: after setZoom (%v)", time.Since(start))
		v.showFeedback("Zoom: 100% (1:1)", 1*time.Second)
		log.Printf("handleRunePress: after showFeedback (%v)", time.Since(start))

	case 'x':
		v.fitToWindow()
		log.Printf("handleRunePress: after fitToWindow (%v)", time.Since(start))
		v.showFeedback("Fit to window", 1*time.Second)
		log.Printf("handleRunePress: after showFeedback (%v)", time.Since(start))

	case '2':
		v.setZoom(2.0)
		v.showFeedback("Zoom: 200%", 1*time.Second)

	case '3':
		v.setZoom(3.0)
		v.showFeedback("Zoom: 300%", 1*time.Second)

	case '4':
		v.setZoom(4.0)
		v.showFeedback("Zoom: 400%", 1*time.Second)

	// Slideshow
	case 's', 'S':
		interval := 20 * time.Second
		if r == 'S' {
			interval = 40 * time.Second
		}
		v.toggleSlideshow(interval)

	// Quit
	case 'q', 'Q':
		v.app.Quit()
	}
}
