// Package collect — read-only collectors of host state.
//
// Each collector returns RAW measurements (numbers, strings, maps). The
// translation into a Dimension (light + detail + metrics) is done by
// the evaluators in internal/evaluate, which are PURE. This separation
// is what lets us test the whole logic without a real host: tests
// inject fake Runners with tables of (stdout, exit code).
package collect

import (
	"context"
	"strconv"
	"strings"

	"github.com/JorgeMP-3/laia-arch/infra/resourced/internal/run"
)

// ProbeOutcome is the verdict of the egress probe.
type ProbeOutcome int

const (
	ProbeOK     ProbeOutcome = iota // there is connectivity (HTTP 2xx/3xx, or 4xx/5xx = there was a response)
	ProbeDown                       // the container cannot reach the internet (DNS/connect/timeout/TLS)
	ProbeBroken                     // we could not measure (curl missing, lxc failed, etc.)
)

func (o ProbeOutcome) String() string {
	switch o {
	case ProbeOK:
		return "ok"
	case ProbeDown:
		return "down"
	case ProbeBroken:
		return "broken"
	}
	return "unknown"
}

// EgressProbe is the raw result of a probe. It does NOT include a
// Detail with "reapply script" — that is evaluator policy.
type EgressProbe struct {
	Outcome ProbeOutcome
	Detail  string
}

// Probe runs an HTTP curl inside `container` to verify it can reach
// the internet. The function is PURE with respect to the host: all I/O
// goes through r (injectable in tests). In production, r = run.Real(...).
//
// The command (long; the "what" is in the body, the "why" in the comment):
//
//		lxc exec <container> -- curl -4 -sS -o /dev/null -w %{http_code} \
//		    --max-time 8 <url>
//
//	  - -4 forces IPv4 (the P4000/host goes out via IPv4; avoid surprises
//	    with broken IPv6 routes)
//	  - -sS: silent except errors
//	  - -o /dev/null: discard body; we only want the code
//	  - -w %{http_code}: print the code at the end (stdout)
//	  - --max-time 8: 8s inside the container, gives room to the Runner's
//	    10s timeout (Run.Real)
func Probe(ctx context.Context, r run.Runner, container, url string) EgressProbe {
	if r == nil {
		return EgressProbe{Outcome: ProbeBroken, Detail: "no runner"}
	}
	res := r(ctx, "lxc", "exec", container, "--",
		"curl", "-4", "-sS", "-o", "/dev/null",
		"-w", "%{http_code}", "--max-time", "8", url)
	return mapProbe(res, container)
}

// mapProbe is the COMPLETE table of §S1 mapping Result → Outcome. The
// function is PURE: the only state it reads is res + container. The
// table is fully covered by egress_test.go.
func mapProbe(res run.Result, container string) EgressProbe {
	// The process never started: Runner timeout, binary missing, or
	// lxc failed. → Broken (we could not measure).
	if res.Err != nil {
		return EgressProbe{Outcome: ProbeBroken, Detail: shortErr(res.Err)}
	}
	code, _ := strconv.Atoi(strings.TrimSpace(res.Stdout))
	switch res.ExitCode {
	case 0:
		// exit 0 with an HTTP code: 2xx/3xx = OK, 4xx/5xx = OK as well
		// (the mirror responded, so there is connectivity — the
		// mirror may have a transient 404).
		switch {
		case code >= 200 && code < 400:
			return EgressProbe{Outcome: ProbeOK, Detail: "HTTP " + strconv.Itoa(code)}
		case code >= 400:
			return EgressProbe{Outcome: ProbeOK, Detail: "HTTP " + strconv.Itoa(code) + " (mirror responded)"}
		case code == 0:
			// exit 0 with no HTTP code: curl did not print anything
			// (rare: --max-time would have surfaced as exit 28).
			// We treat it as Broken to avoid a false green.
			return EgressProbe{Outcome: ProbeBroken, Detail: "exit 0 with no HTTP code"}
		default:
			return EgressProbe{Outcome: ProbeBroken, Detail: "exit 0 with HTTP code " + strconv.Itoa(code)}
		}
	case 6, 7, 28, 35:
		// curl: 6=resolve, 7=connect, 28=timeout, 35=TLS handshake.
		// These are the 4 signatures of "no internet egress".
		return EgressProbe{Outcome: ProbeDown, Detail: "curl exit " + strconv.Itoa(res.ExitCode) + " (DNS/connect/timeout/TLS)"}
	case 127:
		// curl not installed in the container. NOT egress down: it
		// is "tool missing" → Broken (unknown), not Down.
		return EgressProbe{Outcome: ProbeBroken, Detail: "curl is not installed in " + container}
	default:
		return EgressProbe{Outcome: ProbeBroken, Detail: "exit " + strconv.Itoa(res.ExitCode)}
	}
}

// shortErr summarizes the Runner error for the Broken Detail. Avoids
// exposing internals (tokens, full paths): just the type.
func shortErr(err error) string {
	if err == nil {
		return ""
	}
	// Deploy lesson (2026-06-03): hiding the cause behind a generic
	// "could not run the probe" cost real diagnosis time when the unit
	// sandbox blocked snap-confine. The probe command carries no
	// secrets (lxc exec + a public URL), so the message passes through
	// via the same policy as shortRunnerErr (timeout classified,
	// length capped).
	return shortRunnerErr(err).Error()
}
