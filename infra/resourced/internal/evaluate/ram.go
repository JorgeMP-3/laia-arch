package evaluate

import (
	"fmt"
	"time"

	"github.com/JorgeMP-3/laia-arch/infra/resourced/internal/config"
	"github.com/JorgeMP-3/laia-arch/infra/resourced/internal/state"
)

// RAM thresholds:
//
//	red   ⟺ available <  baseline + margin           (strict; equal is NOT red)
//	warn  ⟺ available <  baseline + margin + extra  (strict; equal is NOT warn)
//	ok    otherwise
//
// Equal-to-threshold is NOT red. The motivation is operational: a
// host that sits at exactly baseline+margin is "fine, but on the
// edge" — it deserves warn, not red. Red is reserved for "you are
// below the safety margin NOW" which is actionable.
//
// Error from the collector (no /proc, parse failure) is reflected as
// unknown, NOT as a red — the operator should see "could not read"
// rather than a fake red that triggers Telegram.
func RAM(availableMB int64, b config.Budget, now time.Time) state.Dimension {
	red := b.RamProdBaselineMB + b.RamSafetyMarginMB
	warn := red + b.RamWarnExtraMB
	light := state.LightOK
	switch {
	case availableMB < red:
		light = state.LightRed
	case availableMB < warn:
		light = state.LightWarn
	}
	return state.Dimension{
		Light:     light,
		Detail:    fmt.Sprintf("available %d MB (red <%d, warn <%d)", availableMB, red, warn),
		Metrics:   map[string]int64{"available_mb": availableMB},
		CheckedAt: now,
	}
}

// RAMUnknown returns a Dimension for the "collector failed" case. Kept
// separate from RAM() so the caller's intent is explicit and the
// Detail differs (we say "could not read", not "available X MB").
func RAMUnknown(now time.Time, err error) state.Dimension {
	detail := "could not read memory info"
	if err != nil {
		detail += ": " + err.Error()
	}
	return state.Dimension{
		Light:     state.LightUnknown,
		Detail:    detail,
		CheckedAt: now,
	}
}
