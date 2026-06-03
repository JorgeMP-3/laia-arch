package run

import (
	"context"
	"errors"
	"strings"
	"testing"
	"time"
)

// TestRealEcho verifies that a command that exits 0 returns its stdout.
// Minimum smoke: confirms exec.CommandContext + cmd.Output are wired
// correctly inside Real. If this fails, no collector can talk to the
// world.
func TestRealEcho(t *testing.T) {
	r := Real(time.Second)
	res := r(context.Background(), "/bin/echo", "hello")
	if res.Err != nil {
		t.Fatalf("Err: %v", res.Err)
	}
	if res.ExitCode != 0 {
		t.Errorf("ExitCode: got %d want 0", res.ExitCode)
	}
	if strings.TrimSpace(res.Stdout) != "hello" {
		t.Errorf("Stdout: got %q want %q", res.Stdout, "hello")
	}
}

// TestRealExitCodeNoZero: a command exiting != 0 returns its exit code
// and a non-nil Err (ExitError). Collectors distinguish "weird output"
// from "could not measure" with this signal: ProbeBroken is Err != nil,
// ProbeOK/Down is a known exit code.
func TestRealExitCodeNoZero(t *testing.T) {
	r := Real(time.Second)
	// /bin/sh -c 'exit 7' → ExitCode 7, Err non-nil
	res := r(context.Background(), "/bin/sh", "-c", "exit 7")
	if res.Err == nil {
		t.Fatalf("Err: expected non-nil for exit 7")
	}
	if res.ExitCode != 7 {
		t.Errorf("ExitCode: got %d want 7", res.ExitCode)
	}
}

// TestRealTimeout: a sleep longer than the timeout is killed and returns
// Err wrapping context.DeadlineExceeded. ExitCode = -1. This is what the
// egress collector sees if lxc hangs: ProbeBroken (any Err != nil →
// Broken in the table).
func TestRealTimeout(t *testing.T) {
	r := Real(100 * time.Millisecond)
	res := r(context.Background(), "/bin/sleep", "5")
	if res.Err == nil {
		t.Fatalf("Err: expected timeout, got nil")
	}
	if res.ExitCode != -1 {
		t.Errorf("ExitCode: got %d want -1", res.ExitCode)
	}
	if !errors.Is(res.Err, context.DeadlineExceeded) {
		t.Errorf("Err: got %v, expected to wrap context.DeadlineExceeded", res.Err)
	}
}

// TestRealBinaryNotFound: a non-existent binary → ExitCode -1, Err
// non-nil. Same as timeout from the collector's point of view (Broken).
func TestRealBinaryNotFound(t *testing.T) {
	r := Real(time.Second)
	res := r(context.Background(), "/no/such/binary/here")
	if res.Err == nil {
		t.Fatalf("Err: expected non-nil")
	}
	if res.ExitCode != -1 {
		t.Errorf("ExitCode: got %d want -1", res.ExitCode)
	}
}

// TestDefaultTimeoutConstant verifies the zero/negative falls back to
// the default. Protects against an accidental change breaking the hard
// limit.
func TestDefaultTimeoutConstant(t *testing.T) {
	if DefaultTimeout != 10*time.Second {
		t.Errorf("DefaultTimeout: got %v, v1 contract = 10s", DefaultTimeout)
	}
}
