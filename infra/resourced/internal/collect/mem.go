package collect

import (
	"bufio"
	"fmt"
	"os"
	"strconv"
	"strings"
)

// MemAvailableMB parses /proc/meminfo and returns MemAvailable in MB
// (kB / 1024, floored). The path is an argument so tests can pass a
// fixture file without touching the real /proc.
//
// Why MemAvailable and not MemFree? MemAvailable is the kernel's
// estimate of memory available for new allocations without swapping —
// it accounts for reclaimable cache. MemFree alone is misleading on
// modern kernels (it can be small while MemAvailable is large because
// most "free" memory is actually reclaimable cache). The kernel has
// exposed MemAvailable since 3.14; doyouwin-server runs 7.x.
//
// Format expected (whitespace-tolerant):
//
//	MemTotal:       32849568 kB
//	MemFree:         1234567 kB
//	MemAvailable:   21504000 kB
//	...
//
// We only require MemAvailable. Other lines are ignored. A missing
// MemAvailable line is an error (the kernel is too old or /proc is
// unreadable). Garbage values (non-numeric) are an error.
func MemAvailableMB(meminfoPath string) (int64, error) {
	f, err := os.Open(meminfoPath)
	if err != nil {
		return 0, fmt.Errorf("open %s: %w", meminfoPath, err)
	}
	defer f.Close()

	sc := bufio.NewScanner(f)
	for sc.Scan() {
		line := sc.Text()
		// "MemAvailable:   21504000 kB" → key, value
		idx := strings.IndexByte(line, ':')
		if idx < 0 {
			continue
		}
		key := strings.TrimSpace(line[:idx])
		if key != "MemAvailable" {
			continue
		}
		valStr := strings.TrimSpace(line[idx+1:])
		// Strip the "kB" suffix (case-insensitive, may have leading
		// whitespace).
		fields := strings.Fields(valStr)
		if len(fields) == 0 {
			return 0, fmt.Errorf("meminfo: empty MemAvailable value")
		}
		kb, err := strconv.ParseInt(fields[0], 10, 64)
		if err != nil {
			return 0, fmt.Errorf("meminfo: bad MemAvailable %q: %w", fields[0], err)
		}
		// kB → MB: floor division (operator -aligned; spec says
		// "redondeo a la baja").
		return kb / 1024, nil
	}
	if err := sc.Err(); err != nil {
		return 0, fmt.Errorf("scan %s: %w", meminfoPath, err)
	}
	return 0, fmt.Errorf("meminfo: MemAvailable not found in %s", meminfoPath)
}
