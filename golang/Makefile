# Golang CLI Makefile

# Variables
BINARY_NAME=timeless-imageview
BUILD_DIR=build
SRC_DIR=.
PACKAGE_PATH=github.com/time-less-ness/timeless-imgview/golang

# Set the default goal when make is run without arguments
.DEFAULT_GOAL := help

# Help command
.PHONY: help
help:
	@echo "Adviser CLI Build System"
	@echo ""
	@echo "Usage:"
	@echo "  make build    - Build the application"
	@echo "  make clean    - Remove build artifacts"
	@echo "  make test     - Run tests"
	@echo "  make lint     - Run linting checks"
	@echo "  make fmt      - Format the code"
	@echo "  make install  - Install the application locally"
	@echo "  make all      - Clean, format, lint, test, and build"

# Build command
.PHONY: build
build: linux win mac
	@echo "Building..."
	@mkdir -p $(BUILD_DIR)

.PHONY: linux
linux:
	@echo "Building Linux (arm64)."
	GOOS=linux GOARCH=arm64 go build -o $(BUILD_DIR)/$(BINARY_NAME)-linux-arm64 $(SRC_DIR)
	@echo "Building Linux (amd64)."
	GOOS=linux GOARCH=amd64 go build -o $(BUILD_DIR)/$(BINARY_NAME)-linux-amd64 $(SRC_DIR)

.PHONY: mac
mac:
	@echo "Building macOS (arm64, Apple Silicon)."
	GOOS=darwin GOARCH=arm64 go build -o $(BUILD_DIR)/$(BINARY_NAME)-darwin-arm64 $(SRC_DIR)
	@echo "Building macOS (amd64)."
	GOOS=darwin GOARCH=amd64 go build -o $(BUILD_DIR)/$(BINARY_NAME)-darwin-amd64 $(SRC_DIR)

.PHONY: win
win:
	@echo "Building Windows (arm64)."
	GOOS=windows GOARCH=arm64 go build -o $(BUILD_DIR)/$(BINARY_NAME)-windows-arm64.exe $(SRC_DIR)
	@echo "Building Windows (amd64)."
	GOOS=windows GOARCH=amd64 go build -o $(BUILD_DIR)/$(BINARY_NAME)-windows-amd64.exe $(SRC_DIR)

# Install command
.PHONY: install
install:
	@echo "Installing..."
	go install

# Clean command
.PHONY: clean
clean:
	@echo "Cleaning..."
	@rm -rf $(BUILD_DIR)
	@go clean

# Test command
.PHONY: test
test:
	@echo "Running tests..."
	go test ./...

# Lint command
.PHONY: lint
lint:
	@echo "Linting..."
	@if command -v golangci-lint > /dev/null; then \
		golangci-lint run ./...; \
	else \
		echo "golangci-lint not installed. Run: go install github.com/golangci/golangci-lint/cmd/golangci-lint@latest"; \
		exit 1; \
	fi

# Format command
.PHONY: fmt
fmt:
	@echo "Formatting..."
	go fmt ./...
	@echo "Removing errant whitespace..."
	@find . -name '*.go' -exec sed -i '' 's/ $$//g' {} \;
	@echo "Do \`git diff\` to understand any changes fmt did."

# Run all tasks
.PHONY: all
all: clean fmt lint test build
