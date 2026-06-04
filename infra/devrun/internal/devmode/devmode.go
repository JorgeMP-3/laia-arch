// Package devmode implements the dev side of dev-run: resolve a
// project, make sure its dev target is up, ensure the live bind-mount,
// and run commands inside — with the dev_instances cage enforced at
// EVERY entry point (defense in depth: config.Validate already rejects
// bad configs, but the runtime guard holds even for hand-built ones).
//
// Two execution paths, on purpose:
//   - plumbing (list/start/wait/devices) goes through run.Runner —
//     captured output, table-testable;
//   - user commands (test/build/exec/shell) go through a Streamer that
//     attaches the caller's stdin/stdout/stderr, so suites stream live
//     and shells are interactive. Tests inject a fake Streamer.
//
// --dry-run gates BOTH paths before anything mutating: lxc start,
// device add/remove, lxc stop, and every Streamer call.
package devmode

import (
	"context"
	"fmt"
	"io"
	"os"
	"os/exec"
	"strings"
	"time"

	"github.com/JorgeMP-3/laia-arch/infra/devrun/internal/config"
	"github.com/JorgeMP-3/laia-arch/infra/devrun/internal/lxc"
	"github.com/JorgeMP-3/laia-arch/infra/devrun/internal/run"
)

// Streamer runs a command with the user's terminal attached and
// returns its exit code. The real one wires os.Stdin/out/err; tests
// inject a recorder.
type Streamer func(name string, args ...string) int

// RealStreamer attaches the current process streams. Exit code -1
// means the command could not start.
func RealStreamer(name string, args ...string) int {
	cmd := exec.Command(name, args...)
	cmd.Stdin = os.Stdin
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr
	if err := cmd.Run(); err != nil {
		if ee, ok := err.(*exec.ExitError); ok {
			return ee.ExitCode()
		}
		fmt.Fprintf(os.Stderr, "dev-run: no se pudo ejecutar %s: %v\n", name, err)
		return -1
	}
	return 0
}

// Deps carries everything devmode needs; main builds one per
// invocation, tests build it with fakes.
type Deps struct {
	Cfg    *config.Config
	R      run.Runner
	Stream Streamer
	Out    io.Writer // progress lines ("arrancado laia-test…")
	DryRun bool
	Sleep  func(time.Duration) // injected into WaitReady
}

func (d *Deps) printf(format string, a ...any) {
	if d.Out != nil {
		fmt.Fprintf(d.Out, format+"\n", a...)
	}
}

// Project resolves a project by name; the error lists what exists so
// the user does not have to open the YAML.
func (d *Deps) Project(name string) (config.Project, error) {
	p, ok := d.Cfg.Projects[name]
	if !ok {
		return config.Project{}, fmt.Errorf("proyecto %q no está en el registry; definidos: %s",
			name, strings.Join(d.Cfg.Names(), ", "))
	}
	return p, nil
}

// guardDev is THE cage. Every dev-mode operation calls it before any
// lxc verb. The message points to deploy on purpose: reaching a prod
// instance is not a missing feature, it is a different (gated) path.
func (d *Deps) guardDev(target string) error {
	if d.Cfg.IsDevInstance(target) {
		return nil
	}
	return fmt.Errorf("la instancia %q NO está en dev_instances (%s) — el modo dev jamás toca "+
		"instancias fuera de la jaula; para producción usa `dev-run <proyecto> deploy`",
		target, strings.Join(d.Cfg.DevInstances, ", "))
}

// EnsureUp makes sure the target exists and is Running (starting it on
// demand — laia-test lives stopped, P8). Returns the Instance so the
// caller knows container-vs-VM for the mount.
func (d *Deps) EnsureUp(ctx context.Context, target string) (lxc.Instance, error) {
	if err := d.guardDev(target); err != nil {
		return lxc.Instance{}, err
	}
	insts, err := lxc.List(ctx, d.R)
	if err != nil {
		return lxc.Instance{}, err
	}
	inst, ok := insts[target]
	if !ok {
		return lxc.Instance{}, fmt.Errorf("la instancia %q no existe en LXD", target)
	}
	if inst.Status == "Running" {
		return inst, nil
	}
	if d.DryRun {
		d.printf("[dry-run] arrancaría %s (está %s)", target, inst.Status)
		return inst, nil
	}
	d.printf("arrancando %s (bajo demanda)…", target)
	if err := lxc.Start(ctx, d.R, target); err != nil {
		return lxc.Instance{}, err
	}
	if err := lxc.WaitReady(ctx, d.R, target, 30, time.Second, d.Sleep); err != nil {
		return lxc.Instance{}, err
	}
	return inst, nil
}

// DeviceName is the canonical mount-device name for a project.
func DeviceName(project string) string { return "devrun-" + project }

// EnsureMount attaches the live bind-mount if it is not already there.
func (d *Deps) EnsureMount(ctx context.Context, project string, p config.Project, inst lxc.Instance) error {
	if err := d.guardDev(inst.Name); err != nil {
		return err
	}
	devs, err := lxc.DeviceList(ctx, d.R, inst.Name)
	if err != nil {
		return err
	}
	devName := DeviceName(project)
	for _, dev := range devs {
		if dev == devName {
			return nil // already mounted — idempotent
		}
	}
	if d.DryRun {
		d.printf("[dry-run] montaría %s → %s:%s", p.Source, inst.Name, p.MountPath)
		return nil
	}
	d.printf("montando %s → %s:%s", p.Source, inst.Name, p.MountPath)
	return lxc.DeviceAdd(ctx, d.R, inst, devName, p.Source, p.MountPath)
}

// Unmount removes the project's mount device (idempotent).
func (d *Deps) Unmount(ctx context.Context, project string, p config.Project) error {
	if err := d.guardDev(p.DevTarget); err != nil {
		return err
	}
	if d.DryRun {
		d.printf("[dry-run] desmontaría %s de %s", DeviceName(project), p.DevTarget)
		return nil
	}
	return lxc.DeviceRemove(ctx, d.R, p.DevTarget, DeviceName(project))
}

// StopTarget powers off the project's dev target (it was started on
// demand; it can be stopped the same way). Cage-guarded like the rest.
func (d *Deps) StopTarget(ctx context.Context, p config.Project) error {
	if err := d.guardDev(p.DevTarget); err != nil {
		return err
	}
	if d.DryRun {
		d.printf("[dry-run] pararía %s", p.DevTarget)
		return nil
	}
	return lxc.Stop(ctx, d.R, p.DevTarget)
}

// RunIn executes a shell command inside the project's dev target with
// the mount as working directory: the full pipeline (guard → up →
// mount → exec). Returns the INNER command's exit code — dev-run's
// exit code, so agents can script against it.
func (d *Deps) RunIn(ctx context.Context, project string, p config.Project, command string) (int, error) {
	inst, err := d.EnsureUp(ctx, p.DevTarget)
	if err != nil {
		return -1, err
	}
	if err := d.EnsureMount(ctx, project, p, inst); err != nil {
		return -1, err
	}
	if d.DryRun {
		d.printf("[dry-run] ejecutaría en %s (cwd %s): sh -c %q", p.DevTarget, p.MountPath, command)
		return 0, nil
	}
	return d.Stream("lxc", "exec", p.DevTarget, "--cwd", p.MountPath, "--", "sh", "-c", command), nil
}

// Shell opens an interactive bash inside the dev target, cwd at the
// mount. Same pipeline as RunIn.
func (d *Deps) Shell(ctx context.Context, project string, p config.Project) (int, error) {
	inst, err := d.EnsureUp(ctx, p.DevTarget)
	if err != nil {
		return -1, err
	}
	if err := d.EnsureMount(ctx, project, p, inst); err != nil {
		return -1, err
	}
	if d.DryRun {
		d.printf("[dry-run] abriría shell en %s (cwd %s)", p.DevTarget, p.MountPath)
		return 0, nil
	}
	return d.Stream("lxc", "exec", p.DevTarget, "--cwd", p.MountPath, "--", "bash"), nil
}
