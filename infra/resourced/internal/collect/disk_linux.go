//go:build linux
// +build linux

package collect

import (
	"fmt"
	"syscall"
)

// DiskFree returns the free percentage and free MB for path. It uses
// the syscall.Statfs_t structure directly — no shelling out, no
// shelling dependency, no parsing. Linux-only (the spec acknowledges
// this: "linux-only OK").
//
// Why Bavail and not Bfree? Bavail is the blocks free for a non-root
// user (what a process can actually write to). Bfree includes blocks
// reserved for root — using it would over-promise free space and
// produce a false green when the disk is "full for non-root".
//
// Why Bsize? It's the fundamental block size for this filesystem.
// Multiplying Bavail * Bsize gives free bytes; we then convert to MB.
//
// Returns an error if statfs fails (path does not exist, permission,
// etc.) — the caller maps that to "unknown" in the per-path light.
func DiskFree(path string) (freePct float64, freeMB int64, err error) {
	var st syscall.Statfs_t
	if serr := syscall.Statfs(path, &st); serr != nil {
		return 0, 0, fmt.Errorf("statfs %s: %w", path, serr)
	}
	if st.Blocks == 0 {
		return 0, 0, fmt.Errorf("statfs %s: zero total blocks", path)
	}
	// 100 * free / total — float for the percent so we can compare
	// against a percent threshold (4.9 < 5 etc.) cleanly.
	pct := float64(st.Bavail) * 100.0 / float64(st.Blocks)
	// free MB: Bavail blocks * Bsize bytes, divided by 1 MiB.
	// We compute in uint64 to avoid overflow on multi-TB volumes.
	freeBytes := st.Bavail * uint64(st.Bsize)
	mb := int64(freeBytes / (1024 * 1024))
	return pct, mb, nil
}
