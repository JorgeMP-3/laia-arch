# LAIA — Release Interno

Antes de promover una versión:

```bash
bash tests/installer/run_all.sh
git status --short
git tag vX.Y.Z
sudo -E laia-release --version vX.Y.Z --allow-dirty /home/laia-hermes/LAIA
```

Reglas:

- No publicar una release si `tests/installer/run_all.sh` falla.
- No meter datos operacionales ni `archived/` en `/opt/laia`; el instalador los excluye.
- `laia-install --minimal` debe seguir siendo estable porque lo usa `laia-clone`.
- Containers nunca se clonan por tarball entre máquinas; se reconstruyen localmente.
