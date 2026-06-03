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
		t.Errorf("round-trip no coincide:\n got  %+v\n want %+v", got, want)
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
			t.Errorf("fichero temporal sin limpiar: %s", e.Name())
		}
	}
}

func TestReadMissingIsNotExist(t *testing.T) {
	err := ReadJSON(filepath.Join(t.TempDir(), "nope.json"), &Status{})
	if !os.IsNotExist(err) {
		t.Errorf("esperaba os.IsNotExist, got %v", err)
	}
}
