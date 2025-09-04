package gmail

import (
	"context"
	"encoding/base64"
	"fmt"
	"log"
	"os"
	"time"

	"golang.org/x/oauth2"
	"golang.org/x/oauth2/google"
	"google.golang.org/api/gmail/v1"
	"google.golang.org/api/option"
)

// Token represents the OAuth2 token structure
type Token struct {
	AccessToken  string    `json:"access_token"`
	TokenType    string    `json:"token_type"`
	RefreshToken string    `json:"refresh_token"`
	Expiry       time.Time `json:"expiry"`
}

// Credentials wraps the OAuth2 token and service
type Credentials struct {
	Token  *Token
	Config *oauth2.Config
}

// Draft represents a Gmail draft
type Draft struct {
	Id      string         `json:"id"`
	Message *gmail.Message `json:"message"`
}

// EmailMessage represents an email message
type EmailMessage struct {
	To          string
	Subject     string
	Body        string
	Attachment  []byte
	AttachName  string
}

// Client represents a Gmail API client
type Client struct {
	service *gmail.Service
	config  *oauth2.Config
}

// NewClient creates a new Gmail client
func NewClient() *Client {
	return &Client{}
}

// LoginWithToken authenticates using an existing token
func (c *Client) LoginWithToken(token *Token) (*Credentials, error) {
	// We need to read the credentials file to get the client config
	credsData, err := os.ReadFile("credentials.json")
	if err != nil {
		return nil, fmt.Errorf("failed to read credentials file: %v", err)
	}
	
	config, err := google.ConfigFromJSON(credsData, gmail.GmailModifyScope)
	if err != nil {
		return nil, fmt.Errorf("failed to create config: %v", err)
	}

	tokenSource := config.TokenSource(context.Background(), &oauth2.Token{
		AccessToken:  token.AccessToken,
		TokenType:    token.TokenType,
		RefreshToken: token.RefreshToken,
		Expiry:       token.Expiry,
	})

	service, err := gmail.NewService(context.Background(), option.WithTokenSource(tokenSource))
	if err != nil {
		return nil, fmt.Errorf("failed to create service: %v", err)
	}

	c.service = service
	c.config = config

	return &Credentials{
		Token:  token,
		Config: config,
	}, nil
}

// LoginWithCredentials authenticates using credentials file
func (c *Client) LoginWithCredentials(credsPath string) (*Credentials, error) {
	ctx := context.Background()
	
	credsData, err := os.ReadFile(credsPath)
	if err != nil {
		return nil, fmt.Errorf("failed to read credentials file: %v", err)
	}
	
	config, err := google.ConfigFromJSON(credsData, gmail.GmailModifyScope)
	if err != nil {
		return nil, fmt.Errorf("failed to create config from credentials: %v", err)
	}

	// Get authorization URL
	authURL := config.AuthCodeURL("state-token", oauth2.AccessTypeOffline)
	fmt.Printf("Go to the following link in your browser: %v\n", authURL)
	
	// Get authorization code from user
	var authCode string
	fmt.Print("Enter the authorization code: ")
	fmt.Scanln(&authCode)

	// Exchange authorization code for token
	token, err := config.Exchange(ctx, authCode)
	if err != nil {
		return nil, fmt.Errorf("failed to exchange token: %v", err)
	}

	// Create service
	service, err := gmail.NewService(ctx, option.WithTokenSource(config.TokenSource(ctx, token)))
	if err != nil {
		return nil, fmt.Errorf("failed to create service: %v", err)
	}

	c.service = service
	c.config = config

	return &Credentials{
		Token: &Token{
			AccessToken:  token.AccessToken,
			TokenType:    token.TokenType,
			RefreshToken: token.RefreshToken,
			Expiry:       token.Expiry,
		},
		Config: config,
	}, nil
}

// CreateEmailMessage creates an email message
func CreateEmailMessage(body, to, subject string, attachment []byte, attachmentName string) *gmail.Message {
	message := &gmail.Message{}
	
	// Create email content
	emailContent := fmt.Sprintf("To: %s\r\nSubject: %s\r\nMIME-Version: 1.0\r\nContent-Type: text/html; charset=UTF-8\r\n\r\n%s", 
		to, subject, body)
	
	if attachment != nil && attachmentName != "" {
		// Add attachment
		boundary := "boundary123"
		emailContent = fmt.Sprintf("To: %s\r\nSubject: %s\r\nMIME-Version: 1.0\r\nContent-Type: multipart/mixed; boundary=%s\r\n\r\n--%s\r\nContent-Type: text/html; charset=UTF-8\r\n\r\n%s\r\n--%s\r\nContent-Type: application/octet-stream; name=\"%s\"\r\nContent-Transfer-Encoding: base64\r\nContent-Disposition: attachment; filename=\"%s\"\r\n\r\n%s\r\n--%s--",
			to, subject, boundary, boundary, body, boundary, attachmentName, attachmentName, base64.StdEncoding.EncodeToString(attachment), boundary)
	}
	
	message.Raw = base64.URLEncoding.EncodeToString([]byte(emailContent))
	return message
}

// SaveDraft saves a draft message
func (c *Client) SaveDraft(message *gmail.Message) (*Draft, error) {
	draft := &gmail.Draft{
		Message: message,
	}
	
	result, err := c.service.Users.Drafts.Create("me", draft).Do()
	if err != nil {
		return nil, fmt.Errorf("failed to create draft: %v", err)
	}
	
	log.Printf("Draft saved with ID: %s", result.Id)
	
	return &Draft{
		Id:      result.Id,
		Message: result.Message,
	}, nil
}

// SendNow sends a message immediately
func (c *Client) SendNow(message *gmail.Message) (*gmail.Message, error) {
	result, err := c.service.Users.Messages.Send("me", message).Do()
	if err != nil {
		return nil, fmt.Errorf("failed to send message: %v", err)
	}
	
	log.Printf("Message sent with ID: %s", result.Id)
	return result, nil
}

// GetCurrentUser gets the current user's information
func (c *Client) GetCurrentUser() (*gmail.Profile, error) {
	profile, err := c.service.Users.GetProfile("me").Do()
	if err != nil {
		return nil, fmt.Errorf("failed to get profile: %v", err)
	}
	
	return profile, nil
}
