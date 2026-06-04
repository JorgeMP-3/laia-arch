// Package config defines the dev-targets.yaml schema for dev-run.
//
// The registry lives at ~/laia-developers/dev-targets.yaml and is the
// machine-readable companion to the canonical projects table in
// AGENTS.md. dev-run reads it on every invocation (no hot-reload — the
// CLI is short-lived and re-parsing is cheap; the config file is the
// authorization for what dev-run may mount/exec).
//
// Decoding is strict (yaml.KnownFields(true)): a typo in a key is an
// error, not a silent default. Validation rejects, with a clear
// message, every shape that could let dev-run reach a non-dev instance
// or produce an ambiguous mount.
package config

import (
	"bytes"
	"errors"
	"fmt"
	"os"
	"path/filepath"

	"gopkg.in/yaml.v3"
)

// DefaultPath is where dev-run looks for dev-targets.yaml when --config
// is not given. The companion machine-readable to AGENTS.md §4 table.
const DefaultPath = "~/laia-developers/dev-targets.yaml"

// Config is the root of dev-targets.yaml.
//
// dev_instances is the closed whitelist of LXD instances where dev-run
// may mount, exec, test, build, or stop. A target outside this set is
// rejected by every subcommand — the whitelist is the single source of
// truth, and it trumps anything the per-project blocks say.
//
// projects is the per-project recipe: what to mount, where, with which
// command. Validation enforces dev_target ∈ dev_instances and
// prod_target ∉ dev_instances (deploy is the only path that may touch
// a prod target, and it does so via the dedicated switch, never via a
// mount).
type Config struct {
	DevInstances []string           `yaml:"dev_instances"`
	Projects     map[string]Project `yaml:"projects"`
}

// Project is the per-project recipe for dev-run.
type Project struct {
	// Source is the host directory to bind-mount into the dev target.
	// Must be an absolute, existing directory.
	Source string `yaml:"source"`

	// DevTarget is the LXD instance where test/build/exec/shell/mount
	// are run. Must be listed in config.DevInstances.
	DevTarget string `yaml:"dev_target"`

	// MountPath is the absolute path inside DevTarget where the
	// source is exposed. The mount device is named "devrun-<project>".
	MountPath string `yaml:"mount_path"`

	// TestCmd and BuildCmd are run with `sh -c` inside the dev
	// target, with --cwd set to MountPath. They are optional (a
	// project may have only test, only build, or neither — exec/shell
	// always work). The command's exit code is dev-run's exit code.
	TestCmd  string `yaml:"test_cmd,omitempty"`
	BuildCmd string `yaml:"build_cmd,omitempty"`

	// ProdTarget is the LXD instance where `deploy` will prepare
	// the release tarball and run the deploy script. Optional: a
	// project without it cannot be deployed via dev-run (deploy is
	// rejected). It MUST NOT be in DevInstances.
	ProdTarget string `yaml:"prod_target,omitempty"`

	// DeployCmd is the script that runs INSIDE ProdTarget to switch
	// the runtime to the prepared release. dev-run does not know
	// what it does; it only sets DEVRUN_RELEASE_DIR in the env and
	// execs the script with `sh -c`. Required when ProdTarget is
	// set; ignored otherwise.
	DeployCmd string `yaml:"deploy_cmd,omitempty"`
}

// Load reads, decodes, and validates the YAML at path. The path may
// use a leading "~/" which is expanded to the user's home directory
// (dev-run never imports the resourced module, but the convention
// matches the example file and the AGENTS.md table path).
func Load(path string) (*Config, error) {
	expanded, err := expandHome(path)
	if err != nil {
		return nil, fmt.Errorf("config: %w", err)
	}
	data, err := os.ReadFile(expanded)
	if err != nil {
		return nil, fmt.Errorf("config: read %s: %w", expanded, err)
	}
	return Parse(data)
}

// Parse decodes and validates a config from in-memory YAML bytes.
// Used by tests; also by Load.
func Parse(data []byte) (*Config, error) {
	dec := yaml.NewDecoder(bytes.NewReader(data))
	dec.KnownFields(true) // strict: typo in a key is an error
	var c Config
	if err := dec.Decode(&c); err != nil {
		return nil, fmt.Errorf("config: parse yaml: %w", err)
	}
	if err := c.Validate(); err != nil {
		return nil, err
	}
	return &c, nil
}

// Validate enforces the integrity rules of a Config. It is called by
// Parse; it can also be called directly on a Config built in tests.
//
// The rules encode the cage: dev_run mounts/execs only into the
// closed whitelist; deploy goes only to non-whitelisted prod targets.
// A malformed config is rejected before dev-run reaches lxc.
func (c *Config) Validate() error {
	if len(c.DevInstances) == 0 {
		return errors.New("config: dev_instances must list at least one instance (the dev cage)")
	}
	inst := make(map[string]struct{}, len(c.DevInstances))
	for _, d := range c.DevInstances {
		if d == "" {
			return errors.New("config: dev_instances contains an empty entry")
		}
		if _, dup := inst[d]; dup {
			return fmt.Errorf("config: dev_instances has duplicate %q", d)
		}
		inst[d] = struct{}{}
	}
	if len(c.Projects) == 0 {
		return errors.New("config: projects must list at least one project")
	}
	seen := make(map[string]struct{}, len(c.Projects))
	for name, p := range c.Projects {
		if name == "" {
			return errors.New("config: a project has an empty name")
		}
		if _, dup := seen[name]; dup {
			return fmt.Errorf("config: duplicate project %q", name)
		}
		seen[name] = struct{}{}
		if err := p.validate(name, inst); err != nil {
			return err
		}
	}
	return nil
}

func (p *Project) validate(name string, devInstances map[string]struct{}) error {
	if !filepath.IsAbs(p.Source) {
		return fmt.Errorf("config: project %q: source %q must be absolute", name, p.Source)
	}
	if info, err := os.Stat(p.Source); err != nil || !info.IsDir() {
		return fmt.Errorf("config: project %q: source %q must be an existing directory", name, p.Source)
	}
	if p.DevTarget == "" {
		return fmt.Errorf("config: project %q: dev_target is required", name)
	}
	if _, ok := devInstances[p.DevTarget]; !ok {
		return fmt.Errorf("config: project %q: dev_target %q is not in dev_instances (cage: %v)", name, p.DevTarget, devInstances)
	}
	if !filepath.IsAbs(p.MountPath) {
		return fmt.Errorf("config: project %q: mount_path %q must be absolute", name, p.MountPath)
	}
	if p.ProdTarget != "" {
		if _, ok := devInstances[p.ProdTarget]; ok {
			return fmt.Errorf("config: project %q: prod_target %q is in dev_instances — deploy must not share a cage with dev", name, p.ProdTarget)
		}
		if p.DeployCmd == "" {
			return fmt.Errorf("config: project %q: deploy_cmd is required when prod_target is set", name)
		}
	} else if p.DeployCmd != "" {
		return fmt.Errorf("config: project %q: deploy_cmd is set but prod_target is empty", name)
	}
	return nil
}

// Names returns the project names, sorted — used in error messages so
// the user can see what the config actually defines.
func (c *Config) Names() []string {
	out := make([]string, 0, len(c.Projects))
	for n := range c.Projects {
		out = append(out, n)
	}
	// stable order for reproducible error messages
	for i := 1; i < len(out); i++ {
		for j := i; j > 0 && out[j-1] > out[j]; j-- {
			out[j-1], out[j] = out[j], out[j-1]
		}
	}
	return out
}

// IsDevInstance reports whether name is in the dev whitelist. It is
// the guard every mutating subcommand checks BEFORE any lxc call.
func (c *Config) IsDevInstance(name string) bool {
	for _, d := range c.DevInstances {
		if d == name {
			return true
		}
	}
	return false
}

// expandHome replaces a leading "~/" or a lone "~" with the current
// user's home directory. The user's home is read once via os.UserHomeDir.
func expandHome(path string) (string, error) {
	if path == "" {
		return "", errors.New("empty path")
	}
	if path[0] != '~' {
		return path, nil
	}
	home, err := os.UserHomeDir()
	if err != nil {
		return "", fmt.Errorf("resolve ~: %w", err)
	}
	if path == "~" {
		return home, nil
	}
	if len(path) > 1 && path[1] == '/' {
		return filepath.Join(home, path[2:]), nil
	}
	return path, nil
}
