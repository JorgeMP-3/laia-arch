package alert

import (
	"context"
	"errors"
	"fmt"
	"net/http"
	"net/url"
	"strings"
	"time"
)

// Telegram is the push backend that POSTs to api.telegram.org. It is
// constructed once at daemon start and used by the Alerter.
//
// Secrets are re-read on EVERY Send (not cached) so the operator can
// rotate the bot token by editing the .env file; the next alert
// picks it up. This is the price of a single source of truth for
// secrets; the cost is one file read per push, which is fine (pushes
// are rare events, throttled to 1 per Kind per 15 min by default).
type Telegram struct {
	BaseURL     string       // default https://api.telegram.org
	SecretsFile string       // path to the .env file
	HTTPC       *http.Client // optional; default has 10s timeout
}

// NewTelegram is a convenience constructor. HTTPC may be nil; it
// defaults to a 10s-timeout client (matches the spec).
func NewTelegram(secretsFile string) *Telegram {
	return &Telegram{
		SecretsFile: secretsFile,
		HTTPC:       &http.Client{Timeout: 10 * time.Second},
	}
}

// Send POSTs the message to Telegram. It returns an error WITHOUT
// leaking the bot token (errors mention the HTTP status, never the
// URL which would embed the token).
func (t *Telegram) Send(ctx context.Context, text string) error {
	secrets, err := ParseEnv(t.SecretsFile)
	if err != nil {
		return fmt.Errorf("telegram: read secrets: %w", err)
	}
	token := secrets["TELEGRAM_BOT_TOKEN"]
	chatID := secrets["RESOURCED_ALERT_CHAT_ID"]
	if token == "" || chatID == "" {
		return errors.New("telegram: missing TELEGRAM_BOT_TOKEN or RESOURCED_ALERT_CHAT_ID")
	}

	base := t.BaseURL
	if base == "" {
		base = "https://api.telegram.org"
	}
	client := t.HTTPC
	if client == nil {
		client = &http.Client{Timeout: 10 * time.Second}
	}

	// We construct the URL with the token, POST once, and never log it.
	// If something fails, the error mentions ONLY the status and a
	// short reason — never the URL.
	apiURL := base + "/bot" + token + "/sendMessage"

	form := url.Values{}
	form.Set("chat_id", chatID)
	form.Set("text", text)
	form.Set("disable_web_page_preview", "true")

	req, err := http.NewRequestWithContext(ctx, http.MethodPost, apiURL, strings.NewReader(form.Encode()))
	if err != nil {
		// A malformed BaseURL surfaces here and the error message
		// embeds the full URL (with the token). Redact before return.
		return errors.New("telegram: build request: " + redactToken(err.Error(), token))
	}
	req.Header.Set("Content-Type", "application/x-www-form-urlencoded")

	resp, err := client.Do(req)
	if err != nil {
		// Transport failures are *url.Error, whose Error() embeds the
		// FULL request URL — i.e. the bot token. This message ends up
		// in Event.PushErr → events.jsonl (0644), so it MUST be
		// redacted. ReplaceAll (vs. reconstructing the error) is
		// defense in depth: whatever shape the wrapped error has, the
		// token never leaves this function.
		return errors.New("telegram: request failed: " + redactToken(err.Error(), token))
	}
	defer resp.Body.Close()

	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		// IMPORTANT: do NOT include resp.Request.URL (contains token).
		return fmt.Errorf("telegram: HTTP %d", resp.StatusCode)
	}
	return nil
}

// redactToken removes the bot token from msg. Every error path that
// could carry a URL-bearing error (build request, transport) must pass
// through here before the message can reach logs or events.jsonl.
func redactToken(msg, token string) string {
	if token == "" {
		return msg
	}
	return strings.ReplaceAll(msg, token, "***")
}
