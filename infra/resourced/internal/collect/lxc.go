package collect

import (
	"context"
	"encoding/json"
	"fmt"

	"github.com/JorgeMP-3/laia-arch/infra/resourced/internal/run"
)

// LXCInstance is the minimum we read from `lxc list --format json`.
// Status is the raw value from LXD: "Running", "Stopped", "Error",
// "Starting", etc. We do not model the full enum — the evaluator
// only checks for "Running" vs anything-else.
type LXCInstance struct {
	Name   string `json:"name"`
	Status string `json:"status"`
}

// LXCStates runs `lxc list --format json` once and returns
// name→status. A single call covers all containers (one lxc round
// trip per tick, not one per service). Errors are returned so the
// caller can decide whether to set the prod dimension to unknown
// (lxd unreachable) or to fall back to per-container lxc exec
// (rare; we do not do that in v1).
func LXCStates(ctx context.Context, r run.Runner) (map[string]string, error) {
	if r == nil {
		return nil, fmt.Errorf("lxc list: no runner")
	}
	res := r(ctx, "lxc", "list", "--format", "json")
	if res.Err != nil {
		return nil, fmt.Errorf("lxc list: %w", shortRunnerErr(res.Err))
	}
	if res.ExitCode != 0 {
		return nil, fmt.Errorf("lxc list: exit %d", res.ExitCode)
	}
	var insts []LXCInstance
	if jerr := json.Unmarshal([]byte(res.Stdout), &insts); jerr != nil {
		return nil, fmt.Errorf("lxc list: parse json: %w", jerr)
	}
	m := make(map[string]string, len(insts))
	for _, i := range insts {
		m[i.Name] = i.Status
	}
	return m, nil
}
