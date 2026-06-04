//go:build linux
// +build linux

package collect

import (
	"testing"
)

func TestDiskFreePathReal(t *testing.T) {
	// /tmp is a tmpfs in the VM (small) or the host root; either way
	// the call must not error.
	pct, mb, err := DiskFree("/tmp")
	if err != nil {
		t.Fatalf("DiskFree /tmp: %v", err)
	}
	if pct < 0 || pct > 100 {
		t.Errorf("pct out of range: %f", pct)
	}
	if mb < 0 {
		t.Errorf("mb negative: %d", mb)
	}
}

func TestDiskFreePathInexistente(t *testing.T) {
	_, _, err := DiskFree("/no/existe/este/path/disk")
	if err == nil {
		t.Errorf("expected error for non-existent path")
	}
}
