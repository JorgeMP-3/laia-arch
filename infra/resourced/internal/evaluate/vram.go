package evaluate

import (
	"fmt"
	"strings"
	"time"

	"github.com/JorgeMP-3/laia-arch/infra/resourced/internal/state"
)

// DiskResult is the per-path measurement produced by the collector.
// If Err is non-nil, FreePct/FreeMB are zero and the path is treated
// as "unknown" in the aggregate.
type DiskResult struct {
	Path    string
	FreePct float64
	FreeMB  int64
	Err     error
}

// Disk aggregates per-path results into ONE dimension. The light is
// the worst across paths: a single full disk turns the whole
// dimension red, because a full disk kills prod (logs, DB, temp
// files). A single unknown path makes the dimension unknown (the
// operator must see "we could not measure" rather than a fake green).
//
// Format mirrors the spec: "/ 81% libre · /mnt/data 95% libre". A
// path with Err is appended as "<path> unknown (<err>)".
func Disk(results []DiskResult, warnPct, redPct int, now time.Time) state.Dimension {
	if len(results) == 0 {
		return state.Dimension{
			Light:     state.LightUnknown,
			Detail:    "no disk paths configured",
			CheckedAt: now,
		}
	}
	parts := make([]string, 0, len(results))
	worst := state.LightOK
	metrics := map[string]int64{}
	for _, r := range results {
		var pl state.Light
		if r.Err != nil {
			pl = state.LightUnknown
			parts = append(parts, fmt.Sprintf("%s unknown (%v)", r.Path, r.Err))
		} else {
			switch {
			case r.FreePct < float64(redPct):
				pl = state.LightRed
			case r.FreePct < float64(warnPct):
				pl = state.LightWarn
			default:
				pl = state.LightOK
			}
			parts = append(parts, fmt.Sprintf("%s %.0f%% libre", r.Path, r.FreePct))
		}
		if pl.Severity() > worst.Severity() {
			worst = pl
		}
		metrics[r.Path] = r.FreeMB
	}
	return state.Dimension{
		Light:     worst,
		Detail:    strings.Join(parts, " · "),
		Metrics:   metrics,
		CheckedAt: now,
	}
}

// VRAM is the GPU memory evaluator. In v1 it NEVER returns red — the
// spec's plan: "aviso si libre < 1 GB". Red is reserved for v2
// decisions (e.g., refusing to load a model). Error from the
// collector → unknown (no fake green).
func VRAM(used, total, freeMB, warnFreeMB int64, now time.Time) state.Dimension {
	detail := fmt.Sprintf("free %d/%d MB (warn <%d)", freeMB, total, warnFreeMB)
	light := state.LightOK
	if freeMB < warnFreeMB {
		light = state.LightWarn
	}
	return state.Dimension{
		Light:     light,
		Detail:    detail,
		Metrics:   map[string]int64{"used_mb": used, "total_mb": total, "free_mb": freeMB},
		CheckedAt: now,
	}
}

// VRAMUnknown returns the "could not measure" Dimension for VRAM.
func VRAMUnknown(now time.Time, err error) state.Dimension {
	detail := "could not read GPU memory"
	if err != nil {
		detail += ": " + err.Error()
	}
	return state.Dimension{
		Light:     state.LightUnknown,
		Detail:    detail,
		CheckedAt: now,
	}
}
