package idle

import (
	"strings"
	"testing"
	"time"
)

func mkDec(kind, target string, ts time.Time, reason string, free int64) Decision {
	return Decision{TS: ts, Kind: kind, Target: target, Reason: reason, WouldFreeMB: free, Mode: "monitor"}
}

func TestParseSinceTabla(t *testing.T) {
	now := time.Date(2026, 6, 3, 12, 0, 0, 0, time.UTC)
	cases := []struct {
		in   string
		want time.Time
	}{
		{"30d", now.Add(-30 * 24 * time.Hour)},
		{"7d", now.Add(-7 * 24 * time.Hour)},
		{"1d", now.Add(-24 * time.Hour)},
		{"24h", now.Add(-24 * time.Hour)},
		{"90m", now.Add(-90 * time.Minute)},
		{"", now.Add(-30 * 24 * time.Hour)}, // default
	}
	for _, c := range cases {
		t.Run(c.in, func(t *testing.T) {
			got, err := ParseSince(c.in, now)
			if err != nil {
				t.Fatalf("err: %v", err)
			}
			if !got.Equal(c.want) {
				t.Errorf("got %v want %v", got, c.want)
			}
		})
	}
}

func TestParseSinceInvalido(t *testing.T) {
	now := time.Now()
	for _, in := range []string{"abc", "5x", "-3d"} {
		if _, err := ParseSince(in, now); err == nil {
			t.Errorf("expected error for %q", in)
		}
	}
}

// 2 closed episodes + 1 open + 1 corrupt → exact counts, episode list, open detected.
func TestAuditEndToEnd(t *testing.T) {
	t0 := time.Date(2026, 6, 1, 12, 0, 0, 0, time.UTC)
	decs := []Decision{
		// Episode 1: 2h idle
		mkDec("suspend", "laia-dev", t0, "idle 30m (ssh=0 ts=0 load=0.05)", 3072),
		mkDec("suspend_still", "laia-dev", t0.Add(60*time.Minute), "still idle", 3072),
		mkDec("end_idle", "laia-dev", t0.Add(2*time.Hour), "active after 2h idle", 3072),
		// Episode 2: 30m idle
		mkDec("suspend", "laia-dev", t0.Add(24*time.Hour), "idle 30m", 3072),
		mkDec("end_idle", "laia-dev", t0.Add(24*time.Hour+30*time.Minute), "active", 3072),
		// Episode 3: open (suspend, no end)
		mkDec("suspend", "laia-dev", t0.Add(48*time.Hour), "idle 30m", 3072),
		// One corrupt-looking line, simulated by inserting a non-JSON
		// in the source. We test readDecisionsFrom separately below;
		// here we feed only valid Decisions.
	}
	since := t0.Add(-time.Hour)
	summary := Audit(decs, since, t0.Add(72*time.Hour))

	if summary.TotalEpisodes != 3 {
		t.Errorf("TotalEpisodes: got %d want 3", summary.TotalEpisodes)
	}
	if summary.OpenEpisodes != 1 {
		t.Errorf("OpenEpisodes: got %d want 1", summary.OpenEpisodes)
	}
	if len(summary.Targets) != 1 || summary.Targets[0].Target != "laia-dev" {
		t.Errorf("targets: %+v", summary.Targets)
	}
	t0sum := summary.Targets[0]
	if t0sum.WouldFreeTotalMB != 3072*3 {
		t.Errorf("WouldFreeTotalMB: got %d want %d", t0sum.WouldFreeTotalMB, 3072*3)
	}
	// 3 episodes, sorted by start: episode 1 (2h), episode 2 (30m), episode 3 (open).
	if len(t0sum.Episodes) != 3 {
		t.Fatalf("Episodes: got %d", len(t0sum.Episodes))
	}
	if !t0sum.Episodes[2].End.IsZero() {
		t.Errorf("last episode should be open (End zero)")
	}
	if t0sum.Episodes[0].StillCount != 1 {
		t.Errorf("first episode StillCount: got %d want 1", t0sum.Episodes[0].StillCount)
	}
}

// TestReadDecisionsFromCorrupta: 1 corrupt line → counted, others parsed.
func TestReadDecisionsFromCorrupta(t *testing.T) {
	src := `{"ts":"2026-06-01T12:00:00Z","kind":"suspend","target":"laia-dev","reason":"r","mode":"monitor"}
not json at all
{"ts":"2026-06-01T13:00:00Z","kind":"end_idle","target":"laia-dev","reason":"r","mode":"monitor"}
`
	decs, corrupt, err := readDecisionsFrom(strings.NewReader(src))
	if err != nil {
		t.Fatal(err)
	}
	if corrupt != 1 {
		t.Errorf("corrupt: got %d want 1", corrupt)
	}
	if len(decs) != 2 {
		t.Errorf("decs: got %d want 2", len(decs))
	}
}

// TestAuditSinDecisiones: empty list → empty summary, no error.
func TestAuditSinDecisiones(t *testing.T) {
	s := Audit(nil, time.Now(), time.Now())
	if s.TotalEpisodes != 0 || s.OpenEpisodes != 0 {
		t.Errorf("expected zero counts, got %+v", s)
	}
	if len(s.Targets) != 0 {
		t.Errorf("expected no targets")
	}
}

// TestAuditFiltraSince: decisions older than `since` are ignored.
func TestAuditFiltraSince(t *testing.T) {
	t0 := time.Date(2026, 1, 1, 12, 0, 0, 0, time.UTC)
	decs := []Decision{
		mkDec("suspend", "laia-dev", t0, "old", 0),
		mkDec("suspend", "laia-dev", t0.Add(40*24*time.Hour), "new", 0),
	}
	since := t0.Add(30 * 24 * time.Hour)
	s := Audit(decs, since, t0.Add(50*24*time.Hour))
	if s.TotalEpisodes != 1 {
		t.Errorf("expected 1 episode (the new one), got %d", s.TotalEpisodes)
	}
}
