package argparse

import (
	"emailer/internal/config"
	"fmt"
	"log"
	"os"
	"strings"

	"github.com/spf13/pflag"
)

type Args struct {
	recruiterCompany string
	recruiterName    string
	recruiterEmail   string
	attachmentPath   string
	attachmentName   string
	subject          string
	messageBodyPath  string
	timezone         string
	schedule         bool
	scheduleCsvPath  string
	emailAddress     string
	tokenPath        string
	credsPath        string
	help             bool
}

func printUsage(isError bool) {
	output := os.Stdout
	if isError {
		output = os.Stderr
	}

	fmt.Fprintf(output, "Usage: %s <recruiter_company> <recruiter_name> <recruiter_email> [flags]\n\n", os.Args[0])
	fmt.Fprintf(output, "Positional Arguments:\n")
	fmt.Fprintf(output, "  recruiter_company    The name of the recruiter's company\n")
	fmt.Fprintf(output, "  recruiter_name       The name of the recruiter\n")
	fmt.Fprintf(output, "  recruiter_email      The email address of the recruiter\n\n")
	fmt.Fprintf(output, "Flags:\n")

	// Temporarily redirect pflag output to our chosen output
	originalOutput := os.Stderr
	if !isError {
		os.Stderr = os.Stdout
	}
	pflag.PrintDefaults()
	if !isError {
		os.Stderr = originalOutput
	}
}

// ParseArgs should take a pointer to Args and populate it
func ParseArgs(args *Args) {
	// Add help flag
	pflag.BoolVarP(&args.help, "help", "h", false, "Show this help message")

	// Positional arguments (recruiter_company, recruiter_name, recruiter_email)
	// These will be handled separately as positional args

	// Optional arguments with single-character shorthand flags (pflag limitation)
	// Note: Python version uses multi-character shorthands like -tz, -sch, -scsv, -ap, -an
	// but pflag only supports single-character shorthands
	pflag.StringVarP(&args.subject, "subject", "s", "",
		fmt.Sprintf("The subject of the email message as a string template. Overrides the %s environment variable.", config.EnvEmailSubject))

	pflag.StringVarP(&args.messageBodyPath, "message_body_path", "m", "",
		fmt.Sprintf("The path to the message body template. Overrides the %s environment variable.", config.EnvMessageBodyPath))

	pflag.StringVarP(&args.timezone, "timezone", "z", "",
		fmt.Sprintf("The timezone to use for scheduling emails (America/New_York). Overrides the %s environment variable. This is used to determine the time range so it should be the recipient's timezone.", config.EnvTimezone))

	pflag.BoolVarP(&args.schedule, "schedule", "", false,
		fmt.Sprintf("Whether the email should be tracked or not. Overrides the %s. If set, the streak token must be provided via env variable %s", config.EnvEnableStreakScheduling, config.EnvStreakToken))

	pflag.StringVarP(&args.scheduleCsvPath, "schedule_csv_path", "v", "",
		fmt.Sprintf("CSV to use for scheduling the emails. Overrides the %s environment variable. Note: --schedule needs to be enabled for this to be used", config.EnvScheduleCsvPath))

	pflag.StringVarP(&args.emailAddress, "email_address", "e", "",
		fmt.Sprintf("The email address to send to the Streak API. Overrides the %s. If not provided, the email address of the authenticated user will be used. Note: --schedule needs to be enabled for this to be used", config.EnvStreakEmailAddress))

	pflag.StringVarP(&args.tokenPath, "token_path", "t", "",
		fmt.Sprintf("The path to the token.json file. The default value is token.json. Overrides the %s environment variable", config.EnvTokenPath))

	pflag.StringVarP(&args.credsPath, "creds_path", "c", "",
		fmt.Sprintf("The path to the credentials.json file. The default value is credentials.json. Overrides the %s environment variable", config.EnvCredsPath))

	pflag.StringVarP(&args.attachmentPath, "attachment_path", "a", "",
		fmt.Sprintf("The path to the attachment file, if this is provided, attachment_name must also be provided. Overrides the %s environment variable", config.EnvAttachmentPath))

	pflag.StringVarP(&args.attachmentName, "attachment_name", "n", "",
		fmt.Sprintf("The name of the attachment file. Overrides the %s environment variable", config.EnvAttachmentName))

	pflag.Parse()

	// Handle help flag
	if args.help {
		printUsage(false)
		os.Exit(0)
	}

	// Handle positional arguments (recruiter_company, recruiter_name, recruiter_email)
	if pflag.NArg() == 3 {
		args.recruiterCompany = pflag.Arg(0)
		args.recruiterName = pflag.Arg(1)
		args.recruiterEmail = pflag.Arg(2)
	} else {
		printUsage(true)
		os.Exit(1)
	}

}

// validateArgs validates that required arguments are not blank
func ValidateArgs(args *Args) error {
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

func GetArgOrEnv(argValue, envVar string, required bool, defaultValue string) string {
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
