package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"log"
	"os"
	"strings"
	"text/template"
	"time"

	"emailer/internal/config"
	"emailer/internal/gmail"
	"emailer/internal/scheduler"
	"emailer/internal/streak"

	"github.com/joho/godotenv"
)

func main() {
	// Load environment variables
	if err := godotenv.Load(); err != nil {
		log.Printf("Warning: .env file not found: %v", err)
	}

	// Parse command line arguments
	args := parseArgs()

	// Validate required arguments
	if err := validateArgs(args); err != nil {
		log.Fatalf("Validation error: %v", err)
	}

	// Create Gmail client
	gmailClient := gmail.NewClient()

	// Get values from args or env vars
	subject := getArgOrEnv(args.subject, config.EnvEmailSubject, true, "")
	messageBodyPath := getArgOrEnv(args.messageBodyPath, config.EnvMessageBodyPath, true, "")
	attachmentPathString := getArgOrEnv(args.attachmentPath, config.EnvAttachmentPath, false, "")
	attachmentName := getArgOrEnv(args.attachmentName, config.EnvAttachmentName, false, "")

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

type Args struct {
	recruiterCompany   string
	recruiterName      string
	recruiterEmail     string
	attachmentPath     string
	attachmentName     string
	subject            string
	messageBodyPath    string
	timezone           string
	schedule           bool
	scheduleCsvPath    string
	emailAddress       string
	tokenPath          string
	credsPath          string
}

func parseArgs() *Args {
	args := &Args{}

	// Positional arguments
	flag.StringVar(&args.recruiterCompany, "recruiter-company", "", "The company name of the recruiter")
	flag.StringVar(&args.recruiterName, "recruiter-name", "", "The full name of the recruiter")
	flag.StringVar(&args.recruiterEmail, "recruiter-email", "", "The email address of the recruiter")

	// Optional arguments
	flag.StringVar(&args.attachmentPath, "ap", "", "The path to the attachment file")
	flag.StringVar(&args.attachmentName, "an", "", "The name of the attachment file")
	flag.StringVar(&args.subject, "s", "", "The subject of the email message as a string template")
	flag.StringVar(&args.messageBodyPath, "m", "", "The path to the message body template")
	flag.StringVar(&args.timezone, "tz", "", "The timezone to use for scheduling emails")
	flag.BoolVar(&args.schedule, "sch", false, "Whether the email should be scheduled")
	flag.StringVar(&args.scheduleCsvPath, "scsv", "", "CSV to use for scheduling the emails")
	flag.StringVar(&args.emailAddress, "e", "", "The email address to send to the Streak API")
	flag.StringVar(&args.tokenPath, "t", "", "The path to the token.json file")
	flag.StringVar(&args.credsPath, "c", "", "The path to the credentials.json file")

	flag.Parse()

	// Handle positional arguments
	if flag.NArg() >= 3 {
		args.recruiterCompany = flag.Arg(0)
		args.recruiterName = flag.Arg(1)
		args.recruiterEmail = flag.Arg(2)
	}

	return args
}

// validateArgs validates that required arguments are not blank
func validateArgs(args *Args) error {
	if strings.TrimSpace(args.recruiterCompany) == "" {
		return fmt.Errorf("recruiter company cannot be blank")
	}
	if strings.TrimSpace(args.recruiterName) == "" {
		return fmt.Errorf("recruiter name cannot be blank")
	}
	if strings.TrimSpace(args.recruiterEmail) == "" {
		return fmt.Errorf("recruiter email cannot be blank")
	}
	
	// Basic email validation
	if !isValidEmail(args.recruiterEmail) {
		return fmt.Errorf("invalid email format: %s", args.recruiterEmail)
	}
	
	return nil
}

// isValidEmail performs basic email validation
func isValidEmail(email string) bool {
	email = strings.TrimSpace(email)
	if email == "" {
		return false
	}
	
	// Check if email contains @ and has at least one character before and after
	parts := strings.Split(email, "@")
	if len(parts) != 2 {
		return false
	}
	
	if strings.TrimSpace(parts[0]) == "" || strings.TrimSpace(parts[1]) == "" {
		return false
	}
	
	// Check if domain part contains at least one dot
	if !strings.Contains(parts[1], ".") {
		return false
	}
	
	return true
}

func getArgOrEnv(argValue, envVar string, required bool, defaultValue string) string {
	if argValue != "" {
		return argValue
	}
	if value := os.Getenv(envVar); value != "" {
		return value
	}
	if defaultValue != "" {
		return defaultValue
	}
	if required {
		log.Fatalf("Missing required argument or environment variable: %s", envVar)
	}
	return ""
}

func getBoolArgOrEnv(argValue bool, envVar string) bool {
	if argValue {
		return true
	}
	if value := os.Getenv(envVar); value != "" {
		return strings.ToLower(value) == "true"
	}
	return false
}

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
