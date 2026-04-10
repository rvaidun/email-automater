package main

import (
	"encoding/json"
	"fmt"
	"log"
	"os"
	"strings"
	"time"

	"emailer/internal/argparse"
	"emailer/internal/config"
	"emailer/internal/gmail"
	"emailer/internal/scheduler"
	"emailer/internal/streak"

	"github.com/joho/godotenv"
)

func authenticateGmail(client *gmail.Client, tokenPath, credsPath string) (*gmail.Credentials, error) {
	// Try to load existing token
	if _, err := os.Stat(tokenPath); err == nil {
		tokenData, err := os.ReadFile(tokenPath)
		if err != nil {
			return nil, fmt.Errorf("failed to read token file: %v", err)
		}

		var token gmail.Token
		if err := json.Unmarshal(tokenData, &token); err != nil {
			return nil, fmt.Errorf("failed to parse token file: %v", err)
		}

		return client.LoginWithToken(&token, credsPath)
	}

	// Try logging in with credentials

	if _, err := os.Stat(credsPath); err != nil {
		return nil, fmt.Errorf("no credentials JSON file found")
	}

	log.Println("No token JSON file found, logging in with credentials")
	return client.LoginWithCredentials(credsPath)
}

func saveCredentials(creds *gmail.Credentials, tokenPath string) error {
	tokenData, err := json.MarshalIndent(creds.Token, "", "  ")
	if err != nil {
		return fmt.Errorf("failed to marshal token: %v", err)
	}

	if err := os.WriteFile(tokenPath, tokenData, 0644); err != nil {
		return fmt.Errorf("failed to write token file: %v", err)
	}

	log.Println("Token JSON file created")
	return nil
}

// processTemplate substitutes ${var} and $var placeholders in templateStr using data,
// matching Python's string.Template.substitute() behaviour. Returns an error if the
// template references a key that is not present in data.
func processTemplate(templateStr string, data map[string]string) (string, error) {
	var missing []string
	result := os.Expand(templateStr, func(key string) string {
		if val, ok := data[key]; ok {
			return val
		}
		missing = append(missing, key)
		return ""
	})
	if len(missing) > 0 {
		return "", fmt.Errorf("template references undefined variables: %s", strings.Join(missing, ", "))
	}
	return result, nil
}

func scheduleSend(timezone, csvPath string, draft *gmail.Draft, streakToken, streakEmailAddress, toAddress, subject string) error {
	if streakToken == "" {
		return fmt.Errorf("scheduling error: no streak token provided")
	}
	if csvPath == "" {
		return fmt.Errorf("scheduling error: no schedule csv file provided")
	}

	if _, err := os.Stat(csvPath); err != nil {
		return fmt.Errorf("scheduling error: no schedule csv file found")
	}

	if streakEmailAddress == "" {
		log.Printf("Scheduling warning: %s not provided. Streak scheduling may not work as expected", config.EnvStreakEmailAddress)
	}

	// Parse CSV and get scheduled time
	dayRanges, err := scheduler.ParseTimeRangesCSV(csvPath)
	if err != nil {
		return fmt.Errorf("failed to parse CSV: %v", err)
	}

	sendTime, err := scheduler.GetScheduledSendTime(dayRanges, timezone, nil)
	if err != nil {
		return fmt.Errorf("failed to get scheduled time: %v", err)
	}

	if sendTime == nil {
		// Current time is within allowed range, send 10 minutes from now
		loc, err := time.LoadLocation(timezone)
		if err != nil {
			loc = time.UTC
		}
		now := time.Now().In(loc)
		now = now.Add(10 * time.Minute)
		sendTime = &now
	}

	config := &streak.SendLaterConfig{
		Token:        streakToken,
		ToAddress:    toAddress,
		Subject:      subject,
		ThreadID:     draft.Message.ThreadId,
		DraftID:      draft.Id,
		SendDate:     *sendTime,
		IsTracked:    true,
		EmailAddress: streakEmailAddress,
	}

	return streak.ScheduleSendLater(config)
}

func main() {
	// Load environment variables
	if err := godotenv.Load(); err != nil {
		log.Printf("Warning: .env file not found: %v", err)
	}

	// Parse command line arguments
	// create the arg variable. it should be empty struct of argparse.Args
	args := &argparse.Args{}
	argparse.ParseArgs(args)
	// args := argparse.ParseArgs()

	// Validate required arguments
	if err := argparse.ValidateArgs(args); err != nil {
		log.Fatalf("Validation error: %v", err)
	}

	// Create Gmail client
	gmailClient := gmail.NewClient()

	// Login with token
	tokenPath := argparse.GetArgOrEnv(args.TokenPath, config.EnvTokenPath, false, "token.json")

	creds, err := authenticateGmail(gmailClient, tokenPath, args.CredsPath)
	if err != nil {
		log.Fatalf("Authentication failed: %v", err)
	}
	// Save updated credentials
	if err := saveCredentials(creds, tokenPath); err != nil {
		log.Printf("Warning: Failed to save credentials: %v", err)
	}

	// Get values from args or env vars
	subject := argparse.GetArgOrEnv(args.Subject, config.EnvEmailSubject, true, "")
	messageBodyPath := argparse.GetArgOrEnv(args.MessageBodyPath, config.EnvMessageBodyPath, true, "")
	attachmentPathString := argparse.GetArgOrEnv(args.AttachmentPath, config.EnvAttachmentPath, false, "")
	attachmentName := argparse.GetArgOrEnv(args.AttachmentName, config.EnvAttachmentName, false, "")

	// Validate attachment parameters
	if (attachmentPathString != "") != (attachmentName != "") {
		log.Fatal("attachment_path and attachment_name must both appear if either is provided")
	}

	// Validate attachment file exists if path is provided
	if attachmentPathString != "" {
		if _, err := os.Stat(attachmentPathString); err != nil {
			log.Fatalf("Attachment file not found: %v", err)
		}
	}

	shouldSchedule := argparse.GetBoolArgOrEnv(args.Schedule, config.EnvEnableStreakScheduling)

	// Setup email contents
	var attachment []byte
	if attachmentPathString != "" {
		attachment, err = os.ReadFile(attachmentPathString)
		if err != nil {
			log.Fatalf("Failed to read attachment file: %v", err)
		}
	}

	// Validate message template file exists
	if _, err := os.Stat(messageBodyPath); err != nil {
		log.Fatalf("Message template file not found: %v", err)
	}

	templateContent, err := os.ReadFile(messageBodyPath)
	if err != nil {
		log.Fatalf("Failed to read message template: %v", err)
	}

	emailContents, err := processTemplate(string(templateContent), map[string]string{
		"recruiter_name":    args.RecruiterName,
		"recruiter_company": args.RecruiterCompany,
	})
	if err != nil {
		log.Fatalf("Failed to process template: %v", err)
	}

	subject, err = processTemplate(subject, map[string]string{
		"recruiter_company": args.RecruiterCompany,
	})
	if err != nil {
		log.Fatalf("Failed to process subject template: %v", err)
	}

	emailMessage := gmail.CreateEmailMessage(
		emailContents,
		args.RecruiterEmail,
		subject,
		attachment,
		attachmentName,
	)

	log.Printf("Recruiter email: %s, Recruiter Name: %s, Recruiter Company: %s",
		args.RecruiterEmail, args.RecruiterName, args.RecruiterCompany)

	// Save draft
	draft, err := gmailClient.SaveDraft(emailMessage)
	if err != nil {
		log.Fatalf("Failed to save draft: %v", err)
	}

	// Schedule email if requested
	if shouldSchedule {
		timezone := argparse.GetArgOrEnv(args.Timezone, config.EnvTimezone, false, "UTC")
		streakToken := argparse.GetArgOrEnv("", config.EnvStreakToken, true, "")
		csvPath := argparse.GetArgOrEnv(args.ScheduleCsvPath, config.EnvScheduleCsvPath, true, "")
		streakEmailAddress := argparse.GetArgOrEnv(args.EmailAddress, config.EnvStreakEmailAddress, false, "")

		if streakEmailAddress == "" {
			user, err := gmailClient.GetCurrentUser()
			if err != nil {
				log.Printf("Warning: Failed to get current user: %v", err)
			} else {
				streakEmailAddress = user.EmailAddress
			}
		}

		if err := scheduleSend(timezone, csvPath, draft, streakToken, streakEmailAddress, args.RecruiterEmail, subject); err != nil {
			log.Printf("Warning: Failed to schedule email: %v", err)
		}
	}
}
