package evaluate

import (
	"testing"
	"time"

	"github.com/JorgeMP-3/laia-arch/infra/resourced/internal/config"
	"github.com/JorgeMP-3/laia-arch/infra/resourced/internal/state"
)

func makeServices() []config.Service {
	return []config.Service{
		{Name: "laia-agora", Class: "critical", Liveness: config.Liveness{Kind: config.LivenessLXC, Container: "laia-agora"}},
		{Name: "tts-server", Class: "critical", Liveness: config.Liveness{Kind: config.LivenessSystemd, Units: []string{"tts-server.service"}}},
		{Name: "cloudflared", Class: "critical", Liveness: config.Liveness{Kind: config.LivenessLXCSystemd, Container: "laia-edge", Units: []string{"cloudflared.service"}}},
		{Name: "laia-dev", Class: "dev", Liveness: config.Liveness{Kind: config.LivenessLXC, Container: "laia-dev"}},
	}
}

func TestProdTodosOk(t *testing.T) {
	in := ProdInput{
		Services: makeServices(),
		States:   map[string]string{"laia-agora": "ok", "tts-server": "ok", "cloudflared": "ok", "laia-dev": "ok"},
	}
	dim, svcs := Prod(in, time.Now())
	if dim.Light != state.LightOK {
		t.Errorf("dim: got %q want ok", dim.Light)
	}
	if dim.Detail != "3/3 critical alive" {
		t.Errorf("detail: got %q", dim.Detail)
	}
	if len(svcs) != 4 {
		t.Errorf("services map: got %d want 4", len(svcs))
	}
	if svcs["laia-dev"].Class != "dev" {
		t.Errorf("dev class missing")
	}
}

func TestProdCriticalDown(t *testing.T) {
	in := ProdInput{
		Services: makeServices(),
		States:   map[string]string{"laia-agora": "down", "tts-server": "ok", "cloudflared": "ok", "laia-dev": "ok"},
	}
	dim, _ := Prod(in, time.Now())
	if dim.Light != state.LightRed {
		t.Errorf("dim: got %q want red", dim.Light)
	}
	if dim.Detail != "down: laia-agora" {
		t.Errorf("detail: got %q", dim.Detail)
	}
}

func TestProdSoloDevDownNoAlarma(t *testing.T) {
	// Dev class is informational: laia-dev down must NOT turn prod red.
	in := ProdInput{
		Services: makeServices(),
		States:   map[string]string{"laia-agora": "ok", "tts-server": "ok", "cloudflared": "ok", "laia-dev": "down"},
	}
	dim, svcs := Prod(in, time.Now())
	if dim.Light != state.LightOK {
		t.Errorf("dim: got %q want ok (dev down must not alarm)", dim.Light)
	}
	if svcs["laia-dev"].Alive != "down" {
		t.Errorf("dev service map: got %q want down (visible in services)", svcs["laia-dev"].Alive)
	}
}

func TestProdCriticalUnknown(t *testing.T) {
	in := ProdInput{
		Services: makeServices(),
		States:   map[string]string{"laia-agora": "ok", "tts-server": "unknown", "cloudflared": "ok", "laia-dev": "ok"},
	}
	dim, _ := Prod(in, time.Now())
	if dim.Light != state.LightUnknown {
		t.Errorf("dim: got %q want unknown", dim.Light)
	}
}

func TestProdCloudflaredContainerParado(t *testing.T) {
	// laia-edge is Stopped → cloudflared is "unknown" (we do not poke
	// stopped containers). The result is unknown, not down, not red.
	in := ProdInput{
		Services: makeServices(),
		States:   map[string]string{"laia-agora": "ok", "tts-server": "ok", "cloudflared": "unknown", "laia-dev": "ok"},
	}
	dim, _ := Prod(in, time.Now())
	if dim.Light != state.LightUnknown {
		t.Errorf("dim: got %q want unknown (container down, not service down)", dim.Light)
	}
}

func TestProdEstadoAusenteEsUnknown(t *testing.T) {
	// The Prod evaluator does NOT know the liveness kind — it just
	// sees the pre-computed states map. A missing state means the
	// caller chose not to (or could not) compute it → unknown. The
	// interpretation "missing lxc container = down" lives in
	// collect.ServiceStates (which has the kind context). This test
	// documents the evaluator's contract.
	in := ProdInput{
		Services: makeServices(),
		States:   map[string]string{"tts-server": "ok", "cloudflared": "ok", "laia-dev": "ok"},
		// laia-agora REMOVED from states
	}
	dim, _ := Prod(in, time.Now())
	if dim.Light != state.LightUnknown {
		t.Errorf("dim: got %q want unknown (caller should pre-mark missing as down or unknown)", dim.Light)
	}
}

func TestProdMultiUnitUnaDown(t *testing.T) {
	// nextcloud has 3 snap units; if any is down, the service is down.
	in := ProdInput{
		Services: []config.Service{
			{Name: "nextcloud", Class: "critical", Liveness: config.Liveness{
				Kind:  config.LivenessSystemd,
				Units: []string{"snap.nextcloud.apache.service", "snap.nextcloud.mysql.service", "snap.nextcloud.php-fpm.service"},
			}},
		},
		// Caller pre-combined: 1 of 3 down → "down"
		States: map[string]string{"nextcloud": "down"},
	}
	dim, _ := Prod(in, time.Now())
	if dim.Light != state.LightRed {
		t.Errorf("dim: got %q want red (1 of 3 units down)", dim.Light)
	}
}
