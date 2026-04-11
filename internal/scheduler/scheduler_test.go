package scheduler

import (
	"os"
	"path/filepath"
	"testing"
	"time"
)

// csvFixture matches the fixture used in tests/test_schedule_helper.py
const csvFixture = `DAY,START_TIME,END_TIME
0, 10:00, 11:00
0, 14:00, 14:30
1, 10:00, 11:00
1, 14:00, 14:30
2, 10:00, 11:00
2, 14:00, 14:30
3, 10:00, 11:00
3, 14:00, 14:30
4, 10:00, 11:00
`

func writeCSV(t *testing.T, content string) string {
	t.Helper()
	path := filepath.Join(t.TempDir(), "schedule.csv")
	if err := os.WriteFile(path, []byte(content), 0644); err != nil {
		t.Fatalf("failed to write csv: %v", err)
	}
	return path
}

func parsedFixture(t *testing.T) *DayRanges {
	t.Helper()
	ranges, err := ParseTimeRangesCSV(writeCSV(t, csvFixture))
	if err != nil {
		t.Fatalf("ParseTimeRangesCSV: %v", err)
	}
	return ranges
}

var laTZ = func() *time.Location {
	loc, err := time.LoadLocation("America/Los_Angeles")
	if err != nil {
		panic(err)
	}
	return loc
}()

// at returns a time.Time in laTZ for the given date/hour/minute.
func at(year, month, day, hour, minute int) time.Time {
	return time.Date(year, time.Month(month), day, hour, minute, 0, 0, laTZ)
}

func TestParseTimeRangesCSV(t *testing.T) {
	csv := `DAY,START_TIME,END_TIME
0,09:00,12:00
0,13:00,15:00
1,10:00,14:00
`
	ranges, err := ParseTimeRangesCSV(writeCSV(t, csv))
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	// Monday (day 0) should have two ranges
	if len(ranges[0]) != 2 {
		t.Fatalf("expected 2 ranges for Monday, got %d", len(ranges[0]))
	}
	assertTimeRange(t, ranges[0][0], 9, 0, 12, 0)
	assertTimeRange(t, ranges[0][1], 13, 0, 15, 0)

	// Tuesday (day 1) should have one range
	if len(ranges[1]) != 1 {
		t.Fatalf("expected 1 range for Tuesday, got %d", len(ranges[1]))
	}
	assertTimeRange(t, ranges[1][0], 10, 0, 14, 0)

	// Wednesday through Sunday should be empty
	for day := 2; day < 7; day++ {
		if len(ranges[day]) != 0 {
			t.Errorf("expected 0 ranges for day %d, got %d", day, len(ranges[day]))
		}
	}
}

func assertTimeRange(t *testing.T, tr TimeRange, startH, startM, endH, endM int) {
	t.Helper()
	if tr.Start.Hour() != startH || tr.Start.Minute() != startM {
		t.Errorf("start: got %02d:%02d, want %02d:%02d", tr.Start.Hour(), tr.Start.Minute(), startH, startM)
	}
	if tr.End.Hour() != endH || tr.End.Minute() != endM {
		t.Errorf("end: got %02d:%02d, want %02d:%02d", tr.End.Hour(), tr.End.Minute(), endH, endM)
	}
}

func TestParseTimeRangesCSV_Empty(t *testing.T) {
	_, err := ParseTimeRangesCSV(writeCSV(t, "DAY,START_TIME,END_TIME\n"))
	if err != nil {
		t.Errorf("expected no error for empty csv (header only), got %v", err)
	}
}

func TestParseTimeRangesCSV_InvalidFile(t *testing.T) {
	_, err := ParseTimeRangesCSV("/nonexistent/path/schedule.csv")
	if err == nil {
		t.Error("expected error for missing file")
	}
}

// TestGetScheduledSendTime mirrors test_get_scheduled_send_time_within_range from Python.
// All times are in America/Los_Angeles.
//
// The test cases are:
//   Monday 9:15 AM  → between 10:00–11:00 (next window today)
//   Monday 10:30 AM → nil (currently within 10:00–11:00 window)
//   Monday 12:15 PM → between 14:00–14:30 (next window today)
//   Monday 3:00 PM  → between 10:00–11:00 the next day (Tuesday)
//   Friday 6:00 PM  → between 10:00–11:00 the following Monday
func TestGetScheduledSendTime(t *testing.T) {
	dayRanges := parsedFixture(t)

	cases := []struct {
		name    string
		now     time.Time
		wantNil bool      // true when current time is inside an allowed window
		wantMin time.Time // inclusive lower bound
		wantMax time.Time // exclusive upper bound
	}{
		{
			// Monday 9:15 AM — not yet in the 10:00-11:00 window, so schedule within it
			name:    "Monday 9:15 before first window",
			now:     at(2025, 3, 18, 9, 15),
			wantMin: at(2025, 3, 18, 10, 0),
			wantMax: at(2025, 3, 18, 11, 0),
		},
		{
			// Monday 10:30 AM — inside the 10:00-11:00 window
			name:    "Monday 10:30 inside window",
			now:     at(2025, 3, 18, 10, 30),
			wantNil: true,
		},
		{
			// Monday 12:15 PM — past first window, before second
			name:    "Monday 12:15 between windows",
			now:     at(2025, 3, 18, 12, 15),
			wantMin: at(2025, 3, 18, 14, 0),
			wantMax: at(2025, 3, 18, 14, 30),
		},
		{
			// Monday 3:00 PM — past all windows today
			name:    "Monday 15:00 past all windows",
			now:     at(2025, 3, 18, 15, 0),
			wantMin: at(2025, 3, 19, 10, 0),
			wantMax: at(2025, 3, 19, 11, 0),
		},
		{
			// Friday 6:00 PM — no windows Sat/Sun, wraps to Monday
			name:    "Friday 18:00 wraps to next Monday",
			now:     at(2025, 3, 21, 18, 0),
			wantMin: at(2025, 3, 24, 10, 0),
			wantMax: at(2025, 3, 24, 11, 0),
		},
	}

	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			result, err := GetScheduledSendTime(dayRanges, "America/Los_Angeles", &tc.now)
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}

			if tc.wantNil {
				if result != nil {
					t.Errorf("expected nil (in-range), got %v", result)
				}
				return
			}

			if result == nil {
				t.Fatal("expected non-nil scheduled time")
			}
			if result.Before(tc.wantMin) || !result.Before(tc.wantMax) {
				t.Errorf("scheduled time %v not in [%v, %v)", result, tc.wantMin, tc.wantMax)
			}
		})
	}
}

func TestGetScheduledSendTime_NoRanges(t *testing.T) {
	empty := &DayRanges{}
	now := at(2025, 3, 18, 10, 0)
	_, err := GetScheduledSendTime(empty, "America/Los_Angeles", &now)
	if err == nil {
		t.Error("expected error when no time ranges configured")
	}
}

func TestGetScheduledSendTime_InvalidTimezone(t *testing.T) {
	dayRanges := parsedFixture(t)
	now := time.Date(2025, 3, 18, 10, 30, 0, 0, time.UTC)
	// Should not error — falls back to UTC
	_, err := GetScheduledSendTime(dayRanges, "Invalid/Timezone", &now)
	if err != nil {
		t.Errorf("unexpected error with invalid timezone: %v", err)
	}
}
