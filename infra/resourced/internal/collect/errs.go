package collect

import (
	"context"
	"errors"
)

// shortRunnerErr keeps Runner errors useful for diagnosis while staying
// one line. Deploy lesson (2026-06-03): the previous version collapsed
// everything to "runner failed", which hid that snap-confine was being
// blocked by the systemd sandbox — the operator-facing Detail must say
// WHY a collector could not measure. Runner commands (lxc, systemctl,
// nvidia-smi) carry no secrets in their error messages, so passing the
// message through is safe; we only classify timeouts and cap length.
func shortRunnerErr(err error) error {
	if err == nil {
		return nil
	}
	if errors.Is(err, context.DeadlineExceeded) {
		return errors.New("timeout")
	}
	msg := err.Error()
	if len(msg) > 120 {
		msg = msg[:120] + "…"
	}
	return errors.New(msg)
}
