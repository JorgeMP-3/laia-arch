package collect

import (
	"context"
	"errors"
	"fmt"
	"strconv"
	"strings"

	"github.com/JorgeMP-3/laia-arch/infra/resourced/internal/run"
)

// Activity is the per-tick measurement of the laia-dev container. The
// S5 idle tracker is PURE: it takes this and returns a decision; no
// state in the collector.
type Activity struct {
	SSHUsers       int
	TailscaleConns int
	Load1          float64
}

// DevActivity runs ONE lxc exec that concatenates who -q, /proc/loadavg
// and ss -Htn state established (separated by '---'), parses the
// output, and returns the Activity. tailscalePrefix is configurable
// (default "100.") so tests can pin it without a global.
//
// Command (the "what" is in the body, the "why" in the comment):
//
//	lxc exec <container> -- sh -c 'who -q; echo ---; \
//	    cat /proc/loadavg; echo ---; ss -Htn state established'
//
// We pack three things into one exec because the cost of one round
// trip to the container dominates three. The sh concatenates the
// outputs with the '---' separator; the parser splits on it.
//
// On error from the Runner, the caller should reset the idle tracker
// (rule 5 of §S5). This function returns the error; the caller
// decides what to do.
func DevActivity(ctx context.Context, r run.Runner, container, tailscalePrefix string) (Activity, error) {
	if r == nil {
		return Activity{}, errors.New("no runner")
	}
	if tailscalePrefix == "" {
		tailscalePrefix = "100."
	}
	shCmd := "who -q; echo ---; cat /proc/loadavg; echo ---; ss -Htn state established"
	res := r(ctx, "lxc", "exec", container, "--", "sh", "-c", shCmd)
	if res.Err != nil {
		return Activity{}, fmt.Errorf("dev activity: %w", shortRunnerErr(res.Err))
	}
	if res.ExitCode != 0 {
		return Activity{}, fmt.Errorf("dev activity: exit %d", res.ExitCode)
	}
	return parseDevActivity(res.Stdout, tailscalePrefix)
}

// parseDevActivity splits on the "---" separators emitted by the shell
// pipeline, then parses each section. The three sections are:
//
//  1. who -q output, variable lines, ending with "# users=N"
//  2. /proc/loadavg, one line: "0.12 0.17 0.12 1/334 9794"
//  3. ss -Htn state established, one line per socket
//
// The 3rd section is the most fragile: malformed lines (no Local
// address, fewer than 4 fields) are skipped silently — they cannot
// affect the idle verdict because the local address is what we filter
// on. Truly missing sections are errors (the operator should know).
func parseDevActivity(out, tailscalePrefix string) (Activity, error) {
	parts := strings.Split(out, "---")
	if len(parts) < 3 {
		return Activity{}, fmt.Errorf("dev activity: expected 3 sections, got %d", len(parts))
	}
	act := Activity{}

	// 1. who -q → # users=N
	whoLines := strings.Split(parts[0], "\n")
	for _, l := range whoLines {
		l = strings.TrimSpace(l)
		const prefix = "# users="
		if strings.HasPrefix(l, prefix) {
			n, err := strconv.Atoi(strings.TrimPrefix(l, prefix))
			if err != nil {
				return act, fmt.Errorf("dev activity: bad # users=%q: %w", l, err)
			}
			act.SSHUsers = n
		}
	}

	// 2. /proc/loadavg → first field of the first non-empty line.
	loadLines := strings.Split(strings.TrimSpace(parts[1]), "\n")
	if len(loadlinesTrimmed(loadLines)) == 0 {
		return act, errors.New("dev activity: loadavg section empty")
	}
	loadLine := loadlinesTrimmed(loadLines)[0]
	fields := strings.Fields(loadLine)
	if len(fields) == 0 {
		return act, errors.New("dev activity: loadavg empty")
	}
	f, err := strconv.ParseFloat(fields[0], 64)
	if err != nil {
		return act, fmt.Errorf("dev activity: bad loadavg field %q: %w", fields[0], err)
	}
	act.Load1 = f
	// Defensive: NaN/Inf would propagate to comparisons and break the
	// idle verdict silently. Reject anything that is not a finite,
	// non-negative number.
	if f != f /* NaN */ || f > 1e9 || f < 0 {
		return act, fmt.Errorf("dev activity: invalid loadavg %v", f)
	}

	// 3. ss -Htn state established → count lines whose local address
	// starts with tailscalePrefix OR ends with ":22" (SSH).
	ssLines := strings.Split(parts[2], "\n")
	for _, l := range ssLines {
		l = strings.TrimSpace(l)
		if l == "" {
			continue
		}
		fields := strings.Fields(l)
		if len(fields) < 4 {
			continue // malformed
		}
		local := fields[3]
		if isTailscaleOrSSH(local, tailscalePrefix) {
			act.TailscaleConns++
		}
	}
	return act, nil
}

// isTailscaleOrSSH: the local address (4th field of `ss`, 0-indexed)
// matches a "user is connected" signal if it is on the tailscale
// subnet (default 100.) OR the well-known SSH port 22. The
// "outgoing connections don't count" warning in §S5 is enforced
// implicitly: outgoing connections from the VM have ephemeral high
// local ports, so "port 22" naturally catches incoming SSH only and
// not VM-initiated HTTP/etc. The tailscale IP match covers incoming
// connections on the tailscale interface (which are, in practice,
// operator SSH or taildrop, i.e., user activity).
func isTailscaleOrSSH(local, tailscalePrefix string) bool {
	if strings.HasPrefix(local, tailscalePrefix) {
		return true
	}
	if strings.HasSuffix(local, ":22") {
		return true
	}
	return false
}

func loadlinesTrimmed(lines []string) []string {
	out := make([]string, 0, len(lines))
	for _, l := range lines {
		if strings.TrimSpace(l) != "" {
			out = append(out, l)
		}
	}
	return out
}
