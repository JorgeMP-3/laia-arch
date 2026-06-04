package main

import (
	"strings"
	"testing"
)

func TestParseArgsTable(t *testing.T) {
	cases := []struct {
		name    string
		args    []string
		want    cli
		wantErr string
	}{
		{"project action", []string{"odoo", "test"},
			cli{configPath: "~/laia-developers/dev-targets.yaml", project: "odoo", action: "test"}, ""},
		{"flags anywhere", []string{"--dry-run", "odoo", "--config", "/x.yaml", "test"},
			cli{configPath: "/x.yaml", dryRun: true, project: "odoo", action: "test"}, ""},
		{"config equals form", []string{"--config=/y.yaml", "status"},
			cli{configPath: "/y.yaml", action: "status"}, ""},
		{"exec args after dashdash", []string{"odoo", "exec", "--", "go", "test", "./..."},
			cli{configPath: "~/laia-developers/dev-targets.yaml", project: "odoo", action: "exec",
				execArgs: []string{"go", "test", "./..."}}, ""},
		{"deploy with sha", []string{"odoo", "deploy", "--sha", "abc123"},
			cli{configPath: "~/laia-developers/dev-targets.yaml", project: "odoo", action: "deploy",
				sha: "abc123"}, ""},
		{"version", []string{"version"},
			cli{configPath: "~/laia-developers/dev-targets.yaml", action: "version"}, ""},
		{"no args", []string{}, cli{}, "falta el subcomando"},
		{"project without action", []string{"odoo"}, cli{}, "falta la acción"},
		{"unknown flag", []string{"--nope", "odoo", "test"}, cli{}, "flag desconocida"},
		{"too many positionals", []string{"a", "b", "c"}, cli{}, "demasiados"},
		{"config without value", []string{"odoo", "test", "--config"}, cli{}, "requiere un valor"},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			got, err := parseArgs(c.args)
			if c.wantErr != "" {
				if err == nil || !strings.Contains(err.Error(), c.wantErr) {
					t.Fatalf("err: got %v, want contains %q", err, c.wantErr)
				}
				return
			}
			if err != nil {
				t.Fatal(err)
			}
			if got.configPath != c.want.configPath || got.dryRun != c.want.dryRun ||
				got.project != c.want.project || got.action != c.want.action ||
				got.sha != c.want.sha ||
				strings.Join(got.execArgs, " ") != strings.Join(c.want.execArgs, " ") {
				t.Errorf("parse:\n got  %+v\n want %+v", got, c.want)
			}
		})
	}
}
