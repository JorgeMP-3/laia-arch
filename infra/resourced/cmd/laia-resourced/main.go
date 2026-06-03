// laia-resourced — resource and host-invariant monitor daemon for LAIA.
//
// v1 (S0..S6): only monitors and warns. Does NOT mutate anything. The
// autonomy (enforce mode) comes after the month's verdict, via a
// config flip on the SAME binary ("deferred mutation" pattern).
//
// Runs as `laia-arch` (group lxd → lxc without sudo). Zero root in v1:
// every command it launches is read-only (see spec §0).
//
// Per-tick flow (see spec §3):
//  1. config: mtime changed? → reload (invalid → keep previous +
//     warn event "config", emitted by S2)
//  2. collect+evaluate each dimension. Egress is probed only every
//     probe_every_ticks; in between, the last Dimension is carried
//     forward (with its original CheckedAt)
//  3. compose Status (Overall = worst dimension, dev_idle excluded)
//     → state.WriteJSON (atomic)
//  4. alert.Process(light transitions) → events.jsonl (S2)
//  5. idle: laia-dev tracker → decisions.jsonl on threshold cross (S5)
//
// If a tick takes longer than tick_seconds, the ticker drops beats and
// the next tick runs immediately (this is what time.NewTicker does
// when the consumer is slow). It is deliberate: we prefer to coalesce
// ticks over queueing work. The only consequence is that egress
// carry-forwards may have age > 1 tick; the operator sees it in
// `laia-res status` ("measured 1m32s ago").
package main

import (
	"context"
	"flag"
	"log"
	"os"
	"os/signal"
	"path/filepath"
	"syscall"
	"time"

	"github.com/JorgeMP-3/laia-arch/infra/resourced/internal/alert"
	"github.com/JorgeMP-3/laia-arch/infra/resourced/internal/build"
	"github.com/JorgeMP-3/laia-arch/infra/resourced/internal/collect"
	"github.com/JorgeMP-3/laia-arch/infra/resourced/internal/config"
	"github.com/JorgeMP-3/laia-arch/infra/resourced/internal/evaluate"
	"github.com/JorgeMP-3/laia-arch/infra/resourced/internal/run"
	"github.com/JorgeMP-3/laia-arch/infra/resourced/internal/state"
)

func main() {
	var (
		stateDir = flag.String("state-dir", state.DefaultDir, "state directory")
		tick     = flag.Duration("tick", 30*time.Second, "interval between snapshots")
		mode     = flag.String("mode", "monitor", "monitor | enforce (v1: only monitor)")
		once     = flag.Bool("once", false, "run a single tick and exit (test/timer)")
		cfgPath  = flag.String("config", config.DefaultConfigPath, "path to the policy YAML")
	)
	flag.Parse()

	// v1 guardrail: the binary REJECTS enforce. Autonomy is enabled in a
	// later version after the month's verdict — not by an accidental
	// flag. config.Validate repeats this check.
	if *mode != "monitor" {
		log.Fatalf("mode %q not supported in v1 (only 'monitor')", *mode)
	}

	host, _ := os.Hostname()
	started := time.Now().UTC()

	// Load config at boot. If the path does not exist, defaults + WARN.
	watcher, err := config.NewWatcher(*cfgPath)
	if err != nil {
		log.Fatalf("config: %v", err)
	}
	if _, serr := os.Stat(*cfgPath); serr != nil && os.IsNotExist(serr) {
		log.Printf("WARN: no config at %s — using defaults", *cfgPath)
	}
	cfg := watcher.Current()
	log.Printf("laia-resourced %s starting (mode=%s tick=%s state=%s host=%s pid=%d services=%d probe-every=%d)",
		build.Version, *mode, *tick, *stateDir, host, os.Getpid(),
		len(cfg.Services), cfg.Egress.ProbeEveryTicks)

	ctx, stop := signal.NotifyContext(context.Background(), syscall.SIGINT, syscall.SIGTERM)
	defer stop()

	// Real Runner: each exec with its own hard 10s timeout (see
	// internal/run). In the implementer's VM lxc/curl may be missing;
	// the collector reflects this as ProbeBroken (unknown) — that IS
	// the contract.
	runner := run.Real(run.DefaultTimeout)

	// Alerter: events.jsonl + optional Telegram push. The sender is
	// nil if Telegram is disabled in the config (events still journaled
	// with PushSkipped="disabled").
	var sender alert.Sender
	if cfg.Alerts.Telegram.Enabled {
		sender = alert.NewTelegram(cfg.Alerts.Telegram.SecretsFile)
	}
	eventsPath := filepath.Join(*stateDir, "events.jsonl")
	alerter := alert.New(alert.AlertsConfig{
		ThrottleMinutes: cfg.Alerts.ThrottleMinutes,
		Host:            host,
	}, eventsPath, sender)

	var ticks uint64
	// Carry-forward state: only in memory. Restart → lost (documented
	// in spec §3). Conservative behavior: re-alerts.
	var prevEgress state.Dimension
	// Previous tick dimensions map, for the Alerter (transitions).
	// nil on the first tick, which means "everything was ok before".
	var prevDims map[string]state.Dimension

	snapshot := func() {
		ticks++

		// 1. Config hot-reload (fail-safe: keep previous on failure).
		if rerr := watcher.Reload(); rerr != nil {
			log.Printf("WARN: hot-reload of %s failed: %v (keeping previous)", *cfgPath, rerr)
			// Emit a config/warn event so the operator sees the failure
			// in events.jsonl (S2 deliverable).
			alerter.Process(prevDims, map[string]state.Dimension{
				"config": {Light: state.LightWarn, Detail: "hot-reload failed: " + rerr.Error(), CheckedAt: time.Now().UTC()},
			})
		}
		cfg = watcher.Current()

		now := time.Now().UTC()
		dims := map[string]state.Dimension{}

		// 2. Egress: probe only on tick 1 or when the counter
		// matches probe_every_ticks. In between, carry-forward with
		// the original CheckedAt (the UI shows "measured 1m32s ago"
		// rather than "4s ago").
		probeEvery := uint64(cfg.Egress.ProbeEveryTicks)
		shouldProbe := ticks == 1 || (probeEvery > 0 && ticks%probeEvery == 0)
		if shouldProbe {
			p := collect.Probe(ctx, runner, cfg.Egress.ProbeContainer, cfg.Egress.ProbeURL)
			prevEgress = evaluate.Egress(p, now, cfg.Egress.ReapplyScript)
		}
		dims["egress"] = prevEgress

		// 2b. RAM: read /proc/meminfo and apply the budget thresholds.
		// The collector takes the path as an arg (injectable for
		// tests). The real path is /proc/meminfo.
		if avail, err := collect.MemAvailableMB("/proc/meminfo"); err != nil {
			dims["ram"] = evaluate.RAMUnknown(now, err)
		} else {
			dims["ram"] = evaluate.RAM(avail, cfg.Budget, now)
		}

		// 2c. VRAM: nvidia-smi via the Runner. In the VM there is no
		// GPU → collector errors → unknown. In the host it returns
		// real MB.
		if used, total, free, gerr := collect.GPU(ctx, runner); gerr != nil {
			dims["vram"] = evaluate.VRAMUnknown(now, gerr)
		} else {
			dims["vram"] = evaluate.VRAM(used, total, free, cfg.Budget.VRAMMinFreeMB, now)
		}

		// 2d. Disk: one statfs per configured path. Aggregate via
		// evaluate.Disk (worst path wins).
		diskResults := make([]evaluate.DiskResult, 0, len(cfg.Budget.DiskPaths))
		for _, p := range cfg.Budget.DiskPaths {
			pct, mb, derr := collect.DiskFree(p)
			diskResults = append(diskResults, evaluate.DiskResult{
				Path: p, FreePct: pct, FreeMB: mb, Err: derr,
			})
		}
		dims["disk"] = evaluate.Disk(diskResults, cfg.Budget.DiskWarnFreePct, cfg.Budget.DiskRedFreePct, now)

		// 2e. Prod: lxc list once, then per-service alive (lxc/systemd/lxc_systemd).
		// If lxc list fails entirely, mark every critical lxc-based
		// service as unknown; systemd-based services still probe via
		// the Runner.
		var lxcStates map[string]string
		if ls, lerr := collect.LXCStates(ctx, runner); lerr != nil {
			log.Printf("WARN: lxc list failed: %v (marking lxc-based services unknown)", lerr)
			lxcStates = map[string]string{}
		} else {
			lxcStates = ls
		}
		serviceStates := collect.ServiceStates(ctx, runner, cfg.Services, lxcStates)
		prodDim, services := evaluate.Prod(evaluate.ProdInput{
			Services: cfg.Services, States: serviceStates,
		}, now)
		dims["prod"] = prodDim

		// Stash services for the Status write below.

		// 4. Alert: transitions vs the previous tick. First tick has
		// prevDims == nil; the alerter treats missing keys as ok.
		alerter.Process(prevDims, dims)

		// 3. Compose Status v2 + atomic write.
		st := state.Status{
			Schema:     state.SchemaVersion,
			Version:    build.Version,
			Mode:       *mode,
			Host:       host,
			PID:        os.Getpid(),
			StartedAt:  started,
			UpdatedAt:  now,
			Tick:       ticks,
			Overall:    evaluate.Overall(dims),
			Dimensions: dims,
			Services:   services,
		}
		if werr := state.WriteJSON(*stateDir, state.StatusFile, st); werr != nil {
			log.Printf("WARN: could not write state: %v", werr)
		}

		prevDims = dims
	}

	snapshot() // first tick immediate (state available at startup)
	if *once {
		return
	}

	t := time.NewTicker(*tick)
	defer t.Stop()
	for {
		select {
		case <-ctx.Done():
			log.Printf("signal received — clean exit after %d ticks", ticks)
			return
		case <-t.C:
			snapshot()
		}
	}
}
