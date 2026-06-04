package journal

import (
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

// TestAppendNLines: N appends → N parseable lines. This is the basic
// contract: if the daemon appends 100 events, audit/grep see 100
// well-formed JSON lines.
func TestAppendNLines(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "events.jsonl")
	for i := 0; i < 5; i++ {
		if err := Append(path, map[string]any{"i": i, "kind": "test"}); err != nil {
			t.Fatalf("Append %d: %v", i, err)
		}
	}
	// Read back and parse.
	data, err := readFile(t, path)
	if err != nil {
		t.Fatal(err)
	}
	lines := splitLines(string(data))
	if len(lines) != 5 {
		t.Fatalf("lines: got %d want 5 (%q)", len(lines), data)
	}
	for i, line := range lines {
		var m map[string]any
		if err := json.Unmarshal([]byte(line), &m); err != nil {
			t.Errorf("line %d unparseable: %v (%q)", i, err, line)
		}
		if int(m["i"].(float64)) != i {
			t.Errorf("line %d: i=%v want %d", i, m["i"], i)
		}
	}
}

// TestAppendCreatesDir: if the parent dir does not exist, Append
// creates it (idempotent with state.WriteJSON's behavior).
func TestAppendCreatesDir(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "subdir", "events.jsonl")
	if err := Append(path, map[string]any{"x": 1}); err != nil {
		t.Fatalf("Append: %v", err)
	}
}

// TestAppendSurvivesAcrossFiles: appending to a file that already has
// content from a previous run continues the line count, does not
// truncate.
func TestAppendSurvivesAcrossFiles(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "events.jsonl")
	if err := Append(path, map[string]any{"a": 1}); err != nil {
		t.Fatal(err)
	}
	if err := Append(path, map[string]any{"a": 2}); err != nil {
		t.Fatal(err)
	}
	data, _ := readFile(t, path)
	if got := len(splitLines(string(data))); got != 2 {
		t.Errorf("lines: got %d want 2", got)
	}
}

func readFile(t *testing.T, path string) ([]byte, error) {
	t.Helper()
	return os.ReadFile(path)
}

func splitLines(s string) []string {
	// Trim trailing empty line if the file ends with \n
	s = strings.TrimRight(s, "\n")
	if s == "" {
		return nil
	}
	return strings.Split(s, "\n")
}
