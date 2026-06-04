// Package idle — audit summary of decisions.jsonl.
//
// The audit is the OPERATOR'S view of the daemon's shadow record:
// how many times would it have suspended laia-dev, for how long, with
// what would_free_mb total. The data is the substrate of the
// "verdict of the month" (see plan §9). The audit logic is PURE so
// tests can build fixtures in memory.
package idle

import (
	"bufio"
	"encoding/json"
	"fmt"
	"io"
	"os"
	"sort"
	"strings"
	"time"
)

// Episode is one idle streak: a suspend start, optional re-confirms,
// an end (or open). Open episodes have End.IsZero() == true.
type Episode struct {
	Target      string
	Start       time.Time
	End         time.Time
	StartReason string // reason of the first suspend
	WouldFreeMB int64
	StillCount  int
}

// TargetSummary aggregates episodes for a single target.
type TargetSummary struct {
	Target           string
	TotalEpisodes    int
	OpenEpisodes     int
	WouldFreeTotalMB int64
	Episodes         []Episode
}

// Summary is the full audit result.
type Summary struct {
	Since         time.Time
	Generated     time.Time
	Targets       []*TargetSummary // sorted by name
	TotalEpisodes int
	OpenEpisodes  int
	CorruptLines  int
}

// OpenEpisodesList returns the open episodes across all targets
// (sorted by start time). Convenience for the "episodios aún abiertos: N"
// line in the CLI render.
//
// The struct also has a numeric field OpenEpisodes (the count); this
// method is suffixed List to avoid the field/method name collision.
func (s *Summary) OpenEpisodesList() []Episode {
	var out []Episode
	for _, t := range s.Targets {
		for _, e := range t.Episodes {
			if e.End.IsZero() {
				out = append(out, e)
			}
		}
	}
	sort.Slice(out, func(i, j int) bool { return out[i].Start.Before(out[j].Start) })
	return out
}

// ReadDecisions opens path and returns the parsed decisions. A
// missing file is an error that the caller may choose to swallow
// (for the "no decisions yet" path). Corrupt lines are SKIPPED and
// counted, never returned as errors — the audit must be robust to
// operator-side JSON mistakes.
func ReadDecisions(path string) ([]Decision, int, error) {
	f, err := os.Open(path)
	if err != nil {
		return nil, 0, err
	}
	defer f.Close()
	return readDecisionsFrom(f)
}

func readDecisionsFrom(r io.Reader) ([]Decision, int, error) {
	var decs []Decision
	var corrupt int
	sc := bufio.NewScanner(r)
	for sc.Scan() {
		line := strings.TrimSpace(sc.Text())
		if line == "" {
			continue
		}
		var d Decision
		if err := json.Unmarshal([]byte(line), &d); err != nil {
			corrupt++
			continue
		}
		decs = append(decs, d)
	}
	if err := sc.Err(); err != nil {
		return nil, corrupt, err
	}
	return decs, corrupt, nil
}

// Audit builds the Summary from a list of decisions, filtered by
// `since`. Only decisions with TS >= since are considered. PURE —
// no I/O, easy to test with fixture decisions.
func Audit(decs []Decision, since time.Time, now time.Time) Summary {
	open := map[string]*Episode{} // target → current open episode
	targets := map[string]*TargetSummary{}

	getOrCreate := func(name string) *TargetSummary {
		if t, ok := targets[name]; ok {
			return t
		}
		t := &TargetSummary{Target: name}
		targets[name] = t
		return t
	}

	for _, d := range decs {
		if d.TS.Before(since) {
			continue
		}
		t := getOrCreate(d.Target)
		switch d.Kind {
		case "suspend":
			ep := &Episode{
				Target:      d.Target,
				Start:       d.TS,
				StartReason: d.Reason,
				WouldFreeMB: d.WouldFreeMB,
			}
			open[d.Target] = ep
		case "suspend_still":
			if ep, ok := open[d.Target]; ok {
				ep.StillCount++
			}
		case "end_idle":
			if ep, ok := open[d.Target]; ok {
				ep.End = d.TS
				t.Episodes = append(t.Episodes, *ep)
				delete(open, d.Target)
			} else {
				// orphan end_idle: emit a zero-duration episode so
				// it shows up in the audit (not silently dropped).
				t.Episodes = append(t.Episodes, Episode{
					Target: d.Target, Start: d.TS, End: d.TS, StartReason: d.Reason,
				})
			}
		}
	}

	// Any still-open episodes at the end of the file.
	for _, ep := range open {
		t := getOrCreate(ep.Target)
		t.Episodes = append(t.Episodes, *ep)
	}

	// Summarize + sort.
	out := Summary{Since: since, Generated: now}
	for _, t := range targets {
		t.TotalEpisodes = len(t.Episodes)
		for _, e := range t.Episodes {
			if e.End.IsZero() {
				t.OpenEpisodes++
				out.OpenEpisodes++
			}
			t.WouldFreeTotalMB += e.WouldFreeMB
		}
		sort.Slice(t.Episodes, func(i, j int) bool {
			return t.Episodes[i].Start.Before(t.Episodes[j].Start)
		})
		out.TotalEpisodes += t.TotalEpisodes
	}
	keys := make([]string, 0, len(targets))
	for k := range targets {
		keys = append(keys, k)
	}
	sort.Strings(keys)
	for _, k := range keys {
		out.Targets = append(out.Targets, targets[k])
	}
	return out
}

// ParseSince parses the --since argument. Accepted forms:
//
//	24h, 30m, 90s  (time.ParseDuration)
//	Nd              (N days, 24h each — not understood by ParseDuration)
//
// An empty string defaults to "30d". The reference "now" is an
// argument so tests can pin the clock.
func ParseSince(s string, now time.Time) (time.Time, error) {
	if s == "" {
		s = "30d"
	}
	var d time.Duration
	if strings.HasSuffix(s, "d") {
		n, err := parseInt(strings.TrimSuffix(s, "d"))
		if err != nil {
			return time.Time{}, fmt.Errorf("since: %q (expected Nd or duration)", s)
		}
		d = time.Duration(n) * 24 * time.Hour
	} else {
		var err error
		d, err = time.ParseDuration(s)
		if err != nil {
			return time.Time{}, fmt.Errorf("since: %q (expected Nd or duration)", s)
		}
	}
	return now.Add(-d), nil
}

func parseInt(s string) (int, error) {
	n := 0
	for _, r := range s {
		if r < '0' || r > '9' {
			return 0, fmt.Errorf("not a number: %q", s)
		}
		n = n*10 + int(r-'0')
	}
	if s == "" {
		return 0, fmt.Errorf("empty")
	}
	return n, nil
}
