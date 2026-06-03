// laia-res — CLI client for laia-resourced.
//
// Reads state from disk; does NOT need the daemon alive for `status`
// (that is why the daemon publishes to /srv/laia/state/resourced/ on
// every tick). In S1 the render is minimal: heartbeat + dimensions
// (one line each). S6 polishes it to an aligned table + semantic exit
// codes for scripts.
package main

import (
	"flag"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"time"

	"github.com/JorgeMP-3/laia-arch/infra/resourced/internal/build"
	"github.com/JorgeMP-3/laia-arch/infra/resourced/internal/state"
)

func main() {
	// Subcommand first, flags after: the flag package stops parsing at
	// the first positional, so `laia-res status --state-dir X` would
	// lose the flag if we used the global FlagSet. We extract the
	// subcommand and parse the rest with its own FlagSet → `status
	// --state-dir X`, `--state-dir X` (implicit status) and bare
	// `status` all work.
	args := os.Args[1:]
	cmd := "status"
	if len(args) > 0 && !strings.HasPrefix(args[0], "-") {
		cmd, args = args[0], args[1:]
	}

	fs := flag.NewFlagSet(cmd, flag.ExitOnError)
	stateDir := fs.String("state-dir", state.DefaultDir, "state directory")
	if err := fs.Parse(args); err != nil {
		os.Exit(2)
	}

	switch cmd {
	case "status":
		os.Exit(cmdStatus(*stateDir))
	case "version":
		fmt.Printf("laia-res %s\n", build.Version)
	default:
		fmt.Fprintf(os.Stderr, "usage: laia-res [status|version] [--state-dir DIR]\n")
		os.Exit(2)
	}
}

// cmdStatus reads status.json and renders it. S1: minimal render (S6
// polishes). Exit codes (S6 turns them into a contract):
//
//	0  → state is fresh and no red
//	1  → no state or stale
//	2  → some dimension is red
//
// In S1 the red exit is already wired (cheap to add) but S6 will turn
// the whole exit-code scheme into a documented contract.
func cmdStatus(dir string) int {
	path := filepath.Join(dir, state.StatusFile)
	var st state.Status
	if err := state.ReadJSON(path, &st); err != nil {
		if os.IsNotExist(err) {
			fmt.Printf("no state at %s — is laia-resourced running?\n", path)
			return 1
		}
		fmt.Fprintf(os.Stderr, "could not read %s: %v\n", path, err)
		return 1
	}

	age := time.Since(st.UpdatedAt).Round(time.Second)
	freshness := "fresh"
	if age > 2*time.Minute {
		freshness = "STALE (daemon may be down)"
	}
	fmt.Printf("laia-resourced  %s  mode=%s\n", st.Version, st.Mode)
	fmt.Printf("  host:        %s (pid %d)\n", st.Host, st.PID)
	fmt.Printf("  started:     %s\n", st.StartedAt.Local().Format("2006-01-02 15:04:05"))
	fmt.Printf("  last tick:   #%d %s ago — %s\n", st.Tick, age, freshness)
	if st.Overall != "" {
		fmt.Printf("  overall:     %s\n", strings.ToUpper(string(st.Overall)))
	}
	if len(st.Dimensions) > 0 {
		fmt.Println("  dimensions:")
		// Stable order so the output does not jump between runs.
		keys := make([]string, 0, len(st.Dimensions))
		for k := range st.Dimensions {
			keys = append(keys, k)
		}
		sortStrings(keys)
		for _, k := range keys {
			d := st.Dimensions[k]
			fmt.Printf("    %-9s %-7s %s\n", k, d.Light, d.Detail)
		}
	}
	if st.Overall == state.LightRed {
		return 2
	}
	return 0
}

// sortStrings avoids importing "sort" just for this (keeps the binary
// small; S6 will depend on more anyway).
func sortStrings(s []string) {
	for i := 1; i < len(s); i++ {
		for j := i; j > 0 && s[j-1] > s[j]; j-- {
			s[j-1], s[j] = s[j], s[j-1]
		}
	}
}
