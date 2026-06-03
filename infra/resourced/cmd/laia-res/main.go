// laia-res — CLI client for laia-resourced.
//
// Reads state from disk; does NOT need the daemon alive for `status`
// or `audit` (that is why the daemon publishes to
// /srv/laia/state/resourced/ on every tick).
//
// Subcommands:
//
//	status   — render the latest status.json (aligned table +
//	           exit code 0/1/2 for scripts).
//	audit    — summarize decisions.jsonl (the shadow record). The
//	           "verdict of the month" feeds off this.
//	version  — print the binary version.
package main

import (
	"flag"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"text/tabwriter"
	"time"

	"github.com/JorgeMP-3/laia-arch/infra/resourced/internal/build"
	"github.com/JorgeMP-3/laia-arch/infra/resourced/internal/idle"
	"github.com/JorgeMP-3/laia-arch/infra/resourced/internal/state"
)

func main() {
	args := os.Args[1:]
	cmd := "status"
	if len(args) > 0 && !strings.HasPrefix(args[0], "-") {
		cmd, args = args[0], args[1:]
	}
	switch cmd {
	case "status":
		os.Exit(cmdStatus(args))
	case "audit":
		os.Exit(cmdAudit(args))
	case "version":
		fmt.Printf("laia-res %s\n", build.Version)
	default:
		fmt.Fprintf(os.Stderr, "usage: laia-res [status|audit|version] [--state-dir DIR] [--since Nd]\n")
		os.Exit(2)
	}
}

// cmdStatus renders status.json.
//
// Exit codes (S6 contract):
//
//	0  → state is fresh and no dimension is red
//	1  → no state file, stale state, or read error
//	2  → state is fresh but some dimension is red
//
// If the file's schema is higher than the one this binary knows
// about, a warning is printed to stderr and we render best-effort
// (unknown fields are dropped by the JSON unmarshal).
func cmdStatus(args []string) int {
	fs := flag.NewFlagSet("status", flag.ExitOnError)
	stateDir := fs.String("state-dir", state.DefaultDir, "state directory")
	if err := fs.Parse(args); err != nil {
		os.Exit(2)
	}
	path := filepath.Join(*stateDir, state.StatusFile)
	var st state.Status
	if err := state.ReadJSON(path, &st); err != nil {
		if os.IsNotExist(err) {
			fmt.Printf("no state at %s — is laia-resourced running?\n", path)
			return 1
		}
		fmt.Fprintf(os.Stderr, "could not read %s: %v\n", path, err)
		return 1
	}
	if st.Schema > state.SchemaVersion {
		fmt.Fprintf(os.Stderr,
			"WARN: status.json schema=%d > binary schema=%d — best-effort render\n",
			st.Schema, state.SchemaVersion)
	}

	age := time.Since(st.UpdatedAt).Round(time.Second)
	freshness := "fresh"
	if age > 2*time.Minute {
		freshness = "STALE (daemon may be down)"
	}
	overallLabel := strings.ToUpper(string(st.Overall))
	if st.Overall == "" {
		overallLabel = "(none)"
	}
	fmt.Printf("laia-resourced %s  mode=%s  host=%s (pid %d)\n",
		st.Version, st.Mode, st.Host, st.PID)
	fmt.Printf("last tick: #%d %s ago — %s      overall: %s\n\n",
		st.Tick, age, freshness, overallLabel)

	if len(st.Dimensions) > 0 {
		tw := tabwriter.NewWriter(os.Stdout, 0, 0, 2, ' ', 0)
		fmt.Fprintln(tw, "DIMENSION\tLIGHT\tDETAIL")
		keys := sortedDimKeys(st.Dimensions)
		for _, k := range keys {
			d := st.Dimensions[k]
			fmt.Fprintf(tw, "%s\t%s\t%s\n", k, d.Light, d.Detail)
		}
		tw.Flush()
		fmt.Println()
	}
	if len(st.Services) > 0 {
		tw := tabwriter.NewWriter(os.Stdout, 0, 0, 2, ' ', 0)
		fmt.Fprintln(tw, "SERVICE\tCLASS\tSTATE\tDETAIL")
		keys := sortedServiceKeys(st.Services)
		for _, k := range keys {
			s := st.Services[k]
			detail := s.Detail
			if detail == "" {
				detail = "-"
			}
			fmt.Fprintf(tw, "%s\t%s\t%s\t%s\n", k, s.Class, s.Alive, detail)
		}
		tw.Flush()
	}
	if st.Overall == state.LightRed {
		return 2
	}
	return 0
}

// cmdAudit summarizes decisions.jsonl. Exit 0 always (a missing
// file is "no decisions yet", not an error).
func cmdAudit(args []string) int {
	fs := flag.NewFlagSet("audit", flag.ExitOnError)
	stateDir := fs.String("state-dir", state.DefaultDir, "state directory")
	since := fs.String("since", "", "time window: 30d (default), 24h, 7d, 1d, or any Go duration")
	if err := fs.Parse(args); err != nil {
		os.Exit(2)
	}
	path := filepath.Join(*stateDir, "decisions.jsonl")
	decs, corruptAtRead, err := idle.ReadDecisions(path)
	if err != nil {
		if os.IsNotExist(err) {
			fmt.Println("no shadow decisions recorded yet (has the daemon been running long enough?)")
			return 0
		}
		fmt.Fprintf(os.Stderr, "could not read %s: %v\n", path, err)
		return 1
	}
	now := time.Now()
	sinceTime, perr := idle.ParseSince(*since, now)
	if perr != nil {
		fmt.Fprintf(os.Stderr, "%v\n", perr)
		return 2
	}
	summary := idle.Audit(decs, sinceTime, now)
	windowStr := *since
	if windowStr == "" {
		windowStr = "30d"
	}
	fmt.Printf("audit of shadow decisions — last %s (since %s)\n\n",
		windowStr, sinceTime.Format("2006-01-02"))

	if summary.TotalEpisodes == 0 {
		fmt.Println("no episodes in this window.")
		fmt.Printf("open episodes: 0\ncorrupt lines skipped: %d\n", summary.CorruptLines)
		return 0
	}

	for _, t := range summary.Targets {
		fmt.Printf("%s: %d idle episodes → would have suspended %d times (would_free %d MB)\n",
			t.Target, t.TotalEpisodes, t.TotalEpisodes, t.WouldFreeTotalMB)
		for _, e := range t.Episodes {
			if e.End.IsZero() {
				fmt.Printf("  · %s → OPEN   reason: %s\n",
					e.Start.Local().Format("2006-01-02 15:04"), e.StartReason)
			} else {
				dur := e.End.Sub(e.Start).Round(time.Minute)
				fmt.Printf("  · %s → %s (%s)  reason: %s\n",
					e.Start.Local().Format("2006-01-02 15:04"),
					e.End.Local().Format("15:04"),
					dur, e.StartReason)
			}
		}
	}
	openEps := summary.OpenEpisodesList()
	if len(openEps) > 0 {
		fmt.Printf("open episodes: %d", len(openEps))
		for _, e := range openEps {
			fmt.Printf(" (since %s on %s)", e.Start.Local().Format("2006-01-02 15:04"), e.Target)
		}
		fmt.Println()
	}
	fmt.Printf("corrupt lines skipped: %d\n", corruptAtRead)
	return 0
}

func sortedDimKeys(m map[string]state.Dimension) []string {
	keys := make([]string, 0, len(m))
	for k := range m {
		keys = append(keys, k)
	}
	sortStrings(keys)
	return keys
}

func sortedServiceKeys(m map[string]state.ServiceState) []string {
	keys := make([]string, 0, len(m))
	for k := range m {
		keys = append(keys, k)
	}
	sortStrings(keys)
	return keys
}

func sortStrings(s []string) {
	// Insertion sort: small slices, no need for sort.Strings.
	for i := 1; i < len(s); i++ {
		for j := i; j > 0 && s[j-1] > s[j]; j-- {
			s[j-1], s[j] = s[j], s[j-1]
		}
	}
}
