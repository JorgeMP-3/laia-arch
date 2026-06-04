package collect

import (
	"context"
	"fmt"
	"strconv"
	"strings"

	"github.com/JorgeMP-3/laia-arch/infra/resourced/internal/run"
)

// GPU runs nvidia-smi and returns used, total, free memory in MB. The
// command (the "what" is in the body, the "why" in the comment):
//
//	nvidia-smi --query-gpu=memory.used,memory.total,memory.free \
//	           --format=csv,noheader,nounits
//
// - csv,noheader: 3 comma-separated numbers, no header
// - nounits: raw MB (no "MiB" suffix)
//
// We use one call (not per-stat) so the three numbers are from the
// same snapshot — internally consistent.
func GPU(ctx context.Context, r run.Runner) (used, total, free int64, err error) {
	if r == nil {
		return 0, 0, 0, fmt.Errorf("nvidia-smi: no runner")
	}
	res := r(ctx, "nvidia-smi",
		"--query-gpu=memory.used,memory.total,memory.free",
		"--format=csv,noheader,nounits")
	if res.Err != nil {
		return 0, 0, 0, fmt.Errorf("nvidia-smi: %w", shortRunnerErr(res.Err))
	}
	if res.ExitCode != 0 {
		return 0, 0, 0, fmt.Errorf("nvidia-smi: exit %d", res.ExitCode)
	}
	return parseGPUMemCSV(res.Stdout)
}

// parseGPUMemCSV is the pure parser, separated for table tests.
// Expected input: "1923, 8192, 6185" (or similar whitespace). The
// spec also requires handling "No devices found" from older drivers
// that output that as a single line.
func parseGPUMemCSV(out string) (int64, int64, int64, error) {
	s := strings.TrimSpace(out)
	if s == "" {
		return 0, 0, 0, fmt.Errorf("nvidia-smi: empty output")
	}
	if strings.Contains(strings.ToLower(s), "no devices") {
		return 0, 0, 0, fmt.Errorf("nvidia-smi: no devices found")
	}
	parts := strings.Split(s, ",")
	if len(parts) != 3 {
		return 0, 0, 0, fmt.Errorf("nvidia-smi: expected 3 fields, got %d (%q)", len(parts), s)
	}
	vals := [3]int64{}
	for i, p := range parts {
		v, err := strconv.ParseInt(strings.TrimSpace(p), 10, 64)
		if err != nil {
			return 0, 0, 0, fmt.Errorf("nvidia-smi: field %d: %w", i, err)
		}
		vals[i] = v
	}
	return vals[0], vals[1], vals[2], nil
}
