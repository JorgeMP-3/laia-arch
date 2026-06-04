// Package alert — emission of alert events and Telegram push.
//
// Two layers:
//   - Journal: every transition (or first observation != ok) is
//     appended to events.jsonl. This is the durable record.
//   - Push:    best-effort Telegram send for the transitions that
//     matter operationally (red, or recovery from red). Throttled per
//     Kind so a flapping dimension does not flood the channel.
//
// The Alerter is stateful in memory: the throttle map is rebuilt
// empty on daemon restart. That is a documented trade-off: a restart
// may re-push the current state of a red dimension, which is
// acceptable — the alternative (persisting throttle timestamps)
// would add disk I/O on every tick for a rare event.
package alert

import (
	"context"
	"fmt"
	"log"
	"time"

	"github.com/JorgeMP-3/laia-arch/infra/resourced/internal/journal"
	"github.com/JorgeMP-3/laia-arch/infra/resourced/internal/state"
)

// AlertsConfig is the subset of config.Alerts the Alerter needs. We
// pass a copy of the relevant fields, not the whole Config, so the
// Alerter stays decoupled from the YAML schema.
type AlertsConfig struct {
	ThrottleMinutes int
	Host            string
}

// Sender is the contract for a push backend. Telegram implements it;
// tests inject a fake.
type Sender interface {
	Send(ctx context.Context, text string) error
}

// Alerter holds the runtime state for event emission. Construct with
// New. The zero value is not usable.
type Alerter struct {
	cfg        AlertsConfig
	sender     Sender // nil disables push (events still journaled)
	eventsPath string // empty disables journal
	now        func() time.Time
	lastPush   map[string]time.Time // per Kind
}

// New creates an Alerter. sender may be nil (push disabled). eventsPath
// may be empty (journal disabled — used in some tests). The clock is
// time.Now by default; tests inject a fake.
func New(cfg AlertsConfig, eventsPath string, sender Sender) *Alerter {
	return &Alerter{
		cfg:        cfg,
		sender:     sender,
		eventsPath: eventsPath,
		now:        time.Now,
		lastPush:   map[string]time.Time{},
	}
}

// WithClock replaces the clock (for deterministic throttle tests).
func (a *Alerter) WithClock(now func() time.Time) *Alerter {
	a.now = now
	return a
}

// Process compares the lights of the previous tick (prev) and the
// current tick (curr) per dimension key. For each TRANSITION (or first
// observation != ok) it writes an Event to the journal. A push is
// attempted when the new light is red, or we are recovering FROM red
// (so the operator sees the resolution).
//
// Only transitions generate events. A dimension pinned to red for 100
// ticks produces exactly 1 event (plus throttled-but-skipped pushes
// that do NOT add new events, by design).
//
// Returns the events written; tests assert on the list.
func (a *Alerter) Process(prev, curr map[string]state.Dimension) []Event {
	keys := map[string]bool{}
	for k := range prev {
		keys[k] = true
	}
	for k := range curr {
		keys[k] = true
	}

	var out []Event
	for k := range keys {
		c, ok := curr[k]
		if !ok {
			continue
		}
		pLight := prevLightFor(prev, k)
		cLight := c.Light
		if cLight == "" {
			cLight = state.LightOK
		}
		// No transition → no event.
		if pLight == cLight {
			continue
		}

		ev := Event{
			TS:        a.now().UTC(),
			Kind:      k,
			Light:     cLight,
			PrevLight: pLight,
			Msg:       BuildMessage(cLight, k, c.Detail, a.cfg.Host),
		}

		// Push decision: new is red OR previous was red (recovery).
		// Other transitions (ok→warn, warn→ok, ok→unknown) are
		// journaled but not pushed — the operator reads them from
		// the journal, not from Telegram.
		shouldPush := cLight == state.LightRed || pLight == state.LightRed

		switch {
		case !shouldPush:
			ev.PushSkipped = "not-push-worthy"
		case a.sender == nil:
			ev.PushSkipped = "disabled"
		case a.isThrottled(k):
			ev.PushSkipped = "throttled"
		default:
			perr := a.sender.Send(context.Background(), ev.Msg)
			if perr != nil {
				ev.PushErr = perr.Error() // already redacted by Sender
			} else {
				ev.Pushed = true
				a.lastPush[k] = a.now()
			}
		}

		if a.eventsPath != "" {
			if err := journal.Append(a.eventsPath, ev); err != nil {
				log.Printf("WARN: alert: could not write event: %v", err)
			}
		}
		out = append(out, ev)
	}
	return out
}

// prevLightFor returns the previous light for a kind. If the key was
// not in the previous map, the default is "ok" (the system is
// considered healthy until proven otherwise).
func prevLightFor(prev map[string]state.Dimension, k string) state.Light {
	if d, ok := prev[k]; ok {
		return d.Light
	}
	return state.LightOK
}

func (a *Alerter) isThrottled(kind string) bool {
	if a.cfg.ThrottleMinutes <= 0 {
		return false
	}
	last, ok := a.lastPush[kind]
	if !ok {
		return false
	}
	return a.now().Sub(last) < time.Duration(a.cfg.ThrottleMinutes)*time.Minute
}

// BuildMessage formats a push message. Red uses 🔴, recovery from red
// uses ✅. The host name is included so the operator sees WHICH host
// generated the alert (multi-host installations).
//
// Exported so tests can assert on the exact format.
func BuildMessage(light state.Light, kind, detail, host string) string {
	switch light {
	case state.LightRed:
		return fmt.Sprintf("🔴 [%s] %s: %s", host, kind, detail)
	case state.LightOK:
		// Recovery message (we only get here if prev was red).
		return fmt.Sprintf("✅ [%s] %s: %s", host, kind, detail)
	}
	// warn / unknown / future: no emoji, just the fact.
	return fmt.Sprintf("[%s] %s: %s", host, kind, detail)
}
