package config

import (
	"os"
	"path/filepath"
	"sort"
	"strings"
	"testing"
)

// fakeHome makes a temp dir, sets HOME to it, and returns a cleanup
// func plus the temp dir path. Used by tests that exercise ~/ expansion
// in DefaultPath and Load.
func fakeHome(t *testing.T) (string, func()) {
	t.Helper()
	prev, had := os.LookupEnv("HOME")
	d := t.TempDir()
	t.Setenv("HOME", d)
	return d, func() {
		if had {
			_ = os.Setenv("HOME", prev)
		} else {
			_ = os.Unsetenv("HOME")
		}
	}
}

// validYAML is a minimal config that passes Validate. Tests copy and
// mutate it to exercise one rule at a time.
const validYAML = `dev_instances: [laia-test, laia-dev]
projects:
  doyouwin-odoo:
    source: /tmp
    dev_target: laia-test
    mount_path: /mnt/proyecto
    test_cmd: "echo hi"
    prod_target: laia-finance
    deploy_cmd: "bin/deploy.sh"
`

func TestParse_Valid(t *testing.T) {
	c, err := Parse([]byte(validYAML))
	if err != nil {
		t.Fatalf("valid yaml: %v", err)
	}
	if !c.IsDevInstance("laia-test") {
		t.Errorf("laia-test should be a dev instance")
	}
	if c.IsDevInstance("laia-finance") {
		t.Errorf("laia-finance should NOT be a dev instance")
	}
	p, ok := c.Projects["doyouwin-odoo"]
	if !ok {
		t.Fatalf("project doyouwin-odoo missing")
	}
	if p.ProdTarget != "laia-finance" {
		t.Errorf("prod_target: got %q", p.ProdTarget)
	}
}

func TestValidate_DevInstancesTable(t *testing.T) {
	cases := []struct {
		name   string
		yaml   string
		wantOK bool
		wantIn string // substring expected in the error
	}{
		{"empty_dev_instances", `dev_instances: []` + "\nprojects:\n  a: {source: /tmp, dev_target: x, mount_path: /m}\n", false, "dev_instances must list at least one"},
		{"duplicate_dev_instance", `dev_instances: [a, a]` + "\nprojects:\n  p: {source: /tmp, dev_target: a, mount_path: /m}\n", false, "duplicate"},
		{"empty_dev_instance_entry", `dev_instances: [a, ""]` + "\nprojects:\n  p: {source: /tmp, dev_target: a, mount_path: /m}\n", false, "empty entry"},
		{"no_projects", `dev_instances: [a]` + "\nprojects: {}\n", false, "projects must list at least one"},
		{"duplicate_project", `dev_instances: [a]` + "\nprojects:\n  p: {source: /tmp, dev_target: a, mount_path: /m}\n  p: {source: /tmp, dev_target: a, mount_path: /m}\n", false, "already defined"},
		{"empty_project_name", `dev_instances: [a]` + "\nprojects:\n  \"\": {source: /tmp, dev_target: a, mount_path: /m}\n", false, "empty name"},
		{"valid_minimal", `dev_instances: [a]` + "\nprojects:\n  p: {source: /tmp, dev_target: a, mount_path: /m}\n", true, ""},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			_, err := Parse([]byte(tc.yaml))
			if tc.wantOK {
				if err != nil {
					t.Errorf("want ok, got %v", err)
				}
				return
			}
			if err == nil {
				t.Fatalf("want error containing %q, got nil", tc.wantIn)
			}
			if !strings.Contains(err.Error(), tc.wantIn) {
				t.Errorf("error %q does not contain %q", err.Error(), tc.wantIn)
			}
		})
	}
}

func TestValidate_ProjectTable(t *testing.T) {
	cases := []struct {
		name   string
		yaml   string
		wantOK bool
		wantIn string
	}{
		{
			name:   "source_not_absolute",
			yaml:   `dev_instances: [a]` + "\nprojects:\n  p: {source: relative, dev_target: a, mount_path: /m}\n",
			wantOK: false,
			wantIn: "source",
		},
		{
			name:   "source_does_not_exist",
			yaml:   `dev_instances: [a]` + "\nprojects:\n  p: {source: /no/such/path/here, dev_target: a, mount_path: /m}\n",
			wantOK: false,
			wantIn: "must be an existing directory",
		},
		{
			name:   "source_is_file_not_dir",
			yaml:   "", // filled in test
			wantOK: false,
			wantIn: "must be an existing directory",
		},
		{
			name:   "dev_target_missing",
			yaml:   `dev_instances: [a]` + "\nprojects:\n  p: {source: /tmp, mount_path: /m}\n",
			wantOK: false,
			wantIn: "dev_target is required",
		},
		{
			name:   "dev_target_not_in_whitelist",
			yaml:   `dev_instances: [a]` + "\nprojects:\n  p: {source: /tmp, dev_target: b, mount_path: /m}\n",
			wantOK: false,
			wantIn: "is not in dev_instances",
		},
		{
			name:   "mount_path_not_absolute",
			yaml:   `dev_instances: [a]` + "\nprojects:\n  p: {source: /tmp, dev_target: a, mount_path: relative}\n",
			wantOK: false,
			wantIn: "mount_path",
		},
		{
			name:   "prod_target_in_dev_instances",
			yaml:   `dev_instances: [a]` + "\nprojects:\n  p: {source: /tmp, dev_target: a, mount_path: /m, prod_target: a, deploy_cmd: x}\n",
			wantOK: false,
			wantIn: "deploy must not share a cage with dev",
		},
		{
			name:   "prod_target_without_deploy_cmd",
			yaml:   `dev_instances: [a]` + "\nprojects:\n  p: {source: /tmp, dev_target: a, mount_path: /m, prod_target: b}\n",
			wantOK: false,
			wantIn: "deploy_cmd is required when prod_target is set",
		},
		{
			name:   "deploy_cmd_without_prod_target",
			yaml:   `dev_instances: [a]` + "\nprojects:\n  p: {source: /tmp, dev_target: a, mount_path: /m, deploy_cmd: x}\n",
			wantOK: false,
			wantIn: "deploy_cmd is set but prod_target is empty",
		},
		{
			name:   "valid_with_prod",
			yaml:   `dev_instances: [a]` + "\nprojects:\n  p: {source: /tmp, dev_target: a, mount_path: /m, prod_target: b, deploy_cmd: x}\n",
			wantOK: true,
		},
		{
			name:   "valid_no_prod",
			yaml:   `dev_instances: [a]` + "\nprojects:\n  p: {source: /tmp, dev_target: a, mount_path: /m}\n",
			wantOK: true,
		},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			yamlIn := tc.yaml
			if tc.name == "source_is_file_not_dir" {
				f := filepath.Join(t.TempDir(), "file")
				if err := os.WriteFile(f, []byte("x"), 0644); err != nil {
					t.Fatal(err)
				}
				yamlIn = "dev_instances: [a]\nprojects:\n  p: {source: " + f + ", dev_target: a, mount_path: /m}\n"
			}
			_, err := Parse([]byte(yamlIn))
			if tc.wantOK {
				if err != nil {
					t.Errorf("want ok, got %v", err)
				}
				return
			}
			if err == nil {
				t.Fatalf("want error containing %q, got nil", tc.wantIn)
			}
			if !strings.Contains(err.Error(), tc.wantIn) {
				t.Errorf("error %q does not contain %q", err.Error(), tc.wantIn)
			}
		})
	}
}

func TestParse_StrictUnknownFields(t *testing.T) {
	bad := `dev_instances: [a]
projects:
  p: {source: /tmp, dev_target: a, mount_path: /m, unknown_field: 1}
`
	_, err := Parse([]byte(bad))
	if err == nil {
		t.Fatalf("expected parse error for unknown field")
	}
	if !strings.Contains(err.Error(), "unknown_field") &&
		!strings.Contains(err.Error(), "not found") {
		t.Errorf("error should mention the unknown field: %v", err)
	}
}

func TestLoad_TildeExpansion(t *testing.T) {
	home, cleanup := fakeHome(t)
	defer cleanup()

	dir := filepath.Join(home, "cfg")
	if err := os.MkdirAll(dir, 0755); err != nil {
		t.Fatal(err)
	}
	path := filepath.Join(dir, "dev-targets.yaml")
	if err := os.WriteFile(path, []byte(validYAML), 0644); err != nil {
		t.Fatal(err)
	}

	loaded, err := Load("~/cfg/dev-targets.yaml")
	if err != nil {
		t.Fatalf("Load: %v", err)
	}
	if _, ok := loaded.Projects["doyouwin-odoo"]; !ok {
		t.Errorf("project not loaded")
	}
}

func TestLoad_NotFound(t *testing.T) {
	_, err := Load("/no/such/path/dev-targets.yaml")
	if err == nil {
		t.Fatalf("want error")
	}
	if !strings.Contains(err.Error(), "read") {
		t.Errorf("error should mention read: %v", err)
	}
}

func TestNames_SortedAndUnique(t *testing.T) {
	c, err := Parse([]byte(validYAML))
	if err != nil {
		t.Fatal(err)
	}
	names := c.Names()
	if !sort.StringsAreSorted(names) {
		t.Errorf("Names() not sorted: %v", names)
	}
	if len(names) != 1 || names[0] != "doyouwin-odoo" {
		t.Errorf("Names: %v", names)
	}
}
