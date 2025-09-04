.PHONY: build run clean test

# Build the application
build:
	go build -o emailer main.go

# Run the application (example)
run:
	./emailer "Example Company" "John Doe" "john.doe@example.com"

# Clean build artifacts
clean:
	rm -f emailer

# Run tests
test:
	go test ./...

# Install dependencies
deps:
	go mod download
	go mod tidy

# Build for different platforms
build-linux:
	GOOS=linux GOARCH=amd64 go build -o emailer-linux main.go

build-windows:
	GOOS=windows GOARCH=amd64 go build -o emailer-windows.exe main.go

build-darwin:
	GOOS=darwin GOARCH=amd64 go build -o emailer-darwin main.go

# Build all platforms
build-all: build-linux build-windows build-darwin

# Format code
fmt:
	go fmt ./...

# Run linter
lint:
	golangci-lint run

# Generate go.sum
sum:
	go mod tidy
	go mod download
