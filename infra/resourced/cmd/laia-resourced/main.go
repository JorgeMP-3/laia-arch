// laia-resourced — daemon árbitro de recursos e invariantes del host LAIA.
//
// v1 (slice S0): solo escribe un heartbeat de estado cada tick. NO muta nada.
// La autonomía (modo enforce) llega tras el periodo de prueba en sombra; ver
// workflow-server/plans/2026-06-02-laia-resourced-v1-implementacion.md.
//
// Corre como `laia-arch` (grupo lxd → lxc sin sudo). Cero root en v1.
package main

import (
	"context"
	"flag"
	"log"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/JorgeMP-3/laia-arch/infra/resourced/internal/build"
	"github.com/JorgeMP-3/laia-arch/infra/resourced/internal/state"
)

func main() {
	var (
		stateDir = flag.String("state-dir", state.DefaultDir, "directorio de estado")
		tick     = flag.Duration("tick", 30*time.Second, "intervalo entre snapshots")
		mode     = flag.String("mode", "monitor", "monitor | enforce (v1: solo monitor)")
		once     = flag.Bool("once", false, "ejecuta un solo tick y sale (test/timer)")
	)
	flag.Parse()

	// Guardarraíl v1: el binario RECHAZA enforce. La autonomía se habilita en
	// una versión posterior tras el veredicto del mes — no por accidente de flag.
	if *mode != "monitor" {
		log.Fatalf("modo %q no soportado en v1 (solo 'monitor')", *mode)
	}

	host, _ := os.Hostname()
	started := time.Now().UTC()
	log.Printf("laia-resourced %s arrancando (mode=%s tick=%s state=%s host=%s pid=%d)",
		build.Version, *mode, *tick, *stateDir, host, os.Getpid())

	ctx, stop := signal.NotifyContext(context.Background(), syscall.SIGINT, syscall.SIGTERM)
	defer stop()

	var ticks uint64
	snapshot := func() {
		ticks++
		st := state.Status{
			Schema:    state.SchemaVersion,
			Version:   build.Version,
			Mode:      *mode,
			Host:      host,
			PID:       os.Getpid(),
			StartedAt: started,
			UpdatedAt: time.Now().UTC(),
			Tick:      ticks,
		}
		if err := state.WriteJSON(*stateDir, state.StatusFile, st); err != nil {
			log.Printf("WARN: no pude escribir estado: %v", err)
		}
	}

	snapshot() // primer tick inmediato (estado disponible al instante de arrancar)
	if *once {
		return
	}

	t := time.NewTicker(*tick)
	defer t.Stop()
	for {
		select {
		case <-ctx.Done():
			log.Printf("señal recibida — salida limpia tras %d ticks", ticks)
			return
		case <-t.C:
			snapshot()
		}
	}
}
