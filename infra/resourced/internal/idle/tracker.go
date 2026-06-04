// Package idle — the in-memory idle streak tracker for laia-dev.
//
// S5 is a SHADOW: the daemon does NOT suspend the VM; it only records
// what it WOULD have done in enforce mode. The record (decisions.jsonl)
// is the substrate for the month's verdict (the operator's audit of
// "would the daemon have done the right thing?").
//
// The Tracker is in-memory only. Restart → reset → streak starts at
// zero. This is deliberate: the alternative (persisting streak state)
// would couple the daemon's correctness to disk I/O on every tick for
// a feature that is, by design, observational.
package idle

import (
	"fmt"
	"time"

	"github.com/JorgeMP-3/laia-arch/infra/resourced/internal/collect"
	"github.com/JorgeMP-3/laia-arch/infra/resourced/internal/config"
)

// stillRescheduleInterval is the maximum frequency of suspend_still
// re-confirmations. The spec's rule 2: "como máximo cada 60 min".
const stillRescheduleInterval = 60 * time.Minute

// Tracker is the per-target idle streak state machine. It is NOT
// safe for concurrent use; the daemon runs ticks serially.
type Tracker struct {
	idleSince      *time.Time
	lastDecisionAt time.Time // for the 60-min throttle on suspend_still
	episodeLogged  bool      // has the initial suspend been logged for this episode?
}

// New returns an empty Tracker. The struct is plain data; the caller
// (main) decides which target each Tracker is for.
func New() *Tracker { return &Tracker{} }

// Reset clears the streak (used when the collector errors, per spec
// rule 5: "error del collector → racha a cero, sin log").
func (t *Tracker) Reset() {
	t.idleSince = nil
	t.lastDecisionAt = time.Time{}
	t.episodeLogged = false
}

// Idle returns the current streak start (nil if not idle). Used by
// the daemon to label the dev_idle dimension in status.json.
func (t *Tracker) Idle() *time.Time { return t.idleSince }

// Update is the tick entry point. It returns the Decision to log
// (or nil). Behavior, per spec §S5:
//
//  1. Racha cruza for_minutes → UN suspend
//  2. Sigue idle → suspend_still como máximo cada 60 min
//  3. Vuelve actividad tras suspend logueado → end_idle
//  4. Idle que termina ANTES del umbral → nada
//  5. err != nil → reset, sin log
//  6. Restart → reset (automático: Tracker es en memoria)
func (t *Tracker) Update(now time.Time, a collect.Activity, idleCfg config.Idle, idleNow bool, err error) *Decision {
	if err != nil {
		t.Reset()
		return nil
	}
	if !idleNow {
		return t.onActivity(now)
	}
	return t.onIdle(now, a, idleCfg)
}

// onActivity handles the "we are no longer idle" transition. If we
// had an episode in progress (suspend was already logged), emit
// end_idle with the total duration. If the idle streak ended before
// the threshold, emit nothing (rule 4: no log).
func (t *Tracker) onActivity(now time.Time) *Decision {
	if t.idleSince == nil {
		return nil
	}
	if t.episodeLogged {
		dur := now.Sub(*t.idleSince).Round(time.Minute)
		dec := &Decision{
			TS:     now,
			Kind:   "end_idle",
			Target: "laia-dev",
			Reason: fmt.Sprintf("active after %s idle", dur),
			Mode:   "monitor",
		}
		t.Reset()
		return dec
	}
	// Was idle but under threshold → no log.
	t.Reset()
	return nil
}

// onIdle handles the "still idle" path: start of a new streak, or
// crossing the threshold (first suspend), or the 60-min re-confirmation.
func (t *Tracker) onIdle(now time.Time, a collect.Activity, idleCfg config.Idle) *Decision {
	if t.idleSince == nil {
		// Start of a new idle streak.
		t.idleSince = &now
		t.episodeLogged = false
		t.lastDecisionAt = time.Time{}
		return nil
	}
	streak := now.Sub(*t.idleSince)
	threshold := time.Duration(idleCfg.ForMinutes) * time.Minute

	if !t.episodeLogged && streak >= threshold {
		// Rule 1: racha cruza → UN suspend.
		t.episodeLogged = true
		t.lastDecisionAt = now
		return &Decision{
			TS:     now,
			Kind:   "suspend",
			Target: "laia-dev",
			Reason: fmt.Sprintf("idle %dm (ssh=%d ts=%d load=%.2f)", idleCfg.ForMinutes, a.SSHUsers, a.TailscaleConns, a.Load1),
			Mode:   "monitor",
		}
	}
	if t.episodeLogged && now.Sub(t.lastDecisionAt) >= stillRescheduleInterval {
		// Rule 2: re-confirmación cada 60 min mientras siga idle.
		t.lastDecisionAt = now
		return &Decision{
			TS:     now,
			Kind:   "suspend_still",
			Target: "laia-dev",
			Reason: fmt.Sprintf("still idle (ssh=%d ts=%d load=%.2f)", a.SSHUsers, a.TailscaleConns, a.Load1),
			Mode:   "monitor",
		}
	}
	return nil
}
