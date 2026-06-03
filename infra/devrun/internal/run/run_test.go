package run

import (
	"context"
	"strings"
	"testing"
	"time"
)

func TestRealEcho(t *testing.T) {
	r := Real(time.Second)
	res := r(context.Background(), "/bin/echo", "hola")
	if res.Err != nil || res.ExitCode != 0 {
		t.Fatalf("echo: err=%v exit=%d", res.Err, res.ExitCode)
	}
	if strings.TrimSpace(res.Stdout) != "hola" {
		t.Errorf("stdout: got %q", res.Stdout)
	}
}

// A clean non-zero exit returns ExitCode and Err NIL — the contract
// every caller maps against. (Lesson from the resourced review,
// 2026-06-03: the original Runner returned Err here and collapsed
// real failures into "could not measure".)
func TestRealExitCodeNoZeroErrNil(t *testing.T) {
	r := Real(time.Second)
	res := r(context.Background(), "/bin/sh", "-c", "exit 7")
	if res.Err != nil {
		t.Fatalf("Err: expected nil for clean non-zero exit, got %v", res.Err)
	}
	if res.ExitCode != 7 {
		t.Errorf("ExitCode: got %d want 7", res.ExitCode)
	}
}

func TestRealTimeout(t *testing.T) {
	r := Real(100 * time.Millisecond)
	res := r(context.Background(), "/bin/sleep", "2")
	if res.Err == nil {
		t.Fatalf("expected timeout error")
	}
	if res.ExitCode != -1 {
		t.Errorf("ExitCode: got %d want -1", res.ExitCode)
	}
}

func TestRealBinaryNotFound(t *testing.T) {
	r := Real(time.Second)
	res := r(context.Background(), "/no/existe/binario")
	if res.Err == nil || res.ExitCode != -1 {
		t.Fatalf("expected start failure: err=%v exit=%d", res.Err, res.ExitCode)
	}
}
