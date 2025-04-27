package main

import (
	"encoding/json"
	"fmt"
	"io/ioutil"
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
	"fyne.io/fyne/v2/layout"
	"fyne.io/fyne/v2/widget"
)

// Config stores application configuration
type Config struct {
	ReadOnlySettings map[string]string `json:"readOnlySettings"`
	UI               struct {
		FeedbackFg         string `json:"feedbackFg"`
		FeedbackBg         string `json:"feedbackBg"`
		FeedbackFontSize   int    `json:"feedbackFontSize"`
		SlideshowInterval  int    `json:"slideshowInterval"`
	} `json:"ui"`
	LastRun struct {
		LastGeom string `json:"lastGeom"`
	} `json:"lastRun"`
}

// ImageSet stores information about the current image set
type ImageSet struct {
	DeleteDir   string   `json:"deleteDir"`
	SetPos      int      `json:"setPos"`
	ChangeType  string   `json:"changeType"`
	OrderedList []string `json:"orderedList"`
}

// ImageViewer represents the main application
type ImageViewer struct {
	window       fyne.Window
	imageCanvas  *canvas.Image
	scrollView   *container.Scroll
	infoLabel    *widget.Label
	giantInfo    *widget.Label
	config       *Config
	imageSet     *ImageSet
	
	// Window management
	deviceRes    []int
	windowZoom   float64
	imgZoom      float64
	fullscreen   bool
	lastSize     fyne.Size
	lastPos      fyne.Position
	
	// Scrolling
	scrollingDir [4]bool
	scrollPix    int
	
	// Slideshow
	slideshowActive bool
	slideshowTimer  *time.Timer
	
	// Key tracking for multi-key commands
	lastKeyTime time.Time
	previousKey string
	currentKey  string
}

func main() {
	a := app.New()
	w := a.NewWindow("Timeless Image Viewer")
	
	// Create the image viewer
	viewer := NewImageViewer(w)
	
	// Set content and show
	w.SetContent(viewer.scrollView)
	w.Resize(fyne.NewSize(1280, 720))
	w.ShowAndRun()
	
	// Save config on exit
	viewer.saveConfig()
}

// NewImageViewer creates a new image viewer
func NewImageViewer(window fyne.Window) *ImageViewer {
	// Initialize image viewer
	iv := &ImageViewer{
		window:        window,
		deviceRes:     []int{1920, 1080},
		windowZoom:    1.0,
		imgZoom:       1.0,
		fullscreen:    false,
		scrollingDir:  [4]bool{false, false, false, false},
		scrollPix:     1,
	}
	
	// Load config
	iv.loadConfig()
	
	// Create UI components
	iv.setupUI()
	
	// Set up keyboard shortcuts
	iv.setupKeyboardShortcuts()
	
	// Get images from command line arguments
	iv.getImages()
	
	// Load first image
	if len(iv.imageSet.OrderedList) > 0 {
		iv.loadImage(iv.imageSet.OrderedList[0])
	}
	
	return iv
}

// loadConfig loads the application configuration
func (iv *ImageViewer) loadConfig() {
	iv.config = &Config{}
	
	// Default configuration
	iv.config.ReadOnlySettings = map[string]string{
		"dest-a": "~/AI-Images",
		"dest-d": "~/AI-Documents",
		"dest-f": "~/Family-Photos",
		"dest-w": "~/Work-Photos",
		"dest-t": "/tmp",
	}
	
	iv.config.UI.FeedbackFg = "0.85,0.85,0.85,0.9"
	iv.config.UI.FeedbackBg = "0.05,0.05,0.05,0.3"
	iv.config.UI.FeedbackFontSize = 32
	iv.config.UI.SlideshowInterval = 20
	
	iv.config.LastRun.LastGeom = "1920x1080+0,0"
	
	// Try to load from config file
	configPath := filepath.Join(os.Getenv("HOME"), ".tiviewrc.json")
	data, err := ioutil.ReadFile(configPath)
	if err == nil {
		// Config exists, load it
		json.Unmarshal(data, iv.config)
	} else {
		// Config doesn't exist, create it
		iv.saveConfig()
	}
	
	// Set up the image set
	iv.imageSet = &ImageSet{
		DeleteDir:   filepath.Join(os.Getenv("HOME"), ".Trash"),
		SetPos:      0,
		ChangeType:  "ordered",
		OrderedList: []string{},
	}
}

// saveConfig saves the configuration to file
func (iv *ImageViewer) saveConfig() {
	configPath := filepath.Join(os.Getenv("HOME"), ".tiviewrc.json")
	data, _ := json.MarshalIndent(iv.config, "", "  ")
	ioutil.WriteFile(configPath, data, 0644)
}

// setupUI initializes the UI components
func (iv *ImageViewer) setupUI() {
	// Create image canvas
	iv.imageCanvas = &canvas.Image{
		FillMode: canvas.ImageFillContain,
	}
	
	// Create scroll container
	iv.scrollView = container.NewScroll(container.NewCenter(iv.imageCanvas))
	
	// Create info label
	iv.infoLabel = widget.NewLabel("")
	iv.infoLabel.TextStyle = fyne.TextStyle{
		Bold: true,
	}
	
	// Create giant info label for move destinations
	iv.giantInfo = widget.NewLabel("")
	iv.giantInfo.TextStyle = fyne.TextStyle{
		Bold: true,
	}
	
	// Create overlay for labels
	overlay := container.NewWithoutLayout(
		iv.scrollView,
		container.NewVBox(
			layout.NewSpacer(),
			container.NewHBox(layout.NewSpacer(), iv.giantInfo, layout.NewSpacer()),
			container.NewHBox(layout.NewSpacer(), iv.infoLabel, layout.NewSpacer()),
		),
	)
	
	// Set the content
	iv.window.SetContent(overlay)
	
	// Clear initial labels
	iv.clearInfoLabel()
	iv.clearGiantInfo()
}

// setupKeyboardShortcuts sets up keyboard shortcuts
func (iv *ImageViewer) setupKeyboardShortcuts() {
	iv.window.Canvas().(desktop.Canvas).SetOnKeyDown(func(key *fyne.KeyEvent) {
		iv.handleKeyDown(key)
	})
}

// handleKeyDown processes keyboard input
func (iv *ImageViewer) handleKeyDown(key *fyne.KeyEvent) {
	// Handle navigation keys
	switch key.Name {
	case fyne.KeyUp:
		// Scroll up
		iv.scrollUp()
	case fyne.KeyDown:
		// Scroll down
		iv.scrollDown()
	case fyne.KeyLeft:
		// Scroll left
		iv.scrollLeft()
	case fyne.KeyRight:
		// Scroll right
		iv.scrollRight()
	case fyne.KeyPageDown:
		// Next image
		iv.nextImage("ordered")
	case fyne.KeyPageUp:
		// Previous image
		iv.prevImage("ordered")
	case fyne.KeyHome:
		// First image
		iv.firstImage()
	case fyne.KeyEnd:
		// Last image
		iv.lastImage()
	case fyne.KeyDelete:
		// Delete image
		iv.moveImage(iv.imageSet.DeleteDir)
	}
	
	// Handle other keys
	switch string(key.Name) {
	case "s":
		// Toggle slideshow
		iv.toggleSlideshow()
	case "x":
		// Fit to window
		iv.fitToWindow()
	case "z", "1":
		// 1:1 zoom
		iv.zoomOneToOne()
	case "+", "=":
		// Zoom in
		iv.zoomIn()
	case "-", "_":
		// Zoom out
		iv.zoomOut()
	case "2":
		// Zoom to 2x
		iv.zoomTo(2.0)
	case "3":
		// Zoom to 3x
		iv.zoomTo(3.0)
	case "4":
		// Zoom to 4x
		iv.zoomTo(4.0)
	case ".", ">":
		// Next random image
		iv.nextImage("random")
	case ",", "<":
		// Previous random image
		iv.prevImage("random")
	case "]":
		// Next shuffled image
		iv.nextImage("shuffled")
	case "[":
		// Previous shuffled image
		iv.prevImage("shuffled")
	case "'", "\"":
		// Next image
		iv.nextImage("ordered")
	case ";", ":":
		// Previous image
		iv.prevImage("ordered")
	case "f":
		// Toggle fullscreen
		iv.toggleFullscreen()
	case "q":
		// Prepare for quit
		now := time.Now()
		if now.Sub(iv.lastKeyTime) < time.Second && iv.previousKey == "q" {
			iv.window.Close()
		} else {
			iv.showInfo("Press q again to quit")
			iv.previousKey = "q"
			iv.lastKeyTime = now
		}
	case "m":
		// Prepare for move
		now := time.Now()
		if now.Sub(iv.lastKeyTime) < time.Second {
			// Handle second key for move
			iv.handleMoveCommand(iv.currentKey)
		} else {
			iv.showDestinations()
			iv.previousKey = "m"
			iv.lastKeyTime = now
		}
	case "c":
		// Prepare for copy
		now := time.Now()
		if now.Sub(iv.lastKeyTime) < time.Second {
			// Handle second key for copy
			iv.handleCopyCommand(iv.currentKey)
		} else {
			iv.showDestinations()
			iv.previousKey = "c"
			iv.lastKeyTime = now
		}
	default:
		// Store key for multi-key commands
		iv.currentKey = string(key.Name)
	}
}

// getImages collects images from command line arguments or current directory
func (iv *ImageViewer) getImages() {
	// Clear the image list
	iv.imageSet.OrderedList = []string{}
	
	// Get image paths
	args := os.Args[1:]
	if len(args) == 0 {
		args = []string{"."}
	}
	
	for _, arg := range args {
		info, err := os.Stat(arg)
		if err != nil {
			continue
		}
		
		if info.IsDir() {
			// Add images from directory
			files, _ := ioutil.ReadDir(arg)
			for _, file := range files {
				if !file.IsDir() {
					name := strings.ToLower(file.Name())
					if strings.HasSuffix(name, ".jpg") || strings.HasSuffix(name, ".jpeg") || 
					   strings.HasSuffix(name, ".png") {
						iv.imageSet.OrderedList = append(iv.imageSet.OrderedList, filepath.Join(arg, file.Name()))
					}
				}
			}
		} else {
			// Add single file
			name := strings.ToLower(arg)
			if strings.HasSuffix(name, ".jpg") || strings.HasSuffix(name, ".jpeg") || 
			   strings.HasSuffix(name, ".png") {
				iv.imageSet.OrderedList = append(iv.imageSet.OrderedList, arg)
			}
		}
	}
	
	// Sort the list
	sort.Strings(iv.imageSet.OrderedList)
}

// loadImage loads an image from a file path
func (iv *ImageViewer) loadImage(path string) {
	iv.imageCanvas.File = path
	iv.imageCanvas.Refresh()
	iv.window.SetTitle(fmt.Sprintf("Timeless Image Viewer - %s", filepath.Base(path)))
}

// nextImage moves to the next image
func (iv *ImageViewer) nextImage(changeType string) {
	if len(iv.imageSet.OrderedList) == 0 {
		return
	}
	
	// Change ordering type if needed
	if iv.imageSet.ChangeType != changeType {
		iv.changeImageOrder(changeType)
	}
	
	// Move to next image
	iv.imageSet.SetPos = (iv.imageSet.SetPos + 1) % len(iv.imageSet.OrderedList)
	iv.loadImage(iv.imageSet.OrderedList[iv.imageSet.SetPos])
}

// prevImage moves to the previous image
func (iv *ImageViewer) prevImage(changeType string) {
	if len(iv.imageSet.OrderedList) == 0 {
		return
	}
	
	// Change ordering type if needed
	if iv.imageSet.ChangeType != changeType {
		iv.changeImageOrder(changeType)
	}
	
	// Move to previous image
	iv.imageSet.SetPos--
	if iv.imageSet.SetPos < 0 {
		iv.imageSet.SetPos = len(iv.imageSet.OrderedList) - 1
	}
	iv.loadImage(iv.imageSet.OrderedList[iv.imageSet.SetPos])
}

// firstImage moves to the first image
func (iv *ImageViewer) firstImage() {
	if len(iv.imageSet.OrderedList) == 0 {
		return
	}
	
	iv.imageSet.SetPos = 0
	iv.loadImage(iv.imageSet.OrderedList[iv.imageSet.SetPos])
}

// lastImage moves to the last image
func (iv *ImageViewer) lastImage() {
	if len(iv.imageSet.OrderedList) == 0 {
		return
	}
	
	iv.imageSet.SetPos = len(iv.imageSet.OrderedList) - 1
	iv.loadImage(iv.imageSet.OrderedList[iv.imageSet.SetPos])
}

// changeImageOrder changes the ordering of images
func (iv *ImageViewer) changeImageOrder(changeType string) {
	if len(iv.imageSet.OrderedList) == 0 {
		return
	}
	
	// Save current image
	currentImage := iv.imageSet.OrderedList[iv.imageSet.SetPos]
	
	// Change ordering
	switch changeType {
	case "ordered":
		sort.Strings(iv.imageSet.OrderedList)
	case "shuffled":
		// First sort
		sort.Strings(iv.imageSet.OrderedList)
		
		// Then shuffle in groups of 20
		for i := 0; i < len(iv.imageSet.OrderedList); i++ {
			var swapIndex int
			if i < len(iv.imageSet.OrderedList) - 20 {
				swapIndex = i + rand.Intn(20) + 1
			} else {
				swapIndex = rand.Intn(len(iv.imageSet.OrderedList) - i)
			}
			iv.imageSet.OrderedList[i], iv.imageSet.OrderedList[swapIndex] = 
				iv.imageSet.OrderedList[swapIndex], iv.imageSet.OrderedList[i]
		}
	case "random":
		// Full randomization
		rand.Shuffle(len(iv.imageSet.OrderedList), func(i, j int) {
			iv.imageSet.OrderedList[i], iv.imageSet.OrderedList[j] = 
				iv.imageSet.OrderedList[j], iv.imageSet.OrderedList[i]
		})
	}
	
	// Find current image in new ordering
	for i, img := range iv.imageSet.OrderedList {
		if img == currentImage {
			iv.imageSet.SetPos = i
			break
		}
	}
	
	iv.imageSet.ChangeType = changeType
}

// scrollUp scrolls the image up
func (iv *ImageViewer) scrollUp() {
	iv.scrollView.Offset.Y -= float32(iv.scrollPix)
	iv.scrollView.Refresh()
}

// scrollDown scrolls the image down
func (iv *ImageViewer) scrollDown() {
	iv.scrollView.Offset.Y += float32(iv.scrollPix)
	iv.scrollView.Refresh()
}

// scrollLeft scrolls the image left
func (iv *ImageViewer) scrollLeft() {
	iv.scrollView.Offset.X -= float32(iv.scrollPix)
	iv.scrollView.Refresh()
}

// scrollRight scrolls the image right
func (iv *ImageViewer) scrollRight() {
	iv.scrollView.Offset.X += float32(iv.scrollPix)
	iv.scrollView.Refresh()
}

// zoomIn increases zoom level
func (iv *ImageViewer) zoomIn() {
	iv.imgZoom *= 1.1
	iv.updateZoom()
}

// zoomOut decreases zoom level
func (iv *ImageViewer) zoomOut() {
	iv.imgZoom *= 0.9
	iv.updateZoom()
}

// zoomTo sets a specific zoom level
func (iv *ImageViewer) zoomTo(zoom float64) {
	iv.imgZoom = zoom
	iv.updateZoom()
}

// zoomOneToOne sets zoom to 1:1
func (iv *ImageViewer) zoomOneToOne() {
	iv.imgZoom = 1.0
	iv.updateZoom()
}

// fitToWindow resizes the image to fit the window
func (iv *ImageViewer) fitToWindow() {
	iv.imageCanvas.FillMode = canvas.ImageFillContain
	iv.imageCanvas.Refresh()
}

// updateZoom applies the current zoom level
func (iv *ImageViewer) updateZoom() {
	// Apply zoom to image
	size := iv.imageCanvas.Size()
	iv.imageCanvas.SetMinSize(fyne.NewSize(
		float32(float64(size.Width) * iv.imgZoom),
		float32(float64(size.Height) * iv.imgZoom),
	))
	iv.imageCanvas.Refresh()
}

// toggleFullscreen switches between windowed and fullscreen modes
func (iv *ImageViewer) toggleFullscreen() {
	if iv.fullscreen {
		iv.window.SetFullScreen(false)
		iv.fullscreen = false
	} else {
		iv.lastSize = iv.window.Content().Size()
		iv.window.SetFullScreen(true)
		iv.fullscreen = true
	}
}

// toggleSlideshow toggles the slideshow mode
func (iv *ImageViewer) toggleSlideshow() {
	if iv.slideshowActive {
		// Stop slideshow
		if iv.slideshowTimer != nil {
			iv.slideshowTimer.Stop()
		}
		iv.slideshowActive = false
		iv.showInfo("Slideshow stopped")
	} else {
		// Start slideshow
		iv.slideshowActive = true
		interval := time.Duration(iv.config.UI.SlideshowInterval) * time.Second
		iv.showInfo(fmt.Sprintf("Slideshow started (interval: %d seconds)", iv.config.UI.SlideshowInterval))
		
		// Run immediately then schedule
		iv.nextImage(iv.imageSet.ChangeType)
		
		iv.slideshowTimer = time.AfterFunc(interval, func() {
			// This runs in a goroutine already
			if iv.slideshowActive {
				// Need to run on main thread, but there's no clean way
				// to do this in Fyne without QueueEvent, so we'll just
				// make this synchronous for now
				iv.nextImage(iv.imageSet.ChangeType)
				iv.toggleSlideshow() // Re-schedule
			}
		})
	}
}

// moveImage moves the current image to a destination directory
func (iv *ImageViewer) moveImage(destDir string) {
	if len(iv.imageSet.OrderedList) == 0 {
		return
	}
	
	srcPath := iv.imageSet.OrderedList[iv.imageSet.SetPos]
	destPath := filepath.Join(destDir, filepath.Base(srcPath))
	
	// Check if destination exists
	if _, err := os.Stat(destPath); err == nil {
		iv.showInfo(fmt.Sprintf("Image already exists in %s", destDir))
		return
	}
	
	// Move the file
	if err := os.Rename(srcPath, destPath); err != nil {
		iv.showInfo(fmt.Sprintf("Error moving image: %v", err))
		return
	}
	
	// Remove from list and load next image
	iv.imageSet.OrderedList = append(
		iv.imageSet.OrderedList[:iv.imageSet.SetPos],
		iv.imageSet.OrderedList[iv.imageSet.SetPos+1:]...,
	)
	
	if len(iv.imageSet.OrderedList) > 0 {
		if iv.imageSet.SetPos >= len(iv.imageSet.OrderedList) {
			iv.imageSet.SetPos = 0
		}
		iv.loadImage(iv.imageSet.OrderedList[iv.imageSet.SetPos])
	}
	
	iv.showInfo(fmt.Sprintf("Moved to %s", destDir))
}

// copyImage copies the current image to a destination directory
func (iv *ImageViewer) copyImage(destDir string) {
	if len(iv.imageSet.OrderedList) == 0 {
		return
	}
	
	srcPath := iv.imageSet.OrderedList[iv.imageSet.SetPos]
	destPath := filepath.Join(destDir, filepath.Base(srcPath))
	
	// Check if destination exists
	if _, err := os.Stat(destPath); err == nil {
		iv.showInfo(fmt.Sprintf("Image already exists in %s", destDir))
		return
	}
	
	// Copy the file
	srcFile, err := ioutil.ReadFile(srcPath)
	if err != nil {
		iv.showInfo(fmt.Sprintf("Error reading image: %v", err))
		return
	}
	
	if err := ioutil.WriteFile(destPath, srcFile, 0644); err != nil {
		iv.showInfo(fmt.Sprintf("Error copying image: %v", err))
		return
	}
	
	iv.showInfo(fmt.Sprintf("Copied to %s", destDir))
}

// handleMoveCommand processes the second key of a move command
func (iv *ImageViewer) handleMoveCommand(key string) {
	destKey := fmt.Sprintf("dest-%s", key)
	if dest, ok := iv.config.ReadOnlySettings[destKey]; ok {
		expandedPath := strings.Replace(dest, "~", os.Getenv("HOME"), 1)
		iv.moveImage(expandedPath)
	} else {
		iv.showInfo(fmt.Sprintf("No destination defined for key '%s'", key))
	}
}

// handleCopyCommand processes the second key of a copy command
func (iv *ImageViewer) handleCopyCommand(key string) {
	destKey := fmt.Sprintf("dest-%s", key)
	if dest, ok := iv.config.ReadOnlySettings[destKey]; ok {
		expandedPath := strings.Replace(dest, "~", os.Getenv("HOME"), 1)
		iv.copyImage(expandedPath)
	} else {
		iv.showInfo(fmt.Sprintf("No destination defined for key '%s'", key))
	}
}

// showInfo displays information in the info label
func (iv *ImageViewer) showInfo(text string) {
	iv.infoLabel.SetText(text)
	iv.infoLabel.Show()
	
	// Auto-hide after a delay
	go func() {
		time.Sleep(2 * time.Second)
		// Run on main thread
		iv.window.Canvas().Refresh(iv.infoLabel)
		iv.clearInfoLabel()
	}()
}

// clearInfoLabel hides the info label
func (iv *ImageViewer) clearInfoLabel() {
	iv.infoLabel.SetText("")
	iv.infoLabel.Hide()
}

// showDestinations shows available destinations in the giant info label
func (iv *ImageViewer) showDestinations() {
	var destinations []string
	for key, value := range iv.config.ReadOnlySettings {
		if strings.HasPrefix(key, "dest-") {
			destinations = append(destinations, fmt.Sprintf("%s: %s", key[5:], value))
		}
	}
	
	iv.giantInfo.SetText(fmt.Sprintf("Available destinations:\n%s", strings.Join(destinations, "\n")))
	iv.giantInfo.Show()
	
	// Auto-hide after a delay
	go func() {
		time.Sleep(2 * time.Second)
		// Run on main thread
		iv.window.Canvas().Refresh(iv.giantInfo)
		iv.clearGiantInfo()
	}()
}

// clearGiantInfo hides the giant info label
func (iv *ImageViewer) clearGiantInfo() {
	iv.giantInfo.SetText("")
	iv.giantInfo.Hide()
}
