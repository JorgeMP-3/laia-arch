package config

import (
	"os"
	"path/filepath"
	"reflect"
	"testing"
	"time"
)

// TestDefaultsParsesExample verifies that the committed YAML parses
// without error and the result passes Validate. If someone breaks the
// example, this test fails before any runtime.
func TestDefaultsParsesExample(t *testing.T) {
	cfg, err := Defaults()
	if err != nil {
		t.Fatalf("Defaults: %v", err)
	}
	if cfg.Mode != "monitor" {
		t.Errorf("Mode: got %q want monitor", cfg.Mode)
	}
	if cfg.Tick != 30 {
		t.Errorf("Tick: got %d want 30", cfg.Tick)
	}
	if len(cfg.Services) != 13 {
		t.Errorf("Services count: got %d want 13 (12 critical + 1 dev)", len(cfg.Services))
	}
	if cfg.Budget.RamProdBaselineMB != 5000 || cfg.Budget.RamSafetyMarginMB != 3000 {
		t.Errorf("Budget.Ram: got baseline=%d margin=%d", cfg.Budget.RamProdBaselineMB, cfg.Budget.RamSafetyMarginMB)
	}
	if cfg.Egress.ProbeContainer != "laia-edge" {
		t.Errorf("Egress.ProbeContainer: got %q want laia-edge", cfg.Egress.ProbeContainer)
	}
}

// TestExampleParseEqualsDefaults ensures the committed file produces the
// SAME config as the embedded defaults (because they share a single
// source). If someone edits one and not the other, this fails.
//
// Due to //go:embed's "no upward path" limitation, the file lives in
// TWO places: the canonical at infra/resourced/resourced.example.yaml
// (what the operator sees) and a copy at
// internal/config/resourced.example.yaml (next to config.go for the
// embed). If they diverge, this test fails.
func TestExampleParseEqualsDefaults(t *testing.T) {
	def, err := Defaults()
	if err != nil {
		t.Fatalf("Defaults: %v", err)
	}
	// Canonical: the path the operator finds.
	canonical, err := os.ReadFile("../../resourced.example.yaml")
	if err != nil {
		t.Fatalf("read canonical ../../resourced.example.yaml: %v", err)
	}
	// Embed (next to this test).
	embedCopy, err := os.ReadFile("resourced.example.yaml")
	if err != nil {
		t.Fatalf("read embed resourced.example.yaml: %v", err)
	}
	fromCanonical, err := parse(canonical)
	if err != nil {
		t.Fatalf("parse canonical: %v", err)
	}
	fromEmbed, err := parse(embedCopy)
	if err != nil {
		t.Fatalf("parse embed: %v", err)
	}
	// Embedded defaults == canonical == embed copy.
	if def.Tick != fromCanonical.Tick || def.Tick != fromEmbed.Tick {
		t.Errorf("Tick: def=%d canonical=%d embed=%d", def.Tick, fromCanonical.Tick, fromEmbed.Tick)
	}
	if !reflect.DeepEqual(def.Budget, fromCanonical.Budget) || !reflect.DeepEqual(def.Budget, fromEmbed.Budget) {
		t.Errorf("Budget diverges across the 3 sources\n def=%+v\n canonical=%+v\n embed=%+v", def.Budget, fromCanonical.Budget, fromEmbed.Budget)
	}
	if len(def.Services) != len(fromCanonical.Services) || len(def.Services) != len(fromEmbed.Services) {
		t.Fatalf("Services count: def=%d canonical=%d embed=%d", len(def.Services), len(fromCanonical.Services), len(fromEmbed.Services))
	}
	for i := range def.Services {
		if !reflect.DeepEqual(def.Services[i], fromCanonical.Services[i]) || !reflect.DeepEqual(def.Services[i], fromEmbed.Services[i]) {
			t.Errorf("services[%d] diverges across the 3 sources", i)
		}
	}
	if !reflect.DeepEqual(def.Egress, fromCanonical.Egress) || !reflect.DeepEqual(def.Egress, fromEmbed.Egress) {
		t.Errorf("Egress diverges across the 3 sources")
	}
	if !reflect.DeepEqual(def.Alerts, fromCanonical.Alerts) || !reflect.DeepEqual(def.Alerts, fromEmbed.Alerts) {
		t.Errorf("Alerts diverges across the 3 sources")
	}
}

// TestStrictRejectsUnknownKey: a typo in YAML must fail to parse. If
// it didn't, "mode: montiro" would be an unknown mode and never
// detected.
func TestStrictRejectsUnknownKey(t *testing.T) {
	yamlValid := `mode: monitor
tick_seconds: 30
budget: {ram_prod_baseline_mb: 1, ram_safety_margin_mb: 1, ram_warn_extra_mb: 1, vram_min_free_mb: 1, disk_warn_free_pct: 10, disk_red_free_pct: 5, disk_paths: ["/"]}
services: []
egress: {bridge: lxdbr0, probe_container: c, probe_url: "http://x", probe_every_ticks: 4, reapply_script: /x}
alerts: {telegram: {enabled: false, secrets_file: /x}, throttle_minutes: 1}
`
	withTypo := yamlValid + "  invento: true\n"
	if _, err := parse([]byte(withTypo)); err == nil {
		t.Fatalf("expected error for unknown key; parsed OK")
	}
}

// TestValidateRejectsEnforce: the double guardrail (binary + config)
// protects against an accidental flip.
func TestValidateRejectsEnforce(t *testing.T) {
	yamlEnforce := `mode: enforce
tick_seconds: 30
budget: {ram_prod_baseline_mb: 1, ram_safety_margin_mb: 1, ram_warn_extra_mb: 1, vram_min_free_mb: 1, disk_warn_free_pct: 10, disk_red_free_pct: 5, disk_paths: ["/"]}
services: []
egress: {bridge: lxdbr0, probe_container: c, probe_url: "http://x", probe_every_ticks: 4, reapply_script: /x}
alerts: {telegram: {enabled: false, secrets_file: /x}, throttle_minutes: 1}
`
	if _, err := parse([]byte(yamlEnforce)); err == nil {
		t.Fatalf("expected error for mode=enforce; parsed OK")
	}
}

// TestValidateTable: each validation rule rejecting invalid entries.
// Table-driven so adding a case is trivial.
func TestValidateTable(t *testing.T) {
	cases := []struct {
		name string
		yaml string
	}{
		{
			"tick_seconds too low",
			`mode: monitor
tick_seconds: 1
budget: {ram_prod_baseline_mb: 1, ram_safety_margin_mb: 1, ram_warn_extra_mb: 1, vram_min_free_mb: 1, disk_warn_free_pct: 10, disk_red_free_pct: 5, disk_paths: ["/"]}
services: []
egress: {bridge: lxdbr0, probe_container: c, probe_url: "http://x", probe_every_ticks: 4, reapply_script: /x}
alerts: {telegram: {enabled: false, secrets_file: /x}, throttle_minutes: 1}`,
		},
		{
			"throttle_minutes 0",
			`mode: monitor
tick_seconds: 30
budget: {ram_prod_baseline_mb: 1, ram_safety_margin_mb: 1, ram_warn_extra_mb: 1, vram_min_free_mb: 1, disk_warn_free_pct: 10, disk_red_free_pct: 5, disk_paths: ["/"]}
services: []
egress: {bridge: lxdbr0, probe_container: c, probe_url: "http://x", probe_every_ticks: 4, reapply_script: /x}
alerts: {telegram: {enabled: false, secrets_file: /x}, throttle_minutes: 0}`,
		},
		{
			"disk_red >= disk_warn",
			`mode: monitor
tick_seconds: 30
budget: {ram_prod_baseline_mb: 1, ram_safety_margin_mb: 1, ram_warn_extra_mb: 1, vram_min_free_mb: 1, disk_warn_free_pct: 5, disk_red_free_pct: 10, disk_paths: ["/"]}
services: []
egress: {bridge: lxdbr0, probe_container: c, probe_url: "http://x", probe_every_ticks: 4, reapply_script: /x}
alerts: {telegram: {enabled: false, secrets_file: /x}, throttle_minutes: 1}`,
		},
		{
			"service class invalid",
			`mode: monitor
tick_seconds: 30
budget: {ram_prod_baseline_mb: 1, ram_safety_margin_mb: 1, ram_warn_extra_mb: 1, vram_min_free_mb: 1, disk_warn_free_pct: 10, disk_red_free_pct: 5, disk_paths: ["/"]}
services:
  - {name: foo, class: rare, liveness: {kind: lxc, container: foo}}
egress: {bridge: lxdbr0, probe_container: c, probe_url: "http://x", probe_every_ticks: 4, reapply_script: /x}
alerts: {telegram: {enabled: false, secrets_file: /x}, throttle_minutes: 1}`,
		},
		{
			"lxc without container",
			`mode: monitor
tick_seconds: 30
budget: {ram_prod_baseline_mb: 1, ram_safety_margin_mb: 1, ram_warn_extra_mb: 1, vram_min_free_mb: 1, disk_warn_free_pct: 10, disk_red_free_pct: 5, disk_paths: ["/"]}
services:
  - {name: foo, class: critical, liveness: {kind: lxc}}
egress: {bridge: lxdbr0, probe_container: c, probe_url: "http://x", probe_every_ticks: 4, reapply_script: /x}
alerts: {telegram: {enabled: false, secrets_file: /x}, throttle_minutes: 1}`,
		},
		{
			"systemd without units",
			`mode: monitor
tick_seconds: 30
budget: {ram_prod_baseline_mb: 1, ram_safety_margin_mb: 1, ram_warn_extra_mb: 1, vram_min_free_mb: 1, disk_warn_free_pct: 10, disk_red_free_pct: 5, disk_paths: ["/"]}
services:
  - {name: foo, class: critical, liveness: {kind: systemd}}
egress: {bridge: lxdbr0, probe_container: c, probe_url: "http://x", probe_every_ticks: 4, reapply_script: /x}
alerts: {telegram: {enabled: false, secrets_file: /x}, throttle_minutes: 1}`,
		},
		{
			"duplicate services",
			`mode: monitor
tick_seconds: 30
budget: {ram_prod_baseline_mb: 1, ram_safety_margin_mb: 1, ram_warn_extra_mb: 1, vram_min_free_mb: 1, disk_warn_free_pct: 10, disk_red_free_pct: 5, disk_paths: ["/"]}
services:
  - {name: foo, class: critical, liveness: {kind: lxc, container: a}}
  - {name: foo, class: critical, liveness: {kind: lxc, container: b}}
egress: {bridge: lxdbr0, probe_container: c, probe_url: "http://x", probe_every_ticks: 4, reapply_script: /x}
alerts: {telegram: {enabled: false, secrets_file: /x}, throttle_minutes: 1}`,
		},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			if _, err := parse([]byte(c.yaml)); err == nil {
				t.Fatalf("expected error; parsed OK")
			}
		})
	}
}

// TestLoadDefaultsIfMissing: if the path does not exist, Load returns
// defaults (documented scenario).
func TestLoadDefaultsIfMissing(t *testing.T) {
	cfg, err := Load("/no/such/path/resourced.yaml")
	if err != nil {
		t.Fatalf("Load: %v (expected silent defaults)", err)
	}
	if cfg.Mode != "monitor" {
		t.Errorf("Mode: got %q want monitor", cfg.Mode)
	}
}

// TestWatcherHotReload: the watcher detects new mtime, reloads, and on
// invalid YAML PRESERVES the previous config. This is the "fail safe"
// contract of hot-reload.
func TestWatcherHotReload(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "resourced.yaml")

	// 1) First load with a valid YAML.
	first := []byte(`mode: monitor
tick_seconds: 30
budget: {ram_prod_baseline_mb: 1, ram_safety_margin_mb: 1, ram_warn_extra_mb: 1, vram_min_free_mb: 1, disk_warn_free_pct: 10, disk_red_free_pct: 5, disk_paths: ["/"]}
services: []
egress: {bridge: lxdbr0, probe_container: c, probe_url: "http://x", probe_every_ticks: 4, reapply_script: /x}
alerts: {telegram: {enabled: false, secrets_file: /x}, throttle_minutes: 1}
`)
	if err := os.WriteFile(path, first, 0o644); err != nil {
		t.Fatal(err)
	}
	w, err := NewWatcher(path)
	if err != nil {
		t.Fatalf("NewWatcher: %v", err)
	}
	if w.Current().Tick != 30 {
		t.Fatalf("first load: Tick=%d want 30", w.Current().Tick)
	}

	// 2) Overwrite with BROKEN YAML. Force future mtime (1h ahead) so
	// the watcher detects it even if the FS has 1s resolution.
	broken := []byte(`mode: montiro  # typo
tick_seconds: 60
budget: {ram_prod_baseline_mb: 1, ram_safety_margin_mb: 1, ram_warn_extra_mb: 1, vram_min_free_mb: 1, disk_warn_free_pct: 10, disk_red_free_pct: 5, disk_paths: ["/"]}
services: []
egress: {bridge: lxdbr0, probe_container: c, probe_url: "http://x", probe_every_ticks: 4, reapply_script: /x}
alerts: {telegram: {enabled: false, secrets_file: /x}, throttle_minutes: 1}
`)
	if err := os.WriteFile(path, broken, 0o644); err != nil {
		t.Fatal(err)
	}
	future := time.Now().Add(time.Hour)
	if err := os.Chtimes(path, future, future); err != nil {
		t.Fatal(err)
	}
	if rerr := w.Reload(); rerr == nil {
		t.Fatalf("Reload: expected error for invalid YAML")
	}
	if w.Current().Tick != 30 {
		t.Errorf("invalid reload should preserve Tick=30, got %d", w.Current().Tick)
	}

	// 3) New valid YAML with tick_seconds=60.
	good := []byte(`mode: monitor
tick_seconds: 60
budget: {ram_prod_baseline_mb: 1, ram_safety_margin_mb: 1, ram_warn_extra_mb: 1, vram_min_free_mb: 1, disk_warn_free_pct: 10, disk_red_free_pct: 5, disk_paths: ["/"]}
services: []
egress: {bridge: lxdbr0, probe_container: c, probe_url: "http://x", probe_every_ticks: 4, reapply_script: /x}
alerts: {telegram: {enabled: false, secrets_file: /x}, throttle_minutes: 1}
`)
	if err := os.WriteFile(path, good, 0o644); err != nil {
		t.Fatal(err)
	}
	future2 := time.Now().Add(2 * time.Hour)
	if err := os.Chtimes(path, future2, future2); err != nil {
		t.Fatal(err)
	}
	if rerr := w.Reload(); rerr != nil {
		t.Fatalf("Reload good: %v", rerr)
	}
	if w.Current().Tick != 60 {
		t.Errorf("Reload good: Tick=%d want 60", w.Current().Tick)
	}
}

// TestWatcherNoReloadIfMtimeEqual: idempotency — a Reload with no
// change must not waste work or fail.
func TestWatcherNoReloadIfMtimeEqual(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "resourced.yaml")
	if err := os.WriteFile(path, []byte("mode: monitor\ntick_seconds: 30\nbudget: {ram_prod_baseline_mb: 1, ram_safety_margin_mb: 1, ram_warn_extra_mb: 1, vram_min_free_mb: 1, disk_warn_free_pct: 10, disk_red_free_pct: 5, disk_paths: [\"/\"]}\nservices: []\negress: {bridge: lxdbr0, probe_container: c, probe_url: \"http://x\", probe_every_ticks: 4, reapply_script: /x}\nalerts: {telegram: {enabled: false, secrets_file: /x}, throttle_minutes: 1}\n"), 0o644); err != nil {
		t.Fatal(err)
	}
	w, err := NewWatcher(path)
	if err != nil {
		t.Fatal(err)
	}
	if rerr := w.Reload(); rerr != nil {
		t.Errorf("idempotent Reload: %v", rerr)
	}
}
