# dev-run — el puente host↔instancias del flujo de desarrollo

> Editas en el host; `dev-run` ejecuta en el destino correcto. **Sin daemon**: binario Go
> estático que solo vive mientras corre un comando (0 MB residentes).
> Spec/decisiones: `~/laia-developers/workflow-main/plans/2026-06-03-dev-run-spec-minimax.md`.
> Doctrina (la matriz de pruebas): `~/laia-developers/AGENTS.md` §6.3.

## Los dos modos (y por qué son distintos)

| Modo | Mecanismo | Para qué |
|---|---|---|
| **dev** (`test`/`build`/`exec`/`shell`/`mount`) | **Bind-mount EN VIVO** del dir del host dentro de la instancia (`shift=true` solo en containers; en VMs virtiofs no lo necesita) | El bucle interno: editas en el host y el código ya está dentro. Solo en la **jaula** `dev_instances` |
| **deploy** | **Preparar/conmutar**: `git archive HEAD` → `/srv/deploy/<proy>/<sha>/` en el target + `deploy_cmd` del proyecto | Producción. JAMÁS mounts en vivo en prod (heredaría cada tecleo). Confirmación TTY obligatoria |

## Uso

```bash
dev-run <proyecto> test            # arranca el target si hace falta, monta, corre test_cmd
dev-run <proyecto> build           # ídem con build_cmd
dev-run <proyecto> exec -- go vet ./...
dev-run <proyecto> shell           # bash interactivo dentro (cwd = mount)
dev-run <proyecto> mount|umount|stop
dev-run <proyecto> deploy          # prod: precondiciones git + confirmación tecleada
dev-run <proyecto> deploy --sha <S>  # rollback/re-conmutar una release ya preparada
dev-run status                     # tabla proyecto→target→estado→montado
dev-run --dry-run …                # imprime sin mutar NADA (tampoco en deploy)
```

**Exit codes**: el del comando interno (scripts/agentes dependen de esto) · `2` = error de
uso/config/jaula, o `status` con un target inexistente.

## El registry — `~/laia-developers/dev-targets.yaml`

La config ES la autorización: sin entrada en el yaml, dev-run no toca nada. Ver
`dev-targets.example.yaml`. Reglas que valida: `source` absoluto y existente,
`dev_target ∈ dev_instances`, `prod_target ∉ dev_instances`, `deploy_cmd` obligatorio si hay
`prod_target`.

## Guardarraíles integrados

- **La jaula (`dev_instances`) es inviolable** desde cualquier subcomando de dev — da igual lo
  que diga el bloque de un proyecto. El rechazo apunta a `deploy`.
- **`deploy` nunca conmuta sin confirmación interactiva** (teclear el nombre del target; sin
  TTY → rechazo): un agente no deploya a producción desatendido.
- A producción **solo va lo commiteado, pusheado y en `main`** (precondiciones git).
- Las releases en `/srv/deploy/<proy>/` **no se borran** — rollback = `deploy --sha` anterior.
- `--dry-run` no ejecuta nada mutador, en ningún modo.

## Sutilezas operativas

- `laia-test` vive **parado** (bajo demanda): el primer `dev-run` lo arranca y espera al
  agente; `dev-run <proy> stop` lo devuelve a dormir.
- Los mounts virtiofs hacia la **VM** son efectivamente de solo-escritura-host (la VM no puede
  escribir en el dir del host) — los artefactos de build dentro de la instancia van a `$HOME`
  o `/tmp` de la instancia (GOCACHE ya hace esto solo).
- `deploy_cmd` corre dentro del prod target con `DEVRUN_RELEASE_DIR` apuntando a la release
  preparada: el script del proyecto decide cómo conmutar (symlink, restart…). dev-run no sabe
  de Odoo.

## Build y tests

```bash
cd infra/devrun
go test ./...                                  # todo con fakes, sin host
CGO_ENABLED=0 go build -o bin/dev-run ./cmd/dev-run
```
