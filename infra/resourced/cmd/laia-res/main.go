// laia-res — cliente CLI de laia-resourced.
//
// Lee el estado de disco; NO necesita que el daemon esté vivo para `status`
// (por eso el daemon publica a /srv/laia/state/resourced/ en cada tick).
package main

import (
	"flag"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"time"

	"github.com/JorgeMP-3/laia-arch/infra/resourced/internal/build"
	"github.com/JorgeMP-3/laia-arch/infra/resourced/internal/state"
)

func main() {
	// Subcomando primero, flags después: el paquete flag deja de parsear al
	// primer posicional, así que `laia-res status --state-dir X` perdería el
	// flag si usáramos el FlagSet global. Extraemos el subcomando y parseamos
	// el resto con su propio FlagSet → funcionan `status --state-dir X`,
	// `--state-dir X` (status implícito) y `status` a secas.
	args := os.Args[1:]
	cmd := "status"
	if len(args) > 0 && !strings.HasPrefix(args[0], "-") {
		cmd, args = args[0], args[1:]
	}

	fs := flag.NewFlagSet(cmd, flag.ExitOnError)
	stateDir := fs.String("state-dir", state.DefaultDir, "directorio de estado")
	if err := fs.Parse(args); err != nil {
		os.Exit(2)
	}

	switch cmd {
	case "status":
		os.Exit(cmdStatus(*stateDir))
	case "version":
		fmt.Printf("laia-res %s\n", build.Version)
	default:
		fmt.Fprintf(os.Stderr, "uso: laia-res [status|version] [--state-dir DIR]\n")
		os.Exit(2)
	}
}

func cmdStatus(dir string) int {
	path := filepath.Join(dir, state.StatusFile)
	var st state.Status
	if err := state.ReadJSON(path, &st); err != nil {
		if os.IsNotExist(err) {
			fmt.Printf("sin estado en %s — ¿está corriendo laia-resourced?\n", path)
			return 1
		}
		fmt.Fprintf(os.Stderr, "no pude leer %s: %v\n", path, err)
		return 1
	}

	age := time.Since(st.UpdatedAt).Round(time.Second)
	freshness := "fresco"
	if age > 2*time.Minute {
		freshness = "STALE (el daemon puede estar caído)"
	}
	fmt.Printf("laia-resourced  %s  modo=%s\n", st.Version, st.Mode)
	fmt.Printf("  host:        %s (pid %d)\n", st.Host, st.PID)
	fmt.Printf("  arrancado:   %s\n", st.StartedAt.Local().Format("2006-01-02 15:04:05"))
	fmt.Printf("  último tick: #%d hace %s — %s\n", st.Tick, age, freshness)
	return 0
}
