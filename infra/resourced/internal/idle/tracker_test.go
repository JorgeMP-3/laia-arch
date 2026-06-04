package idle

import (
	"testing"
	"time"

	"github.com/JorgeMP-3/laia-arch/infra/resourced/internal/collect"
	"github.com/JorgeMP-3/laia-arch/infra/resourced/internal/config"
)

func idleCfg(forMin int) config.Idle {
	return config.Idle{LoadBelow: 0.2, ForMinutes: forMin}
}

func actIdle() collect.Activity {
	return collect.Activity{SSHUsers: 0, TailscaleConns: 0, Load1: 0.08}
}

func actBusy() collect.Activity {
	return collect.Activity{SSHUsers: 1, TailscaleConns: 0, Load1: 0.08}
}

// Rule 1: racha cruza el umbral → UN suspend.
func TestTrackerRegla1_CruceUmbralProduceUnSuspend(t *testing.T) {
	tr := New()
	t0 := time.Date(2026, 6, 3, 12, 0, 0, 0, time.UTC)
	cfg := idleCfg(30)

	// T+0: idle starts. No decision.
	if d := tr.Update(t0, actIdle(), cfg, true, nil); d != nil {
		t.Fatalf("tick 0: expected no decision, got %+v", d)
	}
	// T+10m: still under threshold. No decision.
	if d := tr.Update(t0.Add(10*time.Minute), actIdle(), cfg, true, nil); d != nil {
		t.Fatalf("tick 10m: expected no decision, got %+v", d)
	}
	// T+30m: racha crosses 30 min → suspend.
	d := tr.Update(t0.Add(30*time.Minute), actIdle(), cfg, true, nil)
	if d == nil {
		t.Fatalf("tick 30m: expected suspend, got nil")
	}
	if d.Kind != "suspend" {
		t.Errorf("kind: got %q want suspend", d.Kind)
	}
	// T+31m, 32m, ... 89m: still idle, no more suspends (only the initial).
	for m := 31; m < 90; m++ {
		d := tr.Update(t0.Add(time.Duration(m)*time.Minute), actIdle(), cfg, true, nil)
		if d != nil {
			t.Errorf("tick %dm: expected no decision, got %+v", m, d)
		}
	}
}

// Rule 2: sigue idle → suspend_still cada 60 min tras el suspend.
func TestTrackerRegla2_SuspendStillCada60Min(t *testing.T) {
	tr := New()
	t0 := time.Date(2026, 6, 3, 12, 0, 0, 0, time.UTC)
	cfg := idleCfg(30)

	tr.Update(t0, actIdle(), cfg, true, nil)
	tr.Update(t0.Add(30*time.Minute), actIdle(), cfg, true, nil) // suspend
	// T+60m (90 total): 60 min after suspend → suspend_still.
	d := tr.Update(t0.Add(90*time.Minute), actIdle(), cfg, true, nil)
	if d == nil || d.Kind != "suspend_still" {
		t.Fatalf("tick 90m: expected suspend_still, got %+v", d)
	}
	// T+119m: only 29 min since last still → no decision.
	if d := tr.Update(t0.Add(119*time.Minute), actIdle(), cfg, true, nil); d != nil {
		t.Errorf("tick 119m: expected no decision, got %+v", d)
	}
	// T+150m: 60 min after last still → another suspend_still.
	d = tr.Update(t0.Add(150*time.Minute), actIdle(), cfg, true, nil)
	if d == nil || d.Kind != "suspend_still" {
		t.Fatalf("tick 150m: expected suspend_still, got %+v", d)
	}
}

// Rule 3: vuelve actividad tras suspend logueado → end_idle con duración.
func TestTrackerRegla3_EndIdleTrasSuspend(t *testing.T) {
	tr := New()
	t0 := time.Date(2026, 6, 3, 12, 0, 0, 0, time.UTC)
	cfg := idleCfg(30)

	tr.Update(t0, actIdle(), cfg, true, nil)
	tr.Update(t0.Add(30*time.Minute), actIdle(), cfg, true, nil) // suspend
	// T+90m: activity returns.
	d := tr.Update(t0.Add(90*time.Minute), actBusy(), cfg, false, nil)
	if d == nil {
		t.Fatalf("expected end_idle, got nil")
	}
	if d.Kind != "end_idle" {
		t.Errorf("kind: got %q want end_idle", d.Kind)
	}
	if d.Reason == "" {
		t.Errorf("reason should mention duration")
	}
}

// Rule 4: idle que termina ANTES del umbral → no log.
func TestTrackerRegla4_IdleCortoSinLog(t *testing.T) {
	tr := New()
	t0 := time.Date(2026, 6, 3, 12, 0, 0, 0, time.UTC)
	cfg := idleCfg(30)

	tr.Update(t0, actIdle(), cfg, true, nil)
	// T+10m: still idle.
	// T+15m: activity returns (under threshold).
	d := tr.Update(t0.Add(15*time.Minute), actBusy(), cfg, false, nil)
	if d != nil {
		t.Errorf("expected no decision on short idle, got %+v", d)
	}
}

// Rule 5: error del collector → racha a cero, sin log.
func TestTrackerRegla5_ErrorCollectorResetea(t *testing.T) {
	tr := New()
	t0 := time.Date(2026, 6, 3, 12, 0, 0, 0, time.UTC)
	cfg := idleCfg(30)

	// Start a streak.
	tr.Update(t0, actIdle(), cfg, true, nil)
	tr.Update(t0.Add(20*time.Minute), actIdle(), cfg, true, nil)
	// Error: reset, no log.
	if d := tr.Update(t0.Add(25*time.Minute), actIdle(), cfg, true, errFake()); d != nil {
		t.Errorf("error: expected no decision, got %+v", d)
	}
	// Next tick: if we now receive activity (not error), no end_idle
	// (we reset, the streak is gone). The tracker should behave as if
	// it just started.
	if d := tr.Update(t0.Add(26*time.Minute), actBusy(), cfg, false, nil); d != nil {
		t.Errorf("after reset + activity: expected no decision, got %+v", d)
	}
	// Start a fresh streak and cross the threshold → suspend (proves
	// the tracker recovered cleanly from the error).
	tr.Update(t0.Add(27*time.Minute), actIdle(), cfg, true, nil)
	d := tr.Update(t0.Add(27*time.Minute+30*time.Minute), actIdle(), cfg, true, nil)
	if d == nil || d.Kind != "suspend" {
		t.Fatalf("after error recovery: expected suspend, got %+v", d)
	}
}

// Bonus: already-active state must produce no decisions across
// consecutive calls (no spurious events).
func TestTrackerNoOpCuandoActivo(t *testing.T) {
	tr := New()
	t0 := time.Date(2026, 6, 3, 12, 0, 0, 0, time.UTC)
	cfg := idleCfg(30)
	for i := 0; i < 5; i++ {
		d := tr.Update(t0.Add(time.Duration(i)*time.Minute), actBusy(), cfg, false, nil)
		if d != nil {
			t.Errorf("tick %d: expected no decision, got %+v", i, d)
		}
	}
}

type fakeErr struct{}

func (fakeErr) Error() string { return "fake" }
func errFake() error          { return fakeErr{} }
