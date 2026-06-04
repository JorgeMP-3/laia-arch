package alert

import (
	"bufio"
	"fmt"
	"os"
	"strings"
)

// ParseEnv reads a .env file and returns the key→value map. Format:
// one KEY=VALUE per line. Empty lines and lines starting with # are
// ignored. A leading `export ` (with whitespace) is stripped. Single or
// double quotes around the VALUE are stripped (recursively — e.g.
// '"x"' → x). Missing file returns (nil, error).
//
// Why a hand-rolled parser and not godotenv? Single dep discipline:
// stdlib + yaml.v3 only. The format we need is trivial and forgiving —
// no expansion of $OTHER_VAR, no escape sequences. Adding godotenv
// would be a 2nd dep for ~30 lines of code.
//
// Telegra's secrets file is rotated by the operator. The Telegram
// sender re-reads on every send (not cached at startup) so a rotation
// is picked up on the next alert.
func ParseEnv(path string) (map[string]string, error) {
	f, err := os.Open(path)
	if err != nil {
		return nil, fmt.Errorf("open %s: %w", path, err)
	}
	defer f.Close()

	out := map[string]string{}
	sc := bufio.NewScanner(f)
	for sc.Scan() {
		line := strings.TrimSpace(sc.Text())
		if line == "" || strings.HasPrefix(line, "#") {
			continue
		}
		// Optional `export ` prefix.
		line = strings.TrimPrefix(line, "export ")
		line = strings.TrimSpace(line)
		eq := strings.IndexByte(line, '=')
		if eq < 0 {
			continue // no =, skip silently
		}
		key := strings.TrimSpace(line[:eq])
		val := strings.TrimSpace(line[eq+1:])
		val = unquote(val)
		if key == "" {
			continue
		}
		out[key] = val
	}
	if err := sc.Err(); err != nil {
		return nil, fmt.Errorf("scan %s: %w", path, err)
	}
	return out, nil
}

// unquote finds the closing quote of v (single or double) and returns
// the content between them. This is the common .env convention:
// KEY="value"  # comment → "value" (the trailing comment is dropped).
// Unquoted values are returned as-is, so a literal '#' inside an
// unquoted value is preserved.
//
// Intentionally NOT a full shell-style unquoter: no backslash escapes,
// no variable expansion. The files we care about (Telegram secrets)
// are simple KEY="VALUE" or KEY=plain.
func unquote(v string) string {
	if v == "" {
		return v
	}
	first := v[0]
	if first != '"' && first != '\'' {
		return v
	}
	for i := 1; i < len(v); i++ {
		if v[i] == first {
			return v[1:i]
		}
	}
	// No closing quote: best effort, return as-is.
	return v
}
