package evaluate

import (
	"errors"
	"testing"
	"time"

	"github.com/JorgeMP-3/laia-arch/infra/resourced/internal/state"
)

func TestDiskTabla(t *testing.T) {
	now := time.Unix(0, 0).UTC()
	cases := []struct {
		name    string
		results []DiskResult
		want    state.Light
	}{
		{"empty paths → unknown", nil, state.LightUnknown},
		{"all ok", []DiskResult{
			{Path: "/", FreePct: 50},
			{Path: "/mnt/data", FreePct: 80},
		}, state.LightOK},
		{"one warn", []DiskResult{
			{Path: "/", FreePct: 50},
			{Path: "/mnt/data", FreePct: 8}, // < 10
		}, state.LightWarn},
		{"one red", []DiskResult{
			{Path: "/", FreePct: 4}, // < 5
			{Path: "/mnt/data", FreePct: 80},
		}, state.LightRed},
		{"path errored → unknown", []DiskResult{
			{Path: "/", FreePct: 50},
			{Path: "/broken", Err: errors.New("no such file")},
		}, state.LightUnknown},
		{"mixed: one red, one ok → red (worst wins)", []DiskResult{
			{Path: "/", FreePct: 1},
			{Path: "/mnt/data", FreePct: 90},
		}, state.LightRed},
		{"limits from §S4: 4.9→red, 5.0→warn, 9.9→warn, 10.0→ok", []DiskResult{
			{Path: "/p1", FreePct: 4.9},
		}, state.LightRed},
		{"limits: 5.0→warn", []DiskResult{
			{Path: "/p1", FreePct: 5.0},
		}, state.LightWarn},
		{"limits: 9.9→warn", []DiskResult{
			{Path: "/p1", FreePct: 9.9},
		}, state.LightWarn},
		{"limits: 10.0→ok", []DiskResult{
			{Path: "/p1", FreePct: 10.0},
		}, state.LightOK},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			got := Disk(c.results, 10, 5, now)
			if got.Light != c.want {
				t.Errorf("Light: got %q want %q", got.Light, c.want)
			}
		})
	}
}

// TestDiskDetailFormato: el Detail sigue el patrón del spec
// "/ 81% libre · /mnt/data 95% libre" para todos ok, y "X unknown
// (err)" para paths con error.
func TestDiskDetailFormato(t *testing.T) {
	got := Disk([]DiskResult{
		{Path: "/", FreePct: 81},
		{Path: "/mnt/data", FreePct: 95},
	}, 10, 5, time.Now())
	want := "/ 81% libre · /mnt/data 95% libre"
	if got.Detail != want {
		t.Errorf("Detail: got %q want %q", got.Detail, want)
	}
}
