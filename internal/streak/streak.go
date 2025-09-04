package streak

import (
	"bytes"
	"fmt"
	"log"
	"net/http"
	"net/url"
	"strconv"
	"strings"
	"time"
)

// SendLaterConfig contains the configuration for scheduling emails
type SendLaterConfig struct {
	Token        string
	ToAddress    string
	Subject      string
	ThreadID     string
	DraftID      string
	SendDate     time.Time
	IsTracked    bool
	EmailAddress string
}

// scheduleHeaders contains the headers for Streak API requests
var scheduleHeaders = map[string]string{
	"accept":                    "*/*",
	"accept-language":           "en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7",
	"content-type":              "application/x-www-form-urlencoded",
	"origin":                    "https://mail.google.com",
	"priority":                  "u=1, i",
	"referer":                   "https://mail.google.com/",
	"sec-ch-ua":                 `"Chromium";v="134", "Not:A-Brand";v="24", "Google Chrome";v="134"`,
	"sec-ch-ua-arch":            `"arm"`,
	"sec-ch-ua-bitness":         `"64"`,
	"sec-ch-ua-form-factors":    `"Desktop"`,
	"sec-ch-ua-full-version":    `"134.0.6998.118"`,
	"sec-ch-ua-full-version-list": `"Chromium";v="134.0.6998.118", "Not:A-Brand";v="24.0.0.0", "Google Chrome";v="134.0.6998.118"`,
	"sec-ch-ua-mobile":          "?0",
	"sec-ch-ua-model":           `""`,
	"sec-ch-ua-platform":        `"macOS"`,
	"sec-ch-ua-platform-version": `"13.6.3"`,
	"sec-ch-ua-wow64":           "?0",
	"sec-fetch-dest":            "empty",
	"sec-fetch-mode":            "cors",
	"sec-fetch-site":            "cross-site",
	"user-agent":                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36",
	"x-streak-web-client":       "true",
	"x-streak-web-extension-id": "pnnfemgpilpdaojpnkjdgfgbnnjojfik",
	"x-streak-web-extension-version": "6.98",
	"x-streak-web-retry-count":  "0",
}

// ScheduleSendLater schedules an email to be sent later using Streak
func ScheduleSendLater(config *SendLaterConfig) error {
	// Set authorization header
	headers := make(map[string]string)
	for k, v := range scheduleHeaders {
		headers[k] = v
	}
	headers["authorization"] = "Bearer " + config.Token

	// Convert send date to UTC timestamp in milliseconds
	sendDateUTC := config.SendDate.UTC()
	timestamp := strconv.FormatInt(sendDateUTC.UnixMilli(), 10)

	// Prepare form data
	formData := url.Values{}
	formData.Set("threadId", config.ThreadID)
	formData.Set("draftId", config.DraftID)
	formData.Set("sendDate", timestamp)
	formData.Set("subject", config.Subject)
	formData.Set("sendLaterType", "NEW_MESSAGE")
	formData.Set("isTracked", strings.ToLower(strconv.FormatBool(config.IsTracked)))
	formData.Set("shouldBox", "false")
	formData.Set("snippetKeyList", "[]")
	formData.Set("toAddresses", fmt.Sprintf(`["%s"]`, config.ToAddress))

	// Create request
	req, err := http.NewRequest("POST", "https://api.streak.com/api/v2/sendlaters", bytes.NewBufferString(formData.Encode()))
	if err != nil {
		return fmt.Errorf("failed to create request: %v", err)
	}

	// Set headers
	for k, v := range headers {
		req.Header.Set(k, v)
	}

	// Add query parameters
	q := req.URL.Query()
	q.Add("email", config.EmailAddress)
	req.URL.RawQuery = q.Encode()

	// Send request
	client := &http.Client{Timeout: 10 * time.Second}
	resp, err := client.Do(req)
	if err != nil {
		return fmt.Errorf("error scheduling email to be sent later: %v", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("failed to schedule email to be sent later, status: %d", resp.StatusCode)
	}

	log.Printf("Email scheduled to be sent at %s", config.SendDate.Format(time.RFC3339))
	return nil
}
