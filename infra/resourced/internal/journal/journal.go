// Package journal — append-only JSONL writer for events and decisions.
//
// Two files in the state dir use this:
//   - events.jsonl    (alert events, S2)
//   - decisions.jsonl (idle shadow decisions, S5)
//
// Append is a single Open+Write+Close: de-facto atomic for short lines
// (< 4 KB) on a regular file with O_APPEND. The kernel guarantees that
// small writes to a file are not interleaved with other writers as long
// as the buffer stays below PIPE_BUF (4 KB on Linux). We add a trailing
// \n so each call produces a complete JSON line.
package journal

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
)

// Append serializes v as ONE JSON line and appends it to path. The
// parent directory is created if needed (consistent with state.WriteJSON).
// The file is created with mode 0644 if it does not exist.
//
// Errors are wrapped with the operation context to make log lines
// useful when the disk fills up or permissions break.
func Append(path string, v any) error {
	if dir := filepath.Dir(path); dir != "" {
		if err := os.MkdirAll(dir, 0o755); err != nil {
			return fmt.Errorf("mkdir %s: %w", dir, err)
		}
	}
	data, err := json.Marshal(v)
	if err != nil {
		return fmt.Errorf("marshal: %w", err)
	}
	data = append(data, '\n')

	f, err := os.OpenFile(path, os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0o644)
	if err != nil {
		return fmt.Errorf("open %s: %w", path, err)
	}
	defer f.Close()
	if _, err := f.Write(data); err != nil {
		return fmt.Errorf("write: %w", err)
	}
	return nil
}
