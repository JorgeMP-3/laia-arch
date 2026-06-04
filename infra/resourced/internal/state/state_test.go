package state

import (
	"os"
	"path/filepath"
	"testing"
	"time"
)

func TestWriteReadRoundTrip(t *testing.T) {
	dir := t.TempDir()
	want := Status{
		Schema: SchemaVersion, Version: "test", Mode: "monitor",
		Host: "vm", PID: 42, Tick: 7,
		StartedAt: time.Unix(1000, 0).UTC(), UpdatedAt: time.Unix(2000, 0).UTC(),
	}
	if err := WriteJSON(dir, StatusFile, want); err != nil {
		t.Fatalf("WriteJSON: %v", err)
	}
	var got Status
	if err := ReadJSON(filepath.Join(dir, StatusFile), &got); err != nil {
		t.Fatalf("ReadJSON: %v", err)
	}
	if got.Tick != want.Tick || got.Mode != want.Mode || !got.UpdatedAt.Equal(want.UpdatedAt) {
		t.Errorf("round-trip does not match:\n got  %+v\n want %+v", got, want)
	}
}

func TestWriteIsAtomicNoTempLeft(t *testing.T) {
	dir := t.TempDir()
	if err := WriteJSON(dir, StatusFile, Status{Tick: 1}); err != nil {
		t.Fatalf("WriteJSON: %v", err)
	}
	entries, err := os.ReadDir(dir)
	if err != nil {
		t.Fatal(err)
	}
	for _, e := range entries {
		if e.Name() != StatusFile {
			t.Errorf("leftover temp file: %s", e.Name())
		}
	}
}

func TestReadMissingIsNotExist(t *testing.T) {
	err := ReadJSON(filepath.Join(t.TempDir(), "nope.json"), &Status{})
	if !os.IsNotExist(err) {
		t.Errorf("expected os.IsNotExist, got %v", err)
	}
}

// TestStatusV2RoundTrip verifies that the new schema (v2) survives a
// round-trip through disk, including Dimensions and Services. If a
// breaking field is removed or renamed, this test fails.
func TestStatusV2RoundTrip(t *testing.T) {
	dir := t.TempDir()
	checked := time.Unix(3000, 0).UTC()
	updated := time.Unix(4000, 0).UTC()
	want := Status{
		Schema:    SchemaVersion,
		Version:   "v1",
		Mode:      "monitor",
		Host:      "doyouwin-server",
		PID:       99,
		StartedAt: time.Unix(1000, 0).UTC(),
		UpdatedAt: updated,
		Tick:      42,
		Overall:   LightOK,
		Dimensions: map[string]Dimension{
			"egress": {Light: LightOK, Detail: "probe 200", Metrics: map[string]int64{"http": 200}, CheckedAt: checked},
			"ram":    {Light: LightWarn, Detail: "available 9000 MB", Metrics: map[string]int64{"available_mb": 9000}, CheckedAt: checked},
		},
		Services: map[string]ServiceState{
			"laia-agora": {Class: "critical", Alive: "ok"},
		},
	}
	if err := WriteJSON(dir, StatusFile, want); err != nil {
		t.Fatalf("WriteJSON: %v", err)
	}
	var got Status
	if err := ReadJSON(filepath.Join(dir, StatusFile), &got); err != nil {
		t.Fatalf("ReadJSON: %v", err)
	}
	if got.Schema != SchemaVersion {
		t.Errorf("schema: got %d want %d", got.Schema, SchemaVersion)
	}
	if got.Overall != LightOK {
		t.Errorf("overall: got %q want %q", got.Overall, LightOK)
	}
	if len(got.Dimensions) != 2 {
		t.Fatalf("dimensions: got %d want 2", len(got.Dimensions))
	}
	egr, ok := got.Dimensions["egress"]
	if !ok || egr.Light != LightOK || egr.Metrics["http"] != 200 {
		t.Errorf("egress dim corrupt: %+v", egr)
	}
	if !egr.CheckedAt.Equal(checked) {
		t.Errorf("egress CheckedAt: got %v want %v", egr.CheckedAt, checked)
	}
	if len(got.Services) != 1 || got.Services["laia-agora"].Class != "critical" {
		t.Errorf("services corrupt: %+v", got.Services)
	}
}

// TestLightSeverityOrdering checks the 4 lights in the expected severity
// order (ok<warn<unknown<red). Overall depends on this order: a change
// here changes Status composition.
func TestLightSeverityOrdering(t *testing.T) {
	cases := []struct {
		l    Light
		want int
	}{
		{LightOK, 0},
		{LightWarn, 1},
		{LightUnknown, 2},
		{LightRed, 3},
		{Light(""), 2},    // empty: treated as unknown (conservative)
		{Light("foo"), 2}, // unknown: unknown
	}
	for _, c := range cases {
		if got := c.l.Severity(); got != c.want {
			t.Errorf("Light(%q).Severity() = %d, want %d", c.l, got, c.want)
		}
	}
}
