# LAIA-AGORA — Imagen para contenedores de empleados
#
# Build: docker build -t laia-agora:latest .
# Prerequisito: la imagen laia-arch:latest debe existir en el host.
#
# Diferencias respecto a laia-arch:
#   - HERMES_TOOLSET=agora (toolset restringido, sin command_center ni cronjob)
#   - HERMES_USER_MODE=restricted
#   - Usuario hermes UID fijo 10001 (no remapping dinámico con gosu)
#   - Sin Docker socket (no montado en el compose)
#   - Código fuente Python compilado a .pyc y eliminado (protección del código)

FROM laia-arch:latest

# Toolset restringido por defecto
ENV HERMES_TOOLSET=agora
ENV HERMES_USER_MODE=restricted

# Proteger el código fuente: compilar a .pyc y eliminar .py originales.
# El bytecode es funcional pero no legible como código fuente.
USER root
RUN find /opt/hermes -path /opt/hermes/.venv -prune -o \
        -name "*.py" -not -name "entrypoint*" -print | \
    while read f; do \
        python3 -c "import py_compile; py_compile.compile('$f', doraise=True)" 2>/dev/null && \
        rm -f "$f"; \
    done || true

# Hermes user con UID fijo 10001 (distinto del host para aislamiento)
RUN usermod -u 10001 hermes && groupmod -g 10001 hermes && \
    chown -R hermes:hermes /opt/hermes

USER hermes

# El entrypoint del padre ya hace bootstrap de config.yaml, SOUL.md, etc.
# Solo hereda el CMD/ENTRYPOINT original.
