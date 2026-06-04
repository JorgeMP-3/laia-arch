// Package lxc — the read/act layer over the `lxc` CLI for dev-run.
//
// Every call goes through an injected run.Runner (see internal/run) so
// the whole package is table-testable without a host. The only state
// it reads is `lxc list`; the only mutations it performs are: start an
// instance, add/remove a *disk device* (the live bind-mount) — all of
// them gated upstream by the dev_instances whitelist (internal/config)
// and by --dry-run (the caller passes a printing Runner in that case).
package lxc

import (
	"context"
	"encoding/json"
	"fmt"
	"strings"
	"time"

	"github.com/JorgeMP-3/laia-arch/infra/devrun/internal/run"
)

// Instance is the minimum dev-run reads from `lxc list --format json`.
// Type matters: disk devices on containers need shift=true (idmap),
// on VMs virtiofs neither needs nor wants it — both facts verified on
// the host, 2026-06-03 (spec §1).
type Instance struct {
	Name   string `json:"name"`
	Status string `json:"status"` // "Running" | "Stopped" | ...
	Type   string `json:"type"`   // "container" | "virtual-machine"
}

// IsContainer reports whether the instance needs shift=true on mounts.
func (i Instance) IsContainer() bool { return i.Type == "container" }

// List returns name → Instance from a single `lxc list` round trip.
func List(ctx context.Context, r run.Runner) (map[string]Instance, error) {
	res := r(ctx, "lxc", "list", "--format", "json")
	if res.Err != nil {
		return nil, fmt.Errorf("lxc list: %w", res.Err)
	}
	if res.ExitCode != 0 {
		return nil, fmt.Errorf("lxc list: exit %d", res.ExitCode)
	}
	var insts []Instance
	if err := json.Unmarshal([]byte(res.Stdout), &insts); err != nil {
		return nil, fmt.Errorf("lxc list: parse json: %w", err)
	}
	m := make(map[string]Instance, len(insts))
	for _, i := range insts {
		m[i.Name] = i
	}
	return m, nil
}

// Start boots a stopped instance. Idempotent at the caller level: only
// invoked when List reported "Stopped".
func Start(ctx context.Context, r run.Runner, name string) error {
	res := r(ctx, "lxc", "start", name)
	if res.Err != nil {
		return fmt.Errorf("lxc start %s: %w", name, res.Err)
	}
	if res.ExitCode != 0 {
		return fmt.Errorf("lxc start %s: exit %d", name, res.ExitCode)
	}
	return nil
}

// WaitReady polls `lxc exec <name> -- true` until the instance accepts
// commands (a VM needs its lxd-agent up, which takes a few seconds
// after start). attempts × interval bounds the wait; sleep is injected
// so tests run in microseconds.
func WaitReady(ctx context.Context, r run.Runner, name string, attempts int, interval time.Duration, sleep func(time.Duration)) error {
	if attempts <= 0 {
		attempts = 30
	}
	if sleep == nil {
		sleep = time.Sleep
	}
	for n := 0; n < attempts; n++ {
		res := r(ctx, "lxc", "exec", name, "--", "true")
		if res.Err == nil && res.ExitCode == 0 {
			return nil
		}
		sleep(interval)
	}
	return fmt.Errorf("la instancia %s no respondió tras %d intentos (¿agente lxd arrancando?)", name, attempts)
}

// DeviceList returns the device names configured on an instance, one
// per line of `lxc config device list`.
func DeviceList(ctx context.Context, r run.Runner, name string) ([]string, error) {
	res := r(ctx, "lxc", "config", "device", "list", name)
	if res.Err != nil {
		return nil, fmt.Errorf("lxc config device list %s: %w", name, res.Err)
	}
	if res.ExitCode != 0 {
		return nil, fmt.Errorf("lxc config device list %s: exit %d", name, res.ExitCode)
	}
	var out []string
	for _, l := range strings.Split(res.Stdout, "\n") {
		if l = strings.TrimSpace(l); l != "" {
			out = append(out, l)
		}
	}
	return out, nil
}

// DeviceAdd attaches a live bind-mount (disk device). shift=true ONLY
// for containers — verified fact, spec §1. Not idempotent by itself:
// the caller (devmode) checks DeviceList first.
func DeviceAdd(ctx context.Context, r run.Runner, inst Instance, devName, source, path string) error {
	args := []string{"config", "device", "add", inst.Name, devName, "disk",
		"source=" + source, "path=" + path}
	if inst.IsContainer() {
		args = append(args, "shift=true")
	}
	res := r(ctx, "lxc", args...)
	if res.Err != nil {
		return fmt.Errorf("lxc device add %s/%s: %w", inst.Name, devName, res.Err)
	}
	if res.ExitCode != 0 {
		return fmt.Errorf("lxc device add %s/%s: exit %d", inst.Name, devName, res.ExitCode)
	}
	return nil
}

// DeviceRemove detaches a device. Idempotent: if the device is not in
// DeviceList, it returns nil without touching lxc.
func DeviceRemove(ctx context.Context, r run.Runner, name, devName string) error {
	devs, err := DeviceList(ctx, r, name)
	if err != nil {
		return err
	}
	found := false
	for _, d := range devs {
		if d == devName {
			found = true
			break
		}
	}
	if !found {
		return nil
	}
	res := r(ctx, "lxc", "config", "device", "remove", name, devName)
	if res.Err != nil {
		return fmt.Errorf("lxc device remove %s/%s: %w", name, devName, res.Err)
	}
	if res.ExitCode != 0 {
		return fmt.Errorf("lxc device remove %s/%s: exit %d", name, devName, res.ExitCode)
	}
	return nil
}

// Stop powers off an instance. The whitelist gate lives in the caller
// (devmode refuses anything outside dev_instances).
func Stop(ctx context.Context, r run.Runner, name string) error {
	res := r(ctx, "lxc", "stop", name)
	if res.Err != nil {
		return fmt.Errorf("lxc stop %s: %w", name, res.Err)
	}
	if res.ExitCode != 0 {
		return fmt.Errorf("lxc stop %s: exit %d", name, res.ExitCode)
	}
	return nil
}
