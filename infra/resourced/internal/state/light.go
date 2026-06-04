package state

// Light summarizes the verdict of a monitored dimension. There are four
// values, ordered by severity (see Severity):
//   - ok       → all good, normal reading
//   - warn     → tension, operator should look soon
//   - unknown  → could not measure (tool missing, lxc failed, etc.)
//   - red      → alarm, action required
//
// The 4th value "unknown" exists because "could not measure" is neither
// "all good" (a false green hides a problem) nor "alarm" (false alarm).
// In Overall it is treated as worse than warn: if a critical dimension
// cannot be measured, the operator must see it, not a silent green.
type Light string

const (
	LightOK      Light = "ok"
	LightWarn    Light = "warn"
	LightUnknown Light = "unknown"
	LightRed     Light = "red"
)

// Severity orders lights so Overall can be composed. The order matters:
// if a critical dimension drops to unknown while others are ok, Overall
// must be unknown (not ok). An unrecognized Light value (future, malformed)
// is treated as unknown — conservative by default.
func (l Light) Severity() int {
	switch l {
	case LightOK:
		return 0
	case LightWarn:
		return 1
	case LightUnknown:
		return 2
	case LightRed:
		return 3
	}
	return 2
}
