package collect

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

const realMeminfo = `MemTotal:       32849568 kB
MemFree:         1234567 kB
MemAvailable:   21504000 kB
Buffers:          234567 kB
Cached:          5432100 kB
SwapCached:            0 kB
Active:          4567890 kB
Inactive:        2345678 kB
`

func TestMemAvailableMBRealFixture(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "meminfo")
	if err := writeFile(path, realMeminfo); err != nil {
		t.Fatal(err)
	}
	got, err := MemAvailableMB(path)
	if err != nil {
		t.Fatalf("MemAvailableMB: %v", err)
	}
	// 21504000 kB / 1024 = 21000 MB
	if got != 21000 {
		t.Errorf("MemAvailableMB: got %d want 21000", got)
	}
}

// TestMemAvailableMBFloor: 21504001 kB → 21000 MB (truncation, not
// rounding). The spec says "redondeo a la baja" — floor division.
func TestMemAvailableMBFloor(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "meminfo")
	if err := writeFile(path, "MemAvailable:   21504001 kB\n"); err != nil {
		t.Fatal(err)
	}
	got, err := MemAvailableMB(path)
	if err != nil {
		t.Fatal(err)
	}
	if got != 21000 {
		t.Errorf("floor: got %d want 21000", got)
	}
}

func TestMemAvailableMBSinLinea(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "meminfo")
	if err := writeFile(path, "MemTotal: 1000 kB\nMemFree: 500 kB\n"); err != nil {
		t.Fatal(err)
	}
	if _, err := MemAvailableMB(path); err == nil {
		t.Fatalf("expected error when MemAvailable is missing")
	}
}

func TestMemAvailableMBBasura(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "meminfo")
	if err := writeFile(path, "MemAvailable: not_a_number kB\n"); err != nil {
		t.Fatal(err)
	}
	_, err := MemAvailableMB(path)
	if err == nil {
		t.Fatalf("expected error for garbage value")
	}
	if !strings.Contains(err.Error(), "MemAvailable") {
		t.Errorf("error should mention MemAvailable, got %v", err)
	}
}

func TestMemAvailableMBArchivoAusente(t *testing.T) {
	if _, err := MemAvailableMB("/no/existe/meminfo"); err == nil {
		t.Fatalf("expected error for missing file")
	}
}

func writeFile(path, content string) error {
	return os.WriteFile(path, []byte(content), 0o644)
}
