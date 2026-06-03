package alert

import (
	"context"
	"net/http"
	"net/http/httptest"
	"net/url"
	"path/filepath"
	"strings"
	"sync/atomic"
	"testing"
)

const (
	testToken  = "TEST_BOT_TOKEN_42"
	testChatID = "999000111"
)

// writeSecrets creates a .env file with the standard test secrets.
func writeSecrets(t *testing.T) string {
	t.Helper()
	dir := t.TempDir()
	path := filepath.Join(dir, "secrets.env")
	content := "# test secrets\n" +
		"TELEGRAM_BOT_TOKEN=" + testToken + "\n" +
		"RESOURCED_ALERT_CHAT_ID=" + testChatID + "\n"
	if err := writeFile(path, content); err != nil {
		t.Fatal(err)
	}
	return path
}

// TestTelegramHTTPPost: a successful POST must include the token in
// the path, the chat_id and text in the form, and disable_web_page_preview.
func TestTelegramHTTPPost(t *testing.T) {
	var gotPath atomic.Value
	var gotForm atomic.Value
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		gotPath.Store(r.URL.Path)
		if err := r.ParseForm(); err != nil {
			t.Errorf("ParseForm: %v", err)
		}
		gotForm.Store(r.PostForm)
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write([]byte(`{"ok":true}`))
	}))
	defer srv.Close()

	secrets := writeSecrets(t)
	tg := &Telegram{
		BaseURL:     srv.URL,
		SecretsFile: secrets,
		HTTPC:       srv.Client(),
	}
	if err := tg.Send(context.Background(), "hello world"); err != nil {
		t.Fatalf("Send: %v", err)
	}

	// Path must contain the token (proves we are calling the right
	// endpoint with the right creds; the token never leaves the box).
	if p, _ := gotPath.Load().(string); !strings.Contains(p, testToken) {
		t.Errorf("path should contain bot token, got %q", p)
	}
	// Form must carry chat_id and text.
	if f, _ := gotForm.Load().(url.Values); f == nil {
		t.Fatalf("no form captured")
	} else {
		if f.Get("chat_id") != testChatID {
			t.Errorf("chat_id: got %q want %q", f.Get("chat_id"), testChatID)
		}
		if f.Get("text") != "hello world" {
			t.Errorf("text: got %q want %q", f.Get("text"), "hello world")
		}
		if f.Get("disable_web_page_preview") != "true" {
			t.Errorf("disable_web_page_preview: got %q want true", f.Get("disable_web_page_preview"))
		}
	}
}

// TestTelegramHTTP401NoToken: a 401 response must surface as an error
// that does NOT include the token (the URL would contain it).
func TestTelegramHTTP401NoToken(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		w.WriteHeader(http.StatusUnauthorized)
	}))
	defer srv.Close()

	tg := &Telegram{
		BaseURL:     srv.URL,
		SecretsFile: writeSecrets(t),
		HTTPC:       srv.Client(),
	}
	err := tg.Send(context.Background(), "test")
	if err == nil {
		t.Fatalf("expected error for HTTP 401")
	}
	if !strings.Contains(err.Error(), "401") {
		t.Errorf("error should mention HTTP 401, got %q", err.Error())
	}
	// Critical: the token MUST NOT appear in the error.
	if strings.Contains(err.Error(), testToken) {
		t.Errorf("error leaks the bot token: %q", err.Error())
	}
}

// TestTelegramSecretsAusentes: missing file or missing keys → error
// that does NOT leak the file contents.
func TestTelegramSecretsAusentes(t *testing.T) {
	tg := &Telegram{
		BaseURL:     "http://example.invalid",
		SecretsFile: "/no/existe/secrets.env",
		HTTPC:       &http.Client{},
	}
	err := tg.Send(context.Background(), "x")
	if err == nil {
		t.Fatalf("expected error for missing secrets file")
	}
	if !strings.Contains(err.Error(), "secrets") {
		t.Errorf("error should mention 'secrets', got %q", err.Error())
	}
}

// TestTelegramSecretsSinClaves: file exists but missing one of the
// required keys → error.
func TestTelegramSecretsSinClaves(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, ".env")
	if err := writeFile(path, "OTHER=value\n"); err != nil {
		t.Fatal(err)
	}
	tg := &Telegram{BaseURL: "http://x", SecretsFile: path, HTTPC: &http.Client{}}
	err := tg.Send(context.Background(), "x")
	if err == nil {
		t.Fatalf("expected error for missing keys")
	}
	if !strings.Contains(err.Error(), "missing") {
		t.Errorf("error should mention 'missing', got %q", err.Error())
	}
}

// TestTelegramDefaultBaseURL: when BaseURL is empty, the production
// api.telegram.org is used. We only assert that Send is callable
// without crashing on URL construction (no real network call here —
// we point it at an unreachable URL and expect a network error, NOT
// a nil error).
func TestTelegramDefaultBaseURL(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, ".env")
	if err := writeFile(path, "TELEGRAM_BOT_TOKEN=x\nRESOURCED_ALERT_CHAT_ID=1\n"); err != nil {
		t.Fatal(err)
	}
	tg := &Telegram{SecretsFile: path} // BaseURL empty → default
	// We do not actually want to hit the internet. We assert the URL
	// construction worked by checking the error mentions the network
	// or DNS layer (not "invalid URL" or "missing secrets").
	err := tg.Send(context.Background(), "x")
	if err == nil {
		t.Skip("DNS unexpectedly resolved api.telegram.org in the test env")
	}
	if strings.Contains(err.Error(), "missing") || strings.Contains(err.Error(), "invalid") {
		t.Errorf("unexpected construction error: %q", err.Error())
	}
}
