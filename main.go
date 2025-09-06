package main

import (
	"encoding/json"
	"fmt"
	"log"
	"os"
	"strings"
	"text/template"
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

		return client.LoginWithToken(&token)
	}

	// Try logging in with credentials
	if credsPath == "" {
		credsPath = "credentials.json"
	}

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

func processTemplate(templateStr string, data map[string]string) (string, error) {
	tmpl, err := template.New("email").Parse(templateStr)
	if err != nil {
		return "", fmt.Errorf("failed to parse template: %v", err)
	}

	var result strings.Builder
	if err := tmpl.Execute(&result, data); err != nil {
		return "", fmt.Errorf("failed to execute template: %v", err)
	}

	return result.String(), nil
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

	sendTime, err := scheduler.GetScheduledSendTime(dayRanges, timezone)
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

	// Get values from args or env vars
	subject := argparse.GetArgOrEnv(args.subject, config.EnvEmailSubject, true, "")
	messageBodyPath := argparse.GetArgOrEnv(args.messageBodyPath, config.EnvMessageBodyPath, true, "")
	attachmentPathString := argparse.GetArgOrEnv(args.attachmentPath, config.EnvAttachmentPath, false, "")
	attachmentName := argparse.GetArgOrEnv(args.attachmentName, config.EnvAttachmentName, false, "")

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

	shouldSchedule := getBoolArgOrEnv(args.schedule, config.EnvEnableStreakScheduling)
	tokenPath := getArgOrEnv(args.tokenPath, config.EnvTokenPath, false, "token.json")

	// Login with token
	creds, err := authenticateGmail(gmailClient, tokenPath, args.credsPath)
	if err != nil {
		log.Fatalf("Authentication failed: %v", err)
	}

	// Save updated credentials
	if err := saveCredentials(creds, tokenPath); err != nil {
		log.Printf("Warning: Failed to save credentials: %v", err)
	}

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
		"recruiter_name":    args.recruiterName,
		"recruiter_company": args.recruiterCompany,
	})
	if err != nil {
		log.Fatalf("Failed to process template: %v", err)
	}

	subject, err = processTemplate(subject, map[string]string{
		"recruiter_company": args.recruiterCompany,
	})
	if err != nil {
		log.Fatalf("Failed to process subject template: %v", err)
	}

	emailMessage := gmail.CreateEmailMessage(
		emailContents,
		args.recruiterEmail,
		subject,
		attachment,
		attachmentName,
	)

	log.Printf("Recruiter email: %s, Recruiter Name: %s, Recruiter Company: %s",
		args.recruiterEmail, args.recruiterName, args.recruiterCompany)

	// Save draft
	draft, err := gmailClient.SaveDraft(emailMessage)
	if err != nil {
		log.Fatalf("Failed to save draft: %v", err)
	}

	// Schedule email if requested
	if shouldSchedule {
		timezone := getArgOrEnv(args.timezone, config.EnvTimezone, false, "UTC")
		streakToken := getArgOrEnv("", config.EnvStreakToken, true, "")
		csvPath := getArgOrEnv(args.scheduleCsvPath, config.EnvScheduleCsvPath, true, "")
		streakEmailAddress := getArgOrEnv(args.emailAddress, config.EnvStreakEmailAddress, false, "")

		if streakEmailAddress == "" {
			user, err := gmailClient.GetCurrentUser()
			if err != nil {
				log.Printf("Warning: Failed to get current user: %v", err)
			} else {
				streakEmailAddress = user.EmailAddress
			}
		}

		if err := scheduleSend(timezone, csvPath, draft, streakToken, streakEmailAddress, args.recruiterEmail, subject); err != nil {
			log.Printf("Warning: Failed to schedule email: %v", err)
		}
	}
}
