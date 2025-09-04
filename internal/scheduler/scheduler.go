package scheduler

import (
	"encoding/csv"
	"fmt"
	"log"
	"math/rand"
	"os"
	"strconv"
	"strings"
	"time"
)

// TimeRange represents a time range for scheduling
type TimeRange struct {
	Start time.Time
	End   time.Time
}

// DayRanges represents time ranges for each day of the week (0=Monday, 6=Sunday)
type DayRanges [7][]TimeRange

// ParseTimeRangesCSV parses CSV data containing allowed time ranges
func ParseTimeRangesCSV(csvPath string) (*DayRanges, error) {
	file, err := os.Open(csvPath)
	if err != nil {
		return nil, fmt.Errorf("failed to open CSV file: %v", err)
	}
	defer file.Close()

	reader := csv.NewReader(file)
	records, err := reader.ReadAll()
	if err != nil {
		return nil, fmt.Errorf("failed to read CSV: %v", err)
	}

	if len(records) == 0 {
		return nil, fmt.Errorf("CSV file is empty")
	}

	// Skip header row
	records = records[1:]

	dayRanges := &DayRanges{}

	for _, record := range records {
		if len(record) < 3 {
			continue
		}

		day, err := strconv.Atoi(strings.TrimSpace(record[0]))
		if err != nil {
			log.Printf("Warning: invalid day value: %s", record[0])
			continue
		}

		if day < 0 || day > 6 {
			log.Printf("Warning: day value out of range (0-6): %d", day)
			continue
		}

		startTime, err := parseTime(record[1])
		if err != nil {
			log.Printf("Warning: invalid start time: %s", record[1])
			continue
		}

		endTime, err := parseTime(record[2])
		if err != nil {
			log.Printf("Warning: invalid end time: %s", record[2])
			continue
		}

		timeRange := TimeRange{
			Start: startTime,
			End:   endTime,
		}

		dayRanges[day] = append(dayRanges[day], timeRange)
	}

	// Sort each day's ranges by start time
	for day := 0; day < 7; day++ {
		sortTimeRanges(dayRanges[day])
	}

	return dayRanges, nil
}

// GetScheduledSendTime determines when to send an email based on current time and allowed ranges
func GetScheduledSendTime(dayRanges *DayRanges, timezone string) (*time.Time, error) {
	loc, err := time.LoadLocation(timezone)
	if err != nil {
		log.Printf("Warning: invalid timezone %s, using UTC", timezone)
		loc = time.UTC
	}

	now := time.Now().In(loc)
	currentDay := int(now.Weekday())
	if currentDay == 0 { // Sunday
		currentDay = 6
	} else {
		currentDay-- // Convert to 0-based (Monday=0)
	}

	currentTime := time.Date(2000, 1, 1, now.Hour(), now.Minute(), 0, 0, time.UTC)

	// Check if current time is within an allowed range for today
	for _, timeRange := range dayRanges[currentDay] {
		if timeRange.Start.Before(currentTime) && currentTime.Before(timeRange.End) {
			// Current time is in an allowed range, return nil to indicate send now
			return nil, nil
		}
	}

	// Find the next available time range
	var nextTimeRange *TimeRange
	var addDays int

	// First check remaining ranges today
	for _, timeRange := range dayRanges[currentDay] {
		if timeRange.Start.After(currentTime) {
			nextTimeRange = &timeRange
			break
		}
	}

	// If no ranges found today, look for the next available day
	if nextTimeRange == nil {
		for dayOffset := 1; dayOffset <= 7; dayOffset++ {
			nextDay := (currentDay + dayOffset) % 7
			if len(dayRanges[nextDay]) > 0 {
				nextTimeRange = &dayRanges[nextDay][0]
				addDays = dayOffset
				break
			}
		}
	}

	if nextTimeRange == nil {
		return nil, fmt.Errorf("no allowed time ranges found")
	}

	// Find a random time within the range
	randomTime := getRandomTimeInRange(nextTimeRange.Start, nextTimeRange.End)
	
	// Calculate the target date
	targetDate := now.AddDate(0, 0, addDays)
	targetDateTime := time.Date(
		targetDate.Year(), targetDate.Month(), targetDate.Day(),
		randomTime.Hour(), randomTime.Minute(), 0, 0, loc,
	)

	return &targetDateTime, nil
}

// parseTime parses a time string in HH:MM format
func parseTime(timeStr string) (time.Time, error) {
	parts := strings.Split(strings.TrimSpace(timeStr), ":")
	if len(parts) != 2 {
		return time.Time{}, fmt.Errorf("invalid time format: %s", timeStr)
	}

	hour, err := strconv.Atoi(parts[0])
	if err != nil {
		return time.Time{}, fmt.Errorf("invalid hour: %s", parts[0])
	}

	minute, err := strconv.Atoi(parts[1])
	if err != nil {
		return time.Time{}, fmt.Errorf("invalid minute: %s", parts[1])
	}

	if hour < 0 || hour > 23 || minute < 0 || minute > 59 {
		return time.Time{}, fmt.Errorf("time out of range: %s", timeStr)
	}

	return time.Date(2000, 1, 1, hour, minute, 0, 0, time.UTC), nil
}

// sortTimeRanges sorts time ranges by start time
func sortTimeRanges(ranges []TimeRange) {
	for i := 0; i < len(ranges)-1; i++ {
		for j := i + 1; j < len(ranges); j++ {
			if ranges[i].Start.After(ranges[j].Start) {
				ranges[i], ranges[j] = ranges[j], ranges[i]
			}
		}
	}
}

// getRandomTimeInRange returns a random time within the given range
func getRandomTimeInRange(start, end time.Time) time.Time {
	startSeconds := start.Hour()*3600 + start.Minute()*60
	endSeconds := end.Hour()*3600 + end.Minute()*60
	
	randomSeconds := rand.Intn(endSeconds-startSeconds) + startSeconds
	randomHour := randomSeconds / 3600
	randomMinute := (randomSeconds % 3600) / 60
	
	return time.Date(2000, 1, 1, randomHour, randomMinute, 0, 0, time.UTC)
}
