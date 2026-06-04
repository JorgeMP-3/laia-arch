// Package config — declarative policy for laia-resourced.
//
// The policy lives in /srv/laia/arch/resourced.yaml (via --config flag)
// and is reloaded on every tick when mtime changes. If the file does
// not exist, the daemon starts with the embedded defaults (the same
// content as the committed resourced.example.yaml, single source of
// truth).
//
// Decoding is STRICT: an unknown field in YAML is an error, not
// silent — a typo in production is visible on the first tick, not
// discovered after damage.
package config

import (
	"bytes"
	_ "embed"
	"fmt"
	"os"
	"time"

	"gopkg.in/yaml.v3"
)

// Config is the 1:1 mirror of resourced.yaml. yaml.v3 tags, no renames,
// so the diff between an operator's YAML and the struct is trivial to
// audit.
type Config struct {
	Mode     string    `yaml:"mode"`
	Tick     int       `yaml:"tick_seconds"`
	Budget   Budget    `yaml:"budget"`
	Services []Service `yaml:"services"`
	Egress   Egress    `yaml:"egress"`
	Alerts   Alerts    `yaml:"alerts"`
}

// Budget groups thresholds per monitored resource. Field names follow
// the YAML exactly.
type Budget struct {
	RamProdBaselineMB int64    `yaml:"ram_prod_baseline_mb"`
	RamSafetyMarginMB int64    `yaml:"ram_safety_margin_mb"`
	RamWarnExtraMB    int64    `yaml:"ram_warn_extra_mb"`
	VRAMMinFreeMB     int64    `yaml:"vram_min_free_mb"`
	DiskWarnFreePct   int      `yaml:"disk_warn_free_pct"`
	DiskRedFreePct    int      `yaml:"disk_red_free_pct"`
	DiskPaths         []string `yaml:"disk_paths"`
}

// Service describes how a service is monitored: by name (operator
// reference), class (critical|dev) and the concrete liveness. The
// `idle` and `would_free_mb` fields only apply to class=dev and are
// consumed by S5 (laia-dev inactivity in shadow).
type Service struct {
	Name        string   `yaml:"name"`
	Class       string   `yaml:"class"`
	Liveness    Liveness `yaml:"liveness"`
	Idle        *Idle    `yaml:"idle,omitempty"`
	WouldFreeMB int64    `yaml:"would_free_mb,omitempty"`
}

// LivenessKind discriminates how service liveness is measured. The
// switch is centralized in S4 (Prod eval); here we only hold the
// discriminant and its fields.
const (
	LivenessLXC        = "lxc"
	LivenessSystemd    = "systemd"
	LivenessLXCSystemd = "lxc_systemd"
)

type Liveness struct {
	Kind      string   `yaml:"kind"`
	Container string   `yaml:"container,omitempty"`
	Units     []string `yaml:"units,omitempty"`
}

// Idle describes the criteria for considering laia-dev "idle" (S5).
// ssh=0 and tailscale=0 are IMPLICIT in the logic (not in config): an
// open SSH session is never idle even if load is zero. This is enforced
// in S5; here the struct only holds the rest.
type Idle struct {
	LoadBelow  float64 `yaml:"load_below"`
	ForMinutes int     `yaml:"for_minutes"`
}

// Egress groups the policy for the "internet egress" watchlist — the
// boot oneshot is external (systemd); the daemon only verifies and
// warns.
type Egress struct {
	Bridge          string `yaml:"bridge"`
	ProbeContainer  string `yaml:"probe_container"`
	ProbeURL        string `yaml:"probe_url"`
	ProbeEveryTicks int    `yaml:"probe_every_ticks"`
	ReapplyScript   string `yaml:"reapply_script"`
}

// Alerts governs alert emission. In v1 only Telegram; push channel is
// always direct to the API (the host always has internet, so it can
// alert on "containers lost egress"). Throttle per event kind
// (dimension key).
type Alerts struct {
	Telegram        Telegram `yaml:"telegram"`
	ThrottleMinutes int      `yaml:"throttle_minutes"`
}

type Telegram struct {
	Enabled     bool   `yaml:"enabled"`
	SecretsFile string `yaml:"secrets_file"`
}

// TickDuration returns tick_seconds as a Duration. Useful for tests
// that compare against time.NewTicker.
func (c Config) TickDuration() time.Duration { return time.Duration(c.Tick) * time.Second }

// DefaultConfigPath is the default YAML policy path. The VM does not
// use it (no /srv/laia in the implementer's smoke); the real host does.
const DefaultConfigPath = "/srv/laia/arch/resourced.yaml"

// exampleYAML embeds the committed file as the source of truth for
// defaults. A test verifies that the parsed version of this file
// matches what Defaults() returns byte-for-byte.
//
//go:embed resourced.example.yaml
var exampleYAML []byte

// Defaults returns the default config, parsed from the embedded YAML.
// It is what is used if --config does not exist (the daemon warns and
// continues).
func Defaults() (*Config, error) {
	return parse(exampleYAML)
}

// Load reads path and returns a *Config. If path does not exist, it
// returns defaults (documented scenario: daemon starts without config).
// If it exists but is invalid, it returns the error (caller decides
// whether to bail).
func Load(path string) (*Config, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		if os.IsNotExist(err) {
			return Defaults()
		}
		return nil, fmt.Errorf("read %s: %w", path, err)
	}
	return parse(data)
}

// parse is the pure decoding, separated from Load so tests can run
// against in-memory bytes (no filesystem).
func parse(data []byte) (*Config, error) {
	dec := yaml.NewDecoder(bytes.NewReader(data))
	dec.KnownFields(true) // strict: unknown field → error
	var c Config
	if err := dec.Decode(&c); err != nil {
		return nil, fmt.Errorf("yaml: %w", err)
	}
	if err := c.Validate(); err != nil {
		return nil, fmt.Errorf("validate: %w", err)
	}
	return &c, nil
}

// Validate enforces the minimum invariants. It is the second layer of
// the "monitor-only" guardrail (the first is the binary rejecting
// mode != monitor). Full table of tests in config_test.go.
//
// Rules:
//   - mode == "monitor" (v1 has no enforce)
//   - tick_seconds in [5, 600]
//   - throttle_minutes >= 1, probe_every_ticks >= 1
//   - budget thresholds > 0; disk_red < disk_warn (otherwise "red" would
//     be greater than "warn", the opposite of the intuition and would
//     break Overall composition)
//   - disk_paths not empty
//   - services: unique names, class in {critical, dev}, liveness.kind
//     in {lxc, systemd, lxc_systemd} with the minimum fields per kind
func (c *Config) Validate() error {
	if c.Mode != "monitor" {
		return fmt.Errorf("mode=%q not supported (v1 only 'monitor')", c.Mode)
	}
	if c.Tick < 5 || c.Tick > 600 {
		return fmt.Errorf("tick_seconds=%d out of [5, 600]", c.Tick)
	}
	if c.Alerts.ThrottleMinutes < 1 {
		return fmt.Errorf("throttle_minutes=%d must be >= 1", c.Alerts.ThrottleMinutes)
	}
	if c.Egress.ProbeEveryTicks < 1 {
		return fmt.Errorf("probe_every_ticks=%d must be >= 1", c.Egress.ProbeEveryTicks)
	}

	b := c.Budget
	if b.RamProdBaselineMB <= 0 || b.RamSafetyMarginMB <= 0 || b.RamWarnExtraMB <= 0 {
		return fmt.Errorf("ram_*_mb must be > 0")
	}
	if b.VRAMMinFreeMB <= 0 {
		return fmt.Errorf("vram_min_free_mb must be > 0")
	}
	if b.DiskWarnFreePct <= 0 || b.DiskRedFreePct <= 0 {
		return fmt.Errorf("disk_*_pct must be > 0")
	}
	if b.DiskRedFreePct >= b.DiskWarnFreePct {
		return fmt.Errorf("disk_red_free_pct=%d must be < disk_warn_free_pct=%d", b.DiskRedFreePct, b.DiskWarnFreePct)
	}
	if len(b.DiskPaths) == 0 {
		return fmt.Errorf("disk_paths must not be empty")
	}

	seen := map[string]bool{}
	for i, s := range c.Services {
		if s.Name == "" {
			return fmt.Errorf("services[%d].name empty", i)
		}
		if seen[s.Name] {
			return fmt.Errorf("services[%d].name=%q duplicate", i, s.Name)
		}
		seen[s.Name] = true
		if s.Class != "critical" && s.Class != "dev" {
			return fmt.Errorf("services[%d].class=%q must be critical|dev", i, s.Class)
		}
		if s.Liveness.Kind != LivenessLXC && s.Liveness.Kind != LivenessSystemd && s.Liveness.Kind != LivenessLXCSystemd {
			return fmt.Errorf("services[%d].liveness.kind=%q must be lxc|systemd|lxc_systemd", i, s.Liveness.Kind)
		}
		if s.Liveness.Kind == LivenessLXC || s.Liveness.Kind == LivenessLXCSystemd {
			if s.Liveness.Container == "" {
				return fmt.Errorf("services[%d].liveness.container empty (kind=%s)", i, s.Liveness.Kind)
			}
		}
		if s.Liveness.Kind == LivenessSystemd || s.Liveness.Kind == LivenessLXCSystemd {
			if len(s.Liveness.Units) == 0 {
				return fmt.Errorf("services[%d].liveness.units empty (kind=%s)", i, s.Liveness.Kind)
			}
		}
	}

	if c.Egress.ProbeContainer == "" || c.Egress.ProbeURL == "" {
		return fmt.Errorf("egress.probe_container and probe_url are required")
	}
	return nil
}
