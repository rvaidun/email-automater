// Package logger provides a small leveled, colored logger for the emailer CLI.
//
// Levels: DEBUG < INFO < WARN < ERROR < FATAL. Fatal exits the process with
// status 1 after logging. The minimum level can be set with the LOG_LEVEL
// environment variable (debug|info|warn|error). Colors are auto-disabled when
// stderr is not a terminal or when NO_COLOR is set (see https://no-color.org).
package logger

import (
	"fmt"
	"io"
	"os"
	"strings"
	"sync"
	"time"
)

type Level int

const (
	LevelDebug Level = iota
	LevelInfo
	LevelWarn
	LevelError
	LevelFatal
)

const (
	ansiReset   = "\033[0m"
	ansiGray    = "\033[90m"
	ansiCyan    = "\033[36m"
	ansiYellow  = "\033[33m"
	ansiRed     = "\033[31m"
	ansiBoldRed = "\033[1;31m"
)

var (
	mu       sync.Mutex
	out      io.Writer = os.Stderr
	minLevel           = LevelInfo
	useColor           = true
	exitFn             = os.Exit
)

func init() {
	if fi, err := os.Stderr.Stat(); err == nil {
		useColor = (fi.Mode() & os.ModeCharDevice) != 0
	}
	if os.Getenv("NO_COLOR") != "" {
		useColor = false
	}
	if lvl := os.Getenv("LOG_LEVEL"); lvl != "" {
		if l, ok := parseLevel(lvl); ok {
			minLevel = l
		}
	}
}

func parseLevel(s string) (Level, bool) {
	switch strings.ToLower(strings.TrimSpace(s)) {
	case "debug":
		return LevelDebug, true
	case "info":
		return LevelInfo, true
	case "warn", "warning":
		return LevelWarn, true
	case "error":
		return LevelError, true
	case "fatal":
		return LevelFatal, true
	}
	return LevelInfo, false
}

func meta(level Level) (label, color string) {
	switch level {
	case LevelDebug:
		return "DEBUG", ansiGray
	case LevelInfo:
		return "INFO ", ansiCyan
	case LevelWarn:
		return "WARN ", ansiYellow
	case LevelError:
		return "ERROR", ansiRed
	case LevelFatal:
		return "FATAL", ansiBoldRed
	}
	return "?????", ""
}

func write(level Level, format string, args ...any) {
	if level < minLevel {
		return
	}
	label, color := meta(level)
	ts := time.Now().Format("2006/01/02 15:04:05")
	msg := fmt.Sprintf(format, args...)

	mu.Lock()
	defer mu.Unlock()
	if useColor {
		fmt.Fprintf(out, "%s%s [%s]%s %s\n", color, ts, label, ansiReset, msg)
	} else {
		fmt.Fprintf(out, "%s [%s] %s\n", ts, label, msg)
	}
}

func Debug(format string, args ...any) { write(LevelDebug, format, args...) }
func Info(format string, args ...any)  { write(LevelInfo, format, args...) }
func Warn(format string, args ...any)  { write(LevelWarn, format, args...) }
func Error(format string, args ...any) { write(LevelError, format, args...) }

// Fatal logs at FATAL level then exits with status 1.
func Fatal(format string, args ...any) {
	write(LevelFatal, format, args...)
	exitFn(1)
}
