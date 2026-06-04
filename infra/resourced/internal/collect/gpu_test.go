package collect

import (
	"context"
	"errors"
	"testing"

	"github.com/JorgeMP-3/laia-arch/infra/resourced/internal/run"
)

func TestParseGPUMemCSV(t *testing.T) {
	cases := []struct {
		name    string
		in      string
		wantU   int64
		wantT   int64
		wantF   int64
		wantErr bool
	}{
		{"typical", "1923, 8192, 6185", 1923, 8192, 6185, false},
		{"no spaces", "1923,8192,6185", 1923, 8192, 6185, false},
		{"lots of spaces", "  1923 ,  8192  ,  6185  ", 1923, 8192, 6185, false},
		{"empty", "", 0, 0, 0, true},
		{"no devices", "No devices found.", 0, 0, 0, true},
		{"too few fields", "1923, 8192", 0, 0, 0, true},
		{"garbage field", "abc, 8192, 6185", 0, 0, 0, true},
		{"with newline", "1923, 8192, 6185\n", 1923, 8192, 6185, false},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			u, total, f, err := parseGPUMemCSV(c.in)
			if c.wantErr {
				if err == nil {
					t.Fatalf("expected error")
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if u != c.wantU || total != c.wantT || f != c.wantF {
				t.Errorf("got (%d, %d, %d), want (%d, %d, %d)", u, total, f, c.wantU, c.wantT, c.wantF)
			}
		})
	}
}

func TestGPUFakeRunner(t *testing.T) {
	// Exits 0 with valid CSV → success.
	r := func(_ context.Context, name string, args ...string) run.Result {
		if name != "nvidia-smi" {
			return run.Result{ExitCode: -1, Err: errors.New("unexpected cmd: " + name)}
		}
		return run.Result{ExitCode: 0, Stdout: "100, 200, 100"}
	}
	used, total, free, err := GPU(testCtx(), r)
	if err != nil {
		t.Fatalf("GPU: %v", err)
	}
	if used != 100 || total != 200 || free != 100 {
		t.Errorf("got (%d, %d, %d)", used, total, free)
	}
}

func TestGPUNoRunner(t *testing.T) {
	if _, _, _, err := GPU(testCtx(), nil); err == nil {
		t.Errorf("expected error for nil runner")
	}
}

func TestGPUExitCodeNoZero(t *testing.T) {
	r := func(_ context.Context, name string, args ...string) run.Result {
		return run.Result{ExitCode: 1, Stdout: "some error"}
	}
	_, _, _, err := GPU(testCtx(), r)
	if err == nil {
		t.Errorf("expected error for non-zero exit")
	}
}
