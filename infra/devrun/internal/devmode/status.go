package devmode

import (
	"context"
	"fmt"
	"sort"
	"strings"
	"text/tabwriter"

	"github.com/JorgeMP-3/laia-arch/infra/devrun/internal/lxc"
)

// Status renders the project table: dev target, its LXD state, and
// whether the live mount is attached. Read-only (list + device list);
// safe on any target, including prod ones (it only LOOKS).
//
// Exit code contract (like laia-res): 0 = all dev targets exist;
// 2 = some project points to a missing instance (config drift — the
// registry references a target LXD does not know).
func (d *Deps) Status(ctx context.Context) (string, int) {
	insts, err := lxc.List(ctx, d.R)
	if err != nil {
		return fmt.Sprintf("dev-run: no pude hablar con LXD: %v\n", err), 2
	}

	names := d.Cfg.Names()
	var b strings.Builder
	w := tabwriter.NewWriter(&b, 2, 4, 2, ' ', 0)
	fmt.Fprintln(w, "PROYECTO\tDEV TARGET\tESTADO\tMONTADO\tPROD TARGET")

	exit := 0
	for _, name := range names {
		p := d.Cfg.Projects[name]
		state, mounted := "NO EXISTE", "-"
		if inst, ok := insts[p.DevTarget]; ok {
			state = inst.Status
			mounted = "no"
			if devs, derr := lxc.DeviceList(ctx, d.R, p.DevTarget); derr == nil {
				for _, dev := range devs {
					if dev == DeviceName(name) {
						mounted = "sí"
						break
					}
				}
			} else {
				mounted = "?"
			}
		} else {
			exit = 2
		}
		prod := p.ProdTarget
		if prod == "" {
			prod = "-"
		}
		fmt.Fprintf(w, "%s\t%s\t%s\t%s\t%s\n", name, p.DevTarget, state, mounted, prod)
	}
	w.Flush()

	// stable footer with the cage, so the operator always sees it
	sort.Strings(d.Cfg.DevInstances)
	fmt.Fprintf(&b, "\njaula dev: %s\n", strings.Join(d.Cfg.DevInstances, ", "))
	return b.String(), exit
}
