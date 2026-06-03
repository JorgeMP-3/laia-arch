package state

import "time"

// SchemaVersion v2: adds Dimensions/Overall/Services. S0 was a flat
// heartbeat; v2 already carries the verdict of the full watchlist.
// Future non-breaking changes (adding fields with omitempty) do NOT
// bump the schema — only breaking changes (rename/remove, change
// Overall semantics, etc.) do.
const SchemaVersion = 2

// StatusFile is the canonical snapshot filename inside the state dir.
const StatusFile = "status.json"

// Dimension is the verdict of ONE watchlist (egress, ram, vram, disk,
// prod, dev_idle). Detail is a 1-2 sentence human line with the
// relevant numbers (consumed by `laia-res status`). Metrics is omitted
// when empty to keep the JSON small. CheckedAt is WHEN it was actually
// measured — it does not match the tick when there was carry-forward
// (egress), and that is useful: the operator sees "measured 1m32s ago"
// versus a recent green.
type Dimension struct {
	Light     Light            `json:"light"`
	Detail    string           `json:"detail"`
	Metrics   map[string]int64 `json:"metrics,omitempty"`
	CheckedAt time.Time        `json:"checked_at"`
}

// ServiceState is the state of a monitored service by name (lives in
// Status.Services, separate from Dimensions so the operator can inspect
// the full watchlist without parsing the `prod` dimension).
type ServiceState struct {
	Class  string `json:"class"` // critical | dev
	Alive  string `json:"alive"` // ok | down | unknown
	Detail string `json:"detail,omitempty"`
}

// Status is the snapshot the daemon publishes each tick and that
// `laia-res status` reads. S0 fields (schema, version, mode, host, pid,
// started_at, updated_at, tick) are kept as-is so existing readers in
// scripts/UI do not break. S1+ fields (overall, dimensions, services)
// are omitted when empty.
type Status struct {
	Schema     int                     `json:"schema"`
	Version    string                  `json:"version"`
	Mode       string                  `json:"mode"` // monitor | enforce (v1: always monitor)
	Host       string                  `json:"host"`
	PID        int                     `json:"pid"`
	StartedAt  time.Time               `json:"started_at"`
	UpdatedAt  time.Time               `json:"updated_at"`
	Tick       uint64                  `json:"tick"`
	Overall    Light                   `json:"overall,omitempty"`
	Dimensions map[string]Dimension    `json:"dimensions,omitempty"`
	Services   map[string]ServiceState `json:"services,omitempty"`
}
