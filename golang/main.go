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
	// Only one active navigation list at a time
	navOrder       []int  // Current navigation order (ordered, shuffled, or random)
	navIndex       int    // Current position in navOrder
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
	// Image preloading cache
	imageCache      map[string]*imageInfo
	preloadChan     chan int
	// Debug profiling
	debugProfile   bool
}

// imageInfo holds cached image data
type imageInfo struct {
	width   int
	height  int
	imgData image.Image // Cached decoded image
}

func main() {
	log.SetFlags(log.LstdFlags | log.Lshortfile)

	// Seed random number generator
	rand.Seed(time.Now().UnixNano())

	// Parse command line arguments
	var args []string
	debugProfile := false
	for i := 1; i < len(os.Args); i++ {
		if os.Args[i] == "--debug-profile" {
			debugProfile = true
		} else {
			args = append(args, os.Args[i])
		}
	}

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
		navIndex:         0,
		trashDir:         filepath.Join(os.Getenv("HOME"), ".Trash"),
		slideshowStop:    make(chan bool),
		scrollPixels:     10.0,
		scrollResetDelay: 500 * time.Millisecond,
		imageCache:       make(map[string]*imageInfo),
		preloadChan:      make(chan int, 10),
		debugProfile:     debugProfile,
	}

	if viewer.debugProfile {
		log.Printf("Debug profiling enabled")
	}

	// Start preloader goroutine
	go viewer.preloader()

	// Collect images from command line
	viewer.collectImages(args)

	if len(viewer.images) == 0 {
		log.Println("No images found to display")
		os.Exit(1)
	}

	log.Printf("Found %d images to display\n", len(viewer.images))

	// Initialize ordered navigation list
	viewer.navOrder = make([]int, len(viewer.images))
	for i := range viewer.navOrder {
		viewer.navOrder[i] = i
	}

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
	hasDirectories := false

	for _, arg := range args {
		info, err := os.Stat(arg)
		if err != nil {
			log.Printf("Warning: cannot access %s: %v\n", arg, err)
			continue
		}

		if info.IsDir() {
			hasDirectories = true
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
			// It's a file - add in order received
			if !imageMap[arg] {
				imageMap[arg] = true
				v.images = append(v.images, arg)
			}
		}
	}

	// If we collected from directories, we need to add those files and sort everything
	if hasDirectories {
		// Reset the slice and rebuild from map
		v.images = nil
		for img := range imageMap {
			v.images = append(v.images, img)
		}
		// Sort when collecting from directories
		sort.Strings(v.images)
	}
	// Otherwise, files are already in v.images in the order they were passed
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

// preloader runs in background and preloads adjacent images
func (v *ImageViewer) preloader() {
	for index := range v.preloadChan {
		// Determine which indices to preload based on navigation mode
		var indicesToPreload []int

		switch v.changeType {
		case "ordered":
			// Preload previous and next in ordered list
			if index > 0 {
				indicesToPreload = append(indicesToPreload, index-1)
			}
			if index < len(v.images)-1 {
				indicesToPreload = append(indicesToPreload, index+1)
			}

		case "shuffled", "random":
			if v.navOrder != nil {
				// Preload previous and next in current navigation order
				prevIdx := v.navIndex - 1
				if prevIdx < 0 {
					prevIdx = len(v.navOrder) - 1
				}
				nextIdx := v.navIndex + 1
				if nextIdx >= len(v.navOrder) {
					nextIdx = 0
				}
				indicesToPreload = append(indicesToPreload, v.navOrder[prevIdx], v.navOrder[nextIdx])
			}
		}

		// Preload the identified images
		for _, preloadIdx := range indicesToPreload {
			if preloadIdx < 0 || preloadIdx >= len(v.images) {
				continue
			}

			imgPath := v.images[preloadIdx]

			// Skip if already cached
			if _, exists := v.imageCache[imgPath]; exists {
				continue
			}

			// Load and cache dimensions
			start := time.Now()
			if info := v.loadImageInfo(imgPath); info != nil {
				v.imageCache[imgPath] = info
				if v.debugProfile {
					log.Printf("Preloaded (%s): %s [%dx%d] in %v\n", v.changeType, filepath.Base(imgPath), info.width, info.height, time.Since(start))
				}
			}
		}
	}
}

// loadImageInfo loads image dimensions and decoded data
func (v *ImageViewer) loadImageInfo(path string) *imageInfo {
	start := time.Now()
	file, err := os.Open(path)
	if err != nil {
		return nil
	}
	defer file.Close()

	if v.debugProfile {
		log.Printf("loadImageInfo: File opened for %s (%v)", filepath.Base(path), time.Since(start))
	}

	decodeStart := time.Now()
	img, _, err := image.Decode(file)
	if err != nil {
		return nil
	}
	if v.debugProfile {
		log.Printf("loadImageInfo: Image decoded for %s (%v since decode start, %v total)", filepath.Base(path), time.Since(decodeStart), time.Since(start))
	}

	bounds := img.Bounds()
	return &imageInfo{
		width:   bounds.Dx(),
		height:  bounds.Dy(),
		imgData: img,
	}
}

// loadImage loads and displays the image at the given index
func (v *ImageViewer) loadImage(index int) {
	overallStart := time.Now()
	if v.debugProfile {
		log.Printf("loadImage: START index=%d", index)
	}

	if index < 0 || index >= len(v.images) {
		return
	}

	v.currentIndex = index
	imgPath := v.images[index]

	// Check if dimensions are cached
	dimStart := time.Now()
	if info, exists := v.imageCache[imgPath]; exists {
		v.currentImgWidth = info.width
		v.currentImgHeight = info.height
		if v.debugProfile {
			log.Printf("loadImage: Using cached dimensions for %s [%dx%d] (%v)\n", filepath.Base(imgPath), info.width, info.height, time.Since(dimStart))
		}
	} else {
		// Load image to get dimensions and cache them
		if info := v.loadImageInfo(imgPath); info != nil {
			v.currentImgWidth = info.width
			v.currentImgHeight = info.height
			v.imageCache[imgPath] = info
			if v.debugProfile {
				log.Printf("loadImage: Loaded and cached dimensions for %s [%dx%d] (%v)\n", filepath.Base(imgPath), info.width, info.height, time.Since(dimStart))
			}
		} else {
			log.Printf("Error loading image %s\n", imgPath)
			v.showFeedback("Error loading image", 3*time.Second)
			return
		}
	}

	// Update the canvas image using cached data if available
	fileStart := time.Now()
	if info, exists := v.imageCache[imgPath]; exists && info.imgData != nil {
		// Use cached decoded image
		v.currentImage.Image = info.imgData
		if v.debugProfile {
			log.Printf("loadImage: Using cached decoded image (%v since file set start, %v since overall start)", time.Since(fileStart), time.Since(overallStart))
		}
	} else {
		// Fall back to loading from file
		v.currentImage.File = imgPath
		if v.debugProfile {
			log.Printf("loadImage: Set File property (no cache, will load from disk) (%v since file set start, %v since overall start)", time.Since(fileStart), time.Since(overallStart))
		}
	}

	// Reset zoom and fit to window
	fitStart := time.Now()
	v.zoomLevel = 1.0
	v.fitToWindow()
	if v.debugProfile {
		log.Printf("loadImage: fitToWindow completed (%v since fit start, %v since overall start)", time.Since(fitStart), time.Since(overallStart))
	}

	// Update window title
	titleStart := time.Now()
	v.window.SetTitle(fmt.Sprintf("Timeless Image Viewer - %s (%d/%d)",
		filepath.Base(imgPath), index+1, len(v.images)))
	if v.debugProfile {
		log.Printf("loadImage: Window title updated (%v since title start, %v since overall start)", time.Since(titleStart), time.Since(overallStart))
	}

	if v.debugProfile {
		log.Printf("loadImage: COMPLETE %d/%d: %s [%dx%d] (TOTAL: %v)\n",
			index+1, len(v.images), filepath.Base(imgPath),
			v.currentImgWidth, v.currentImgHeight, time.Since(overallStart))
	}

	// Trigger preloading of adjacent images
	select {
	case v.preloadChan <- index:
	default:
		// Channel full, skip preload request
	}
}

// fitToWindow scales the image to fit the window
func (v *ImageViewer) fitToWindow() {
	start := time.Now()
	if v.debugProfile {
		log.Printf("fitToWindow: START")
	}

	// Reset to fit mode - clear any fixed sizing
	propStart := time.Now()
	v.currentImage.FillMode = canvas.ImageFillContain
	v.currentImage.SetMinSize(fyne.NewSize(0, 0))
	v.zoomLevel = 1.0
	if v.debugProfile {
		log.Printf("fitToWindow: properties set (%v)", time.Since(propStart))
	}

	// Refresh just the image widget, not the entire content tree
	refreshStart := time.Now()
	v.currentImage.Refresh()
	if v.debugProfile {
		log.Printf("fitToWindow: Image refresh completed (%v since refresh start, %v total)", time.Since(refreshStart), time.Since(start))
	}
}

// setZoom sets the image to a specific zoom level
func (v *ImageViewer) setZoom(zoom float32) {
	start := time.Now()
	if v.debugProfile {
		log.Printf("setZoom: START zoom=%.2f", zoom)
	}

	v.zoomLevel = zoom

	// Use cached dimensions for fast zoom
	width := float32(v.currentImgWidth) * zoom
	height := float32(v.currentImgHeight) * zoom

	// Set to original fill mode and set explicit size
	propStart := time.Now()
	v.currentImage.FillMode = canvas.ImageFillOriginal
	v.currentImage.SetMinSize(fyne.NewSize(width, height))
	if v.debugProfile {
		log.Printf("setZoom: properties set (%v)", time.Since(propStart))
	}

	// Refresh just the image widget
	refreshStart := time.Now()
	v.currentImage.Refresh()
	if v.debugProfile {
		log.Printf("setZoom: Image refresh completed (%v since refresh start, %v total)", time.Since(refreshStart), time.Since(start))
	}
}

// ensureNavOrder creates navigation order if needed and updates navIndex to current position
func (v *ImageViewer) ensureNavOrder(changeType string) {
	// If switching navigation modes, create new order
	if v.changeType != changeType || v.navOrder == nil {
		v.changeType = changeType

		switch changeType {
		case "ordered":
			// Always recreate ordered list when switching to ordered mode
			v.navOrder = make([]int, len(v.images))
			for i := range v.navOrder {
				v.navOrder[i] = i
			}
			// Find current image in ordered list
			v.navIndex = v.currentIndex

		case "random":
			v.initRandom()
			// Find current image in random order
			for i, idx := range v.navOrder {
				if idx == v.currentIndex {
					v.navIndex = i
					break
				}
			}

		case "shuffled":
			v.initShuffle()
			// Find current image in shuffled order
			for i, idx := range v.navOrder {
				if idx == v.currentIndex {
					v.navIndex = i
					break
				}
			}
		}
	}
}

// nextImage advances to the next image based on change type
func (v *ImageViewer) nextImage(changeType string, skip int) {
	if v.debugProfile {
		log.Printf("nextImage: changeType=%s, skip=%d, currentIndex=%d, navIndex=%d", changeType, skip, v.currentIndex, v.navIndex)
	}
	v.ensureNavOrder(changeType)

	// Navigate forward in current order
	oldNavIndex := v.navIndex
	v.navIndex += skip
	if v.navIndex >= len(v.navOrder) {
		v.navIndex = len(v.navOrder) - 1
	}

	if v.debugProfile {
		log.Printf("nextImage: navIndex %d -> %d, will load image index %d (%s)",
			oldNavIndex, v.navIndex, v.navOrder[v.navIndex], filepath.Base(v.images[v.navOrder[v.navIndex]]))
	}
	v.loadImage(v.navOrder[v.navIndex])
}

// prevImage goes to the previous image based on change type
func (v *ImageViewer) prevImage(changeType string, skip int) {
	v.ensureNavOrder(changeType)

	// Navigate backward in current order
	v.navIndex -= skip
	if v.navIndex < 0 {
		v.navIndex = 0
	}

	v.loadImage(v.navOrder[v.navIndex])
}

// initRandom creates a randomized order of indices
func (v *ImageViewer) initRandom() {
	v.navOrder = make([]int, len(v.images))
	for i := range v.navOrder {
		v.navOrder[i] = i
	}
	rand.Shuffle(len(v.navOrder), func(i, j int) {
		v.navOrder[i], v.navOrder[j] = v.navOrder[j], v.navOrder[i]
	})
	v.navIndex = 0
	log.Printf("Initialized random order for %d images\n", len(v.navOrder))
}

// initShuffle creates a semi-shuffled order of indices
// Similar to Python version: start ordered, then swap each element with
// a random neighbor up to ~20 positions away
func (v *ImageViewer) initShuffle() {
	v.navOrder = make([]int, len(v.images))
	// Start with ordered list
	for i := range v.navOrder {
		v.navOrder[i] = i
	}

	// Do a single pass, swapping each position with a random nearby position
	maxSwapDistance := 20
	for i := range v.navOrder {
		// Pick a random offset up to maxSwapDistance away
		offset := rand.Intn(maxSwapDistance + 1)
		// Randomly choose forward or backward
		if rand.Intn(2) == 0 {
			offset = -offset
		}

		// Calculate swap position, keeping it in bounds
		swapPos := i + offset
		if swapPos < 0 {
			swapPos = 0
		}
		if swapPos >= len(v.navOrder) {
			swapPos = len(v.navOrder) - 1
		}

		// Swap
		v.navOrder[i], v.navOrder[swapPos] = v.navOrder[swapPos], v.navOrder[i]
	}

	v.navIndex = 0
	log.Printf("Initialized semi-shuffled order for %d images (max swap distance: %d)\n", len(v.navOrder), maxSwapDistance)
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
	if v.debugProfile {
		log.Printf("handleRunePress: START key=%c", r)
	}

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
		if v.debugProfile {
			log.Printf("handleRunePress: after setZoom (%v)", time.Since(start))
		}
		v.showFeedback("Zoom: 100% (1:1)", 1*time.Second)

	case 'x':
		v.fitToWindow()
		if v.debugProfile {
			log.Printf("handleRunePress: after fitToWindow (%v)", time.Since(start))
		}
		v.showFeedback("Fit to window", 1*time.Second)

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

	if v.debugProfile {
		log.Printf("handleRunePress: COMPLETE key=%c (%v total)", r, time.Since(start))
	}
}
