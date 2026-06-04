package alert

import (
	"time"

	"github.com/JorgeMP-3/laia-arch/infra/resourced/internal/state"
)

// Event is a single line in events.jsonl. It records a light
// TRANSITION of a dimension (including the first observation if !=
// ok). Push is best-effort: the journal entry is always written; the
// push to Telegram is a side effect recorded in the same line.
type Event struct {
	TS          time.Time   `json:"ts"`
	Kind        string      `json:"kind"` // dimension key: egress | ram | vram | disk | prod | config
	Light       state.Light `json:"light"`
	PrevLight   state.Light `json:"prev_light"`
	Msg         string      `json:"msg"`
	Pushed      bool        `json:"pushed"`
	PushSkipped string      `json:"push_skipped,omitempty"` // "throttled" | "disabled" | "not-push-worthy"
	PushErr     string      `json:"push_err,omitempty"`     // already redacted by Sender: no tokens
}
