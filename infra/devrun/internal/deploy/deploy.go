// Package deploy implements the ONLY path from dev-run to a
// production instance: prepare/switch with versioned artifacts —
// never a live mount (a live mount in prod would inherit every host
// keystroke instantly; see design-rules §Mutación diferida).
//
//	PRECONDICIONES  git clean + main + HEAD==origin/main (solo se
//	                despliega lo commiteado, pusheado y revisado)
//	PREPARAR        git archive HEAD → tar → /srv/deploy/<proy>/<sha>/
//	                (aditivo: el runtime no cambia todavía)
//	CONFIRMAR       SIEMPRE interactivo: teclear el nombre del target.
//	                Sin TTY → rechazo (nadie deploya a prod desatendido)
//	CONMUTAR        deploy_cmd del proyecto DENTRO del target, con
//	                DEVRUN_RELEASE_DIR en el entorno. dev-run no sabe
//	                de Odoo ni de symlinks: eso es del proyecto.
//
// Rollback: `deploy --sha <S>` salta PREPARAR si /srv/deploy/<proy>/<S>
// ya existe en el target (los dirs no se borran) y va directo a
// CONFIRMAR+CONMUTAR.
//
// --dry-run: preconditions run (read-only git), everything else is
// SIMULATED. The spec said prepare could run on dry-run; we keep the
// global invariant "dry-run never mutates" instead — noted as a
// review decision (2026-06-03).
package deploy

import (
	"bufio"
	"context"
	"fmt"
	"io"
	"os"
	"path"
	"strings"

	"github.com/JorgeMP-3/laia-arch/infra/devrun/internal/config"
	"github.com/JorgeMP-3/laia-arch/infra/devrun/internal/run"
)

// Streamer mirrors devmode.Streamer (kept local to avoid coupling the
// two modes): runs with the user's terminal attached, returns exit code.
type Streamer func(name string, args ...string) int

// Deps carries the seams. main builds it with the real ones; tests
// inject fakes for everything (runner, streamer, stdin, TTY check).
type Deps struct {
	Cfg    *config.Config
	R      run.Runner
	Stream Streamer
	In     io.Reader // confirmation input (os.Stdin in production)
	Out    io.Writer // progress + prompts
	DryRun bool
	IsTTY  func() bool
	TmpDir string // where the tarball is staged on the host ("" → os.TempDir)
}

func (d *Deps) printf(format string, a ...any) {
	if d.Out != nil {
		fmt.Fprintf(d.Out, format+"\n", a...)
	}
}

// gitOut runs a git command in the project source and returns trimmed
// stdout; any failure is an error (these are read-only preconditions).
func (d *Deps) gitOut(ctx context.Context, source string, args ...string) (string, error) {
	full := append([]string{"-C", source}, args...)
	res := d.R(ctx, "git", full...)
	if res.Err != nil {
		return "", fmt.Errorf("git %s: %w", strings.Join(args, " "), res.Err)
	}
	if res.ExitCode != 0 {
		return "", fmt.Errorf("git %s: exit %d", strings.Join(args, " "), res.ExitCode)
	}
	return strings.TrimSpace(res.Stdout), nil
}

// Run executes the whole deploy. Returns the process exit code.
func Run(ctx context.Context, d *Deps, project string, p config.Project, sha string) (int, error) {
	if p.ProdTarget == "" {
		return 2, fmt.Errorf("el proyecto %q no define prod_target — no se puede deployar con dev-run", project)
	}
	// Defense in depth: a prod target inside the dev cage means the
	// config is lying somewhere. Refuse loudly.
	if d.Cfg.IsDevInstance(p.ProdTarget) {
		return 2, fmt.Errorf("prod_target %q está en dev_instances — config inconsistente, no deployo", p.ProdTarget)
	}

	// ── PRECONDICIONES (solo cuando preparamos desde HEAD) ──────────
	if sha == "" {
		porcelain, err := d.gitOut(ctx, p.Source, "status", "--porcelain")
		if err != nil {
			return 2, err
		}
		if porcelain != "" {
			return 2, fmt.Errorf("working tree de %s con cambios sin commitear — a producción solo va lo commiteado", p.Source)
		}
		branch, err := d.gitOut(ctx, p.Source, "rev-parse", "--abbrev-ref", "HEAD")
		if err != nil {
			return 2, err
		}
		if branch != "main" {
			return 2, fmt.Errorf("estás en %q — a producción solo se deploya desde main", branch)
		}
		head, err := d.gitOut(ctx, p.Source, "rev-parse", "HEAD")
		if err != nil {
			return 2, err
		}
		remote, err := d.gitOut(ctx, p.Source, "rev-parse", "origin/main")
		if err != nil {
			return 2, err
		}
		if head != remote {
			return 2, fmt.Errorf("HEAD != origin/main — pushea (y pasa review) antes de deployar")
		}
		sha, err = d.gitOut(ctx, p.Source, "rev-parse", "--short", "HEAD")
		if err != nil {
			return 2, err
		}
	}

	releaseDir := path.Join("/srv/deploy", project, sha)

	// ── PREPARAR (aditivo; se salta si el dir ya existe = rollback) ──
	exists := d.remoteDirExists(ctx, p.ProdTarget, releaseDir)
	switch {
	case exists:
		d.printf("release %s ya preparada en %s (rollback/re-conmutación)", sha, p.ProdTarget)
	case d.DryRun:
		d.printf("[dry-run] prepararía %s → %s:%s (git archive + push + untar)", sha, p.ProdTarget, releaseDir)
	default:
		if err := d.prepare(ctx, project, p, sha, releaseDir); err != nil {
			return 2, err
		}
	}

	// ── CONFIRMAR (siempre; el nombre del target, tecleado) ─────────
	if d.DryRun {
		d.printf("[dry-run] pediría confirmación tecleando %q y ejecutaría dentro: %s (DEVRUN_RELEASE_DIR=%s)",
			p.ProdTarget, p.DeployCmd, releaseDir)
		return 0, nil
	}
	if d.IsTTY == nil || !d.IsTTY() {
		return 2, fmt.Errorf("deploy requiere terminal interactiva — un agente no deploya a producción desatendido")
	}
	d.printf("── DEPLOY A PRODUCCIÓN ──")
	d.printf("  proyecto : %s", project)
	d.printf("  release  : %s", sha)
	d.printf("  target   : %s", p.ProdTarget)
	d.printf("  conmuta  : %s", p.DeployCmd)
	d.printf("Para continuar, teclea el nombre del target (%s):", p.ProdTarget)
	scanner := bufio.NewScanner(d.In)
	if !scanner.Scan() || strings.TrimSpace(scanner.Text()) != p.ProdTarget {
		return 2, fmt.Errorf("confirmación incorrecta — deploy abortado, nada ha cambiado en el runtime")
	}

	// ── CONMUTAR (el script del proyecto, dentro del target) ────────
	code := d.Stream("lxc", "exec", p.ProdTarget,
		"--env", "DEVRUN_RELEASE_DIR="+releaseDir,
		"--", "sh", "-c", p.DeployCmd)
	if code == 0 {
		d.printf("deploy OK — %s@%s conmutado. Registra en workflow-<área>/CHANGELOG.md.", project, sha)
	} else {
		d.printf("deploy_cmd salió con %d — revisa el target; la release queda en %s para reintentar", code, releaseDir)
	}
	return code, nil
}

func (d *Deps) remoteDirExists(ctx context.Context, target, dir string) bool {
	res := d.R(ctx, "lxc", "exec", target, "--", "test", "-d", dir)
	return res.Err == nil && res.ExitCode == 0
}

// prepare stages the release: tarball from HEAD on the host, pushed
// and unpacked into the versioned dir. Nothing running changes.
func (d *Deps) prepare(ctx context.Context, project string, p config.Project, sha, releaseDir string) error {
	tmpdir := d.TmpDir
	if tmpdir == "" {
		tmpdir = os.TempDir()
	}
	tarball := path.Join(tmpdir, fmt.Sprintf("devrun-%s-%s.tar.gz", project, sha))
	defer os.Remove(tarball)

	d.printf("preparando release %s → %s:%s", sha, p.ProdTarget, releaseDir)
	if _, err := d.gitOut(ctx, p.Source, "archive", "--format=tar.gz", "-o", tarball, "HEAD"); err != nil {
		return err
	}
	if res := d.R(ctx, "lxc", "exec", p.ProdTarget, "--", "mkdir", "-p", releaseDir); res.Err != nil || res.ExitCode != 0 {
		return fmt.Errorf("mkdir %s en %s falló (err=%v exit=%d)", releaseDir, p.ProdTarget, res.Err, res.ExitCode)
	}
	remoteTar := releaseDir + ".tar.gz"
	if res := d.R(ctx, "lxc", "file", "push", tarball, p.ProdTarget+remoteTar); res.Err != nil || res.ExitCode != 0 {
		return fmt.Errorf("lxc file push a %s falló (err=%v exit=%d)", p.ProdTarget, res.Err, res.ExitCode)
	}
	if res := d.R(ctx, "lxc", "exec", p.ProdTarget, "--", "sh", "-c",
		fmt.Sprintf("tar -xzf %s -C %s && rm %s", remoteTar, releaseDir, remoteTar)); res.Err != nil || res.ExitCode != 0 {
		return fmt.Errorf("extracción en %s falló (err=%v exit=%d)", p.ProdTarget, res.Err, res.ExitCode)
	}
	return nil
}
