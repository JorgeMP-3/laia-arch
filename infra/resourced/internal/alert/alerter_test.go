package alert

import (
	"context"
	"errors"
	"path/filepath"
	"strings"
	"sync/atomic"
	"testing"
	"time"

	"github.com/JorgeMP-3/laia-arch/infra/resourced/internal/state"
)

func dim(light state.Light, detail string) state.Dimension {
	return state.Dimension{Light: light, Detail: detail, CheckedAt: time.Unix(0, 0).UTC()}
}

// fakeSender counts Send calls and can be programmed to fail.
type fakeSender struct {
	calls atomic.Int32
	texts []string
	err   error
}

func (f *fakeSender) Send(_ context.Context, text string) error {
	f.calls.Add(1)
	f.texts = append(f.texts, text)
	return f.err
}

// TestProcessTabla: complete coverage of the transition table from §S2.
// Each row is a real scenario the daemon will produce.
func TestProcessTabla(t *testing.T) {
	dir := t.TempDir()
	events := filepath.Join(dir, "events.jsonl")
	cfg := AlertsConfig{ThrottleMinutes: 15, Host: "test-host"}
	cases := []struct {
		name      string
		prev      map[string]state.Dimension
		curr      map[string]state.Dimension
		wantEv    int         // number of events
		wantPush  int32       // expected Send calls
		wantSkip  string      // expected PushSkipped
		wantLight state.Light // expected event light
	}{
		{
			name:   "ok→red: event + push",
			prev:   map[string]state.Dimension{"egress": dim(state.LightOK, "ok")},
			curr:   map[string]state.Dimension{"egress": dim(state.LightRed, "down")},
			wantEv: 1, wantPush: 1, wantSkip: "", wantLight: state.LightRed,
		},
		{
			name:   "red→red: nothing",
			prev:   map[string]state.Dimension{"egress": dim(state.LightRed, "down")},
			curr:   map[string]state.Dimension{"egress": dim(state.LightRed, "down")},
			wantEv: 0, wantPush: 0,
		},
		{
			name:   "red→ok: event + push (recovery)",
			prev:   map[string]state.Dimension{"egress": dim(state.LightRed, "down")},
			curr:   map[string]state.Dimension{"egress": dim(state.LightOK, "ok")},
			wantEv: 1, wantPush: 1, wantSkip: "", wantLight: state.LightOK,
		},
		{
			name:   "ok→warn: event without push",
			prev:   map[string]state.Dimension{"ram": dim(state.LightOK, "ok")},
			curr:   map[string]state.Dimension{"ram": dim(state.LightWarn, "warn")},
			wantEv: 1, wantPush: 0, wantSkip: "not-push-worthy", wantLight: state.LightWarn,
		},
		{
			name:   "first observation red: event + push",
			prev:   map[string]state.Dimension{},
			curr:   map[string]state.Dimension{"egress": dim(state.LightRed, "down")},
			wantEv: 1, wantPush: 1, wantSkip: "", wantLight: state.LightRed,
		},
		{
			name:   "first observation ok: nothing",
			prev:   map[string]state.Dimension{},
			curr:   map[string]state.Dimension{"egress": dim(state.LightOK, "ok")},
			wantEv: 0, wantPush: 0,
		},
		{
			name:   "first observation unknown: event without push",
			prev:   map[string]state.Dimension{},
			curr:   map[string]state.Dimension{"egress": dim(state.LightUnknown, "no lxc")},
			wantEv: 1, wantPush: 0, wantSkip: "not-push-worthy", wantLight: state.LightUnknown,
		},
		{
			name:   "warn→ok: event without push",
			prev:   map[string]state.Dimension{"ram": dim(state.LightWarn, "warn")},
			curr:   map[string]state.Dimension{"ram": dim(state.LightOK, "ok")},
			wantEv: 1, wantPush: 0, wantSkip: "not-push-worthy", wantLight: state.LightOK,
		},
		{
			name:   "two dims transitioning independently: 2 events",
			prev:   map[string]state.Dimension{"egress": dim(state.LightOK, "ok"), "ram": dim(state.LightOK, "ok")},
			curr:   map[string]state.Dimension{"egress": dim(state.LightRed, "down"), "ram": dim(state.LightWarn, "warn")},
			wantEv: 2, wantPush: 1, // only egress is push-worthy
		},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			sender := &fakeSender{}
			a := New(cfg, events, sender)
			evs := a.Process(c.prev, c.curr)
			if len(evs) != c.wantEv {
				t.Errorf("events: got %d want %d", len(evs), c.wantEv)
			}
			if sender.calls.Load() != c.wantPush {
				t.Errorf("pushes: got %d want %d", sender.calls.Load(), c.wantPush)
			}
			if c.wantEv > 0 && c.wantSkip != "" {
				if evs[0].PushSkipped != c.wantSkip {
					t.Errorf("PushSkipped: got %q want %q", evs[0].PushSkipped, c.wantSkip)
				}
			}
			if c.wantEv > 0 && c.wantLight != "" {
				if evs[0].Light != c.wantLight {
					t.Errorf("Light: got %q want %q", evs[0].Light, c.wantLight)
				}
			}
		})
	}
}

// TestThrottle: 2 reds of the same Kind <15 min apart → 2nd throttled.
// >15 min apart → both push. Different Kinds do NOT share throttle.
func TestThrottle(t *testing.T) {
	dir := t.TempDir()
	events := filepath.Join(dir, "events.jsonl")
	cfg := AlertsConfig{ThrottleMinutes: 15, Host: "h"}

	t0 := time.Date(2026, 1, 1, 12, 0, 0, 0, time.UTC)
	clock := t0
	a := New(cfg, events, &fakeSender{}).WithClock(func() time.Time { return clock })

	// 1) egress: ok → red at t0 → push.
	a.Process(nil, map[string]state.Dimension{"egress": dim(state.LightRed, "x")})
	// 2) egress: red → red at t0+5min → NO event (no transition).
	a.Process(map[string]state.Dimension{"egress": dim(state.LightRed, "x")}, map[string]state.Dimension{"egress": dim(state.LightRed, "y")})
	// 3) egress: red → red at t0+10min: still red → no event.
	a.Process(map[string]state.Dimension{"egress": dim(state.LightRed, "x")}, map[string]state.Dimension{"egress": dim(state.LightRed, "z")})
	// 4) Force a transition: clear the prev to ok, then red again. Same
	// Kind, well within the 15 min window → throttled.
	evs := a.Process(map[string]state.Dimension{"egress": dim(state.LightOK, "")}, map[string]state.Dimension{"egress": dim(state.LightRed, "again")})
	if len(evs) != 1 {
		t.Fatalf("transition should produce 1 event; got %d", len(evs))
	}
	if evs[0].PushSkipped != "throttled" {
		t.Errorf("PushSkipped: got %q want throttled", evs[0].PushSkipped)
	}
	if evs[0].Pushed {
		t.Errorf("Pushed should be false (throttled)")
	}

	// 5) Different Kind (ram) is NOT throttled — its own bucket.
	evs = a.Process(nil, map[string]state.Dimension{"ram": dim(state.LightRed, "y")})
	if len(evs) != 1 {
		t.Fatalf("ram event: got %d", len(evs))
	}
	if evs[0].PushSkipped != "" {
		t.Errorf("ram PushSkipped: got %q want '' (different kind, not throttled)", evs[0].PushSkipped)
	}

	// 6) Advance the clock past the throttle window for egress, force
	// a transition again, expect push.
	clock = t0.Add(20 * time.Minute)
	evs = a.Process(map[string]state.Dimension{"egress": dim(state.LightOK, "")}, map[string]state.Dimension{"egress": dim(state.LightRed, "later")})
	if len(evs) != 1 {
		t.Fatalf("after-window event: got %d", len(evs))
	}
	if evs[0].PushSkipped != "" {
		t.Errorf("after-window PushSkipped: got %q want ''", evs[0].PushSkipped)
	}
	if !evs[0].Pushed {
		t.Errorf("after-window Pushed: got false, want true")
	}
}

// TestSenderNil: a nil sender means "push disabled". Events are still
// written to the journal, but PushSkipped == "disabled".
func TestSenderNil(t *testing.T) {
	dir := t.TempDir()
	events := filepath.Join(dir, "events.jsonl")
	cfg := AlertsConfig{ThrottleMinutes: 15, Host: "h"}
	a := New(cfg, events, nil)
	evs := a.Process(nil, map[string]state.Dimension{"egress": dim(state.LightRed, "x")})
	if len(evs) != 1 {
		t.Fatalf("events: got %d", len(evs))
	}
	if evs[0].PushSkipped != "disabled" {
		t.Errorf("PushSkipped: got %q want disabled", evs[0].PushSkipped)
	}
}

// TestPushErrNoLeak: if the sender returns an error, the error text is
// recorded in PushErr (already redacted by the Sender) and the event is
// still written. No retry loop — the next tick may push again.
func TestPushErrNoLeak(t *testing.T) {
	dir := t.TempDir()
	events := filepath.Join(dir, "events.jsonl")
	cfg := AlertsConfig{ThrottleMinutes: 15, Host: "h"}
	sender := &fakeSender{err: errors.New("telegram: HTTP 401")}
	a := New(cfg, events, sender)
	evs := a.Process(nil, map[string]state.Dimension{"egress": dim(state.LightRed, "x")})
	if len(evs) != 1 || evs[0].Pushed {
		t.Fatalf("expected 1 unpushed event; got %+v", evs)
	}
	if evs[0].PushErr == "" {
		t.Errorf("PushErr should be set")
	}
	if strings.Contains(evs[0].PushErr, "token") {
		t.Errorf("PushErr must not contain 'token' (no leak): %q", evs[0].PushErr)
	}
}

// TestBuildMessageFormatos: red uses 🔴, recovery uses ✅, others
// have no emoji.
func TestBuildMessageFormatos(t *testing.T) {
	cases := []struct {
		light state.Light
		want  string
	}{
		{state.LightRed, "🔴 [h] egress: down"},
		{state.LightOK, "✅ [h] egress: ok"},
		{state.LightWarn, "[h] egress: tight"},
		{state.LightUnknown, "[h] egress: no clue"},
	}
	for _, c := range cases {
		got := BuildMessage(c.light, "egress", detailFor(c.light), "h")
		if got != c.want {
			t.Errorf("Light=%q: got %q want %q", c.light, got, c.want)
		}
	}
}

func detailFor(l state.Light) string {
	switch l {
	case state.LightRed:
		return "down"
	case state.LightOK:
		return "ok"
	case state.LightWarn:
		return "tight"
	}
	return "no clue"
}
