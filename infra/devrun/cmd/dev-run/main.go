// dev-run — the host↔instances development bridge of the LAIA host.
//
// Edit on the host, run in the right destination: live bind-mounts
// into the dev cage (laia-test / laia-dev) for test/build/shell, and a
// gated, versioned, prepare/switch deploy for production targets. No
// daemon: this binary lives only while a command runs (0 MB resident).
//
// Spec: ~/laia-developers/workflow-main/plans/2026-06-03-dev-run-spec-minimax.md
package main

import (
	"context"
	"fmt"
	"os"
	"strings"
	"time"

	"github.com/JorgeMP-3/laia-arch/infra/devrun/internal/config"
	"github.com/JorgeMP-3/laia-arch/infra/devrun/internal/deploy"
	"github.com/JorgeMP-3/laia-arch/infra/devrun/internal/devmode"
	"github.com/JorgeMP-3/laia-arch/infra/devrun/internal/run"
)

// version is overridden at build time via -ldflags.
var version = "dev"

const usage = `uso:
  dev-run [--config PATH] [--dry-run] <proyecto> <acción> [-- <cmd>...]
  dev-run [--config PATH] [--dry-run] status
  dev-run version

acciones de proyecto:
  test | build      ejecuta el test_cmd/build_cmd del proyecto en su dev_target
  exec -- <cmd>     comando arbitrario dentro del dev_target (cwd = mount)
  shell             shell interactiva dentro del dev_target
  mount | umount    gestiona el bind-mount sin ejecutar nada
  stop              para el dev_target (se arrancó bajo demanda)
  deploy [--sha S]  ÚNICO camino a producción (preparar/conmutar + confirmación)

config por defecto: ` + config.DefaultPath + `
exit codes: el del comando interno · 2 = error de uso/config/jaula`

// cli is the parsed command line. Kept as a struct so parseArgs is
// table-testable without touching os.Args or flag globals.
type cli struct {
	configPath string
	dryRun     bool
	sha        string
	project    string
	action     string
	execArgs   []string
}

// parseArgs implements subcommand-first parsing (the flag package
// stops at the first positional, so a global FlagSet would lose
// `dev-run odoo test --dry-run`). Flags may appear anywhere before
// the `--` separator; everything after `--` belongs to exec.
func parseArgs(args []string) (cli, error) {
	c := cli{configPath: config.DefaultPath}
	var pos []string
	for i := 0; i < len(args); i++ {
		a := args[i]
		switch {
		case a == "--":
			c.execArgs = args[i+1:]
			i = len(args)
		case a == "--dry-run":
			c.dryRun = true
		case a == "--config":
			if i+1 >= len(args) {
				return c, fmt.Errorf("--config requiere un valor")
			}
			i++
			c.configPath = args[i]
		case strings.HasPrefix(a, "--config="):
			c.configPath = strings.TrimPrefix(a, "--config=")
		case a == "--sha":
			if i+1 >= len(args) {
				return c, fmt.Errorf("--sha requiere un valor")
			}
			i++
			c.sha = args[i]
		case strings.HasPrefix(a, "--sha="):
			c.sha = strings.TrimPrefix(a, "--sha=")
		case strings.HasPrefix(a, "-"):
			return c, fmt.Errorf("flag desconocida %q", a)
		default:
			pos = append(pos, a)
		}
	}
	switch len(pos) {
	case 0:
		return c, fmt.Errorf("falta el subcomando")
	case 1:
		// global subcommands
		if pos[0] == "status" || pos[0] == "version" {
			c.action = pos[0]
			return c, nil
		}
		return c, fmt.Errorf("falta la acción para el proyecto %q", pos[0])
	case 2:
		c.project, c.action = pos[0], pos[1]
		return c, nil
	default:
		return c, fmt.Errorf("demasiados argumentos: %v", pos)
	}
}

func main() {
	os.Exit(realMain(os.Args[1:]))
}

func realMain(args []string) int {
	c, err := parseArgs(args)
	if err != nil {
		fmt.Fprintf(os.Stderr, "dev-run: %v\n\n%s\n", err, usage)
		return 2
	}
	if c.action == "version" {
		fmt.Printf("dev-run %s\n", version)
		return 0
	}

	cfg, err := config.Load(c.configPath)
	if err != nil {
		fmt.Fprintf(os.Stderr, "dev-run: %v\n", err)
		return 2
	}

	ctx := context.Background()
	d := &devmode.Deps{
		Cfg:    cfg,
		R:      run.Real(run.DefaultTimeout),
		Stream: devmode.RealStreamer,
		Out:    os.Stderr, // progress lines; stdout stays clean for the inner command
		DryRun: c.dryRun,
		Sleep:  time.Sleep,
	}

	if c.action == "status" {
		return cmdStatus(ctx, d)
	}

	p, err := d.Project(c.project)
	if err != nil {
		fmt.Fprintf(os.Stderr, "dev-run: %v\n", err)
		return 2
	}

	fail := func(err error) int {
		fmt.Fprintf(os.Stderr, "dev-run: %v\n", err)
		return 2
	}

	switch c.action {
	case "test":
		if p.TestCmd == "" {
			return fail(fmt.Errorf("el proyecto %q no define test_cmd", c.project))
		}
		code, err := d.RunIn(ctx, c.project, p, p.TestCmd)
		if err != nil {
			return fail(err)
		}
		return code
	case "build":
		if p.BuildCmd == "" {
			return fail(fmt.Errorf("el proyecto %q no define build_cmd", c.project))
		}
		code, err := d.RunIn(ctx, c.project, p, p.BuildCmd)
		if err != nil {
			return fail(err)
		}
		return code
	case "exec":
		if len(c.execArgs) == 0 {
			return fail(fmt.Errorf("exec requiere un comando tras `--`"))
		}
		code, err := d.RunIn(ctx, c.project, p, strings.Join(c.execArgs, " "))
		if err != nil {
			return fail(err)
		}
		return code
	case "shell":
		code, err := d.Shell(ctx, c.project, p)
		if err != nil {
			return fail(err)
		}
		return code
	case "mount":
		inst, err := d.EnsureUp(ctx, p.DevTarget)
		if err != nil {
			return fail(err)
		}
		if err := d.EnsureMount(ctx, c.project, p, inst); err != nil {
			return fail(err)
		}
		return 0
	case "umount":
		if err := d.Unmount(ctx, c.project, p); err != nil {
			return fail(err)
		}
		return 0
	case "stop":
		if err := d.StopTarget(ctx, p); err != nil {
			return fail(err)
		}
		return 0
	case "deploy":
		return cmdDeploy(ctx, d, c, p)
	default:
		return fail(fmt.Errorf("acción desconocida %q", c.action))
	}
}

// cmdStatus lands in S5; the stub keeps the CLI surface complete.
func cmdStatus(_ context.Context, _ *devmode.Deps) int {
	fmt.Fprintln(os.Stderr, "dev-run: status llega en S5")
	return 2
}

// stdinIsTTY uses the char-device bit (stdlib only — no x/term dep):
// pipes and redirections drop it, interactive terminals have it.
func stdinIsTTY() bool {
	fi, err := os.Stdin.Stat()
	return err == nil && fi.Mode()&os.ModeCharDevice != 0
}

func cmdDeploy(ctx context.Context, d *devmode.Deps, c cli, p config.Project) int {
	dd := &deploy.Deps{
		Cfg:    d.Cfg,
		R:      d.R,
		Stream: deploy.Streamer(devmode.RealStreamer),
		In:     os.Stdin,
		Out:    os.Stderr,
		DryRun: c.dryRun,
		IsTTY:  stdinIsTTY,
	}
	code, err := deploy.Run(ctx, dd, c.project, p, c.sha)
	if err != nil {
		fmt.Fprintf(os.Stderr, "dev-run: %v\n", err)
	}
	return code
}
