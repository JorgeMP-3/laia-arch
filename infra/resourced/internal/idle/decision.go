package idle

import "time"

// Decision is the audit-record for ONE shadow action the daemon
// would have taken in enforce mode. Persisted as JSONL (one line per
// decision) into decisions.jsonl. The schema is stable: any change
// here is a breaking change for `laia-res audit`.
type Decision struct {
	TS          time.Time `json:"ts"`
	Kind        string    `json:"kind"`   // "suspend" | "suspend_still" | "end_idle"
	Target      string    `json:"target"` // "laia-dev" in v1 (the only class=dev target)
	Reason      string    `json:"reason"` // human-readable, includes the measurements
	WouldFreeMB int64     `json:"would_free_mb,omitempty"`
	Mode        string    `json:"mode"` // "monitor" always in v1
}
