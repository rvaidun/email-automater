package argparse

import (
	"os"
	"testing"
)

// ---- isValidEmail ----

func TestIsValidEmail(t *testing.T) {
	valid := []string{
		"test@example.com",
		"user.name+tag@sub.domain.org",
		"a@b.co",
	}
	for _, e := range valid {
		if !isValidEmail(e) {
			t.Errorf("expected %q to be valid", e)
		}
	}

	invalid := []string{
		"",
		"notanemail",
		"@nodomain.com",
		"noatsign",
		"missing@dot",
		"double@@at.com",
	}
	for _, e := range invalid {
		if isValidEmail(e) {
			t.Errorf("expected %q to be invalid", e)
		}
	}
}

// ---- ValidateArgs ----

func TestValidateArgs_AllValid(t *testing.T) {
	args := &Args{
		RecruiterCompany: "ACME",
		RecruiterName:    "Jane Doe",
		RecruiterEmail:   "jane@acme.com",
	}
	if err := ValidateArgs(args); err != nil {
		t.Errorf("expected no error, got %v", err)
	}
}

func TestValidateArgs_BlankCompany(t *testing.T) {
	args := &Args{RecruiterCompany: "  ", RecruiterName: "Jane", RecruiterEmail: "jane@acme.com"}
	if err := ValidateArgs(args); err == nil {
		t.Error("expected error for blank company")
	}
}

func TestValidateArgs_BlankName(t *testing.T) {
	args := &Args{RecruiterCompany: "ACME", RecruiterName: "", RecruiterEmail: "jane@acme.com"}
	if err := ValidateArgs(args); err == nil {
		t.Error("expected error for blank name")
	}
}

func TestValidateArgs_BlankEmail(t *testing.T) {
	args := &Args{RecruiterCompany: "ACME", RecruiterName: "Jane", RecruiterEmail: ""}
	if err := ValidateArgs(args); err == nil {
		t.Error("expected error for blank email")
	}
}

func TestValidateArgs_InvalidEmail(t *testing.T) {
	args := &Args{RecruiterCompany: "ACME", RecruiterName: "Jane", RecruiterEmail: "notvalid"}
	if err := ValidateArgs(args); err == nil {
		t.Error("expected error for invalid email")
	}
}

// ---- GetArgOrEnv ----

func TestGetArgOrEnv_ArgTakesPrecedence(t *testing.T) {
	t.Setenv("TEST_VAR", "from_env")
	result := GetArgOrEnv("from_arg", "TEST_VAR", false, "")
	if result != "from_arg" {
		t.Errorf("expected 'from_arg', got %q", result)
	}
}

func TestGetArgOrEnv_FallsBackToEnv(t *testing.T) {
	t.Setenv("TEST_VAR", "from_env")
	result := GetArgOrEnv("", "TEST_VAR", false, "")
	if result != "from_env" {
		t.Errorf("expected 'from_env', got %q", result)
	}
}

func TestGetArgOrEnv_FallsBackToDefault(t *testing.T) {
	os.Unsetenv("TEST_VAR")
	result := GetArgOrEnv("", "TEST_VAR", false, "default_val")
	if result != "default_val" {
		t.Errorf("expected 'default_val', got %q", result)
	}
}

func TestGetArgOrEnv_ReturnsEmptyWhenOptional(t *testing.T) {
	os.Unsetenv("TEST_VAR")
	result := GetArgOrEnv("", "TEST_VAR", false, "")
	if result != "" {
		t.Errorf("expected empty string, got %q", result)
	}
}

// ---- GetBoolArgOrEnv ----

func TestGetBoolArgOrEnv_ArgTrue(t *testing.T) {
	if !GetBoolArgOrEnv(true, "BOOL_VAR") {
		t.Error("expected true when arg is true")
	}
}

func TestGetBoolArgOrEnv_EnvTrue(t *testing.T) {
	t.Setenv("BOOL_VAR", "true")
	if !GetBoolArgOrEnv(false, "BOOL_VAR") {
		t.Error("expected true from env")
	}
}

func TestGetBoolArgOrEnv_EnvFalse(t *testing.T) {
	t.Setenv("BOOL_VAR", "false")
	if GetBoolArgOrEnv(false, "BOOL_VAR") {
		t.Error("expected false from env")
	}
}

func TestGetBoolArgOrEnv_Unset(t *testing.T) {
	os.Unsetenv("BOOL_VAR")
	if GetBoolArgOrEnv(false, "BOOL_VAR") {
		t.Error("expected false when unset")
	}
}
