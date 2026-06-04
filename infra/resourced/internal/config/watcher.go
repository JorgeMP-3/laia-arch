package config

import (
	"fmt"
	"os"
)

// Watcher reloads config on mtime change (hot-reload) with a single
// invariant: if the new one fails, the PREVIOUS one is preserved. The
// operator can push a broken YAML without killing the daemon — the
// next valid reload picks it up. The error is returned to the caller
// (main emits it as a config/warn event, S2).
type Watcher struct {
	path  string
	mtime int64 // modtime of the path on disk; 0 = never seen
	cur   *Config
}

// NewWatcher prepares a Watcher. If the path exists and is valid, it
// is loaded. If it does not exist, defaults are loaded (consistent
// with Load). If it exists but is invalid, the error is returned:
// starting with an invalid config is worse than starting with
// defaults, and the operator deserves to know at boot.
func NewWatcher(path string) (*Watcher, error) {
	w := &Watcher{path: path}
	cfg, err := Load(path)
	if err != nil {
		if !isNotExist(err) {
			return nil, err
		}
		// No file: defaults. cur=mtime=0; Reload will detect a
		// future appearance.
		def, derr := Defaults()
		if derr != nil {
			return nil, derr
		}
		w.cur = def
		return w, nil
	}
	w.cur = cfg
	if info, ierr := os.Stat(path); ierr == nil {
		w.mtime = info.ModTime().UnixNano()
	}
	return w, nil
}

// Current returns the active config. Always non-nil (post-NewWatcher
// or post-first successful Reload).
func (w *Watcher) Current() *Config { return w.cur }

// Reload reloads the config from the path if the mtime changed since
// the last read. Returns an error if the new one fails (preserving
// w.cur). Idempotent: calling Reload with no mtime change is a no-op.
func (w *Watcher) Reload() error {
	info, err := os.Stat(w.path)
	if err != nil {
		if isNotExist(err) {
			// No file, nothing to reload. cur is kept.
			return nil
		}
		return fmt.Errorf("stat %s: %w", w.path, err)
	}
	mt := info.ModTime().UnixNano()
	if w.cur != nil && mt == w.mtime {
		return nil // no change
	}
	cfg, err := Load(w.path)
	if err != nil {
		// Preserves w.cur. Caller will notify the operator.
		return err
	}
	w.cur = cfg
	w.mtime = mt
	return nil
}

// isNotExist avoids importing os in the happy path (readability).
func isNotExist(err error) bool { return os.IsNotExist(err) }
