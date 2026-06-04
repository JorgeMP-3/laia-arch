package alert

import (
	"os"
	"path/filepath"
	"testing"
)

func TestParseEnvTabla(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, ".env")
	src := `# comentario inicial
KEY1=value1
KEY2="value with spaces"
KEY3='single quoted'
export KEY4=exported
KEY5="trailing quote"  # comentario inline
KEY6="nested 'inner' quotes"
EMPTY=
  =no_key
no_eq_line
`
	if err := writeFile(path, src); err != nil {
		t.Fatal(err)
	}
	got, err := ParseEnv(path)
	if err != nil {
		t.Fatalf("ParseEnv: %v", err)
	}
	want := map[string]string{
		"KEY1":  "value1",
		"KEY2":  "value with spaces",
		"KEY3":  "single quoted",
		"KEY4":  "exported",
		"KEY5":  "trailing quote",
		"KEY6":  "nested 'inner' quotes",
		"EMPTY": "",
	}
	if len(got) != len(want) {
		t.Errorf("count: got %d want %d (%+v)", len(got), len(want), got)
	}
	for k, v := range want {
		if got[k] != v {
			t.Errorf("KEY %q: got %q want %q", k, got[k], v)
		}
	}
	if _, ok := got["no_key"]; ok {
		t.Error("no_key should be ignored (empty key)")
	}
}

func TestParseEnvArchivoAusente(t *testing.T) {
	if _, err := ParseEnv("/no/existe/este/path/.env"); err == nil {
		t.Fatalf("esperaba error; devolvió nil")
	}
}

func writeFile(path, content string) error {
	return os.WriteFile(path, []byte(content), 0o600)
}
