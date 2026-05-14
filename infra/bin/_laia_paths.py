#!/usr/bin/env python3
"""LAIA Path Registry — resolve paths from config.yaml"""
import sys, os, yaml

def resolve(cfg: dict, laia_home: str) -> dict:
    paths = cfg.get('paths', {})
    resolved = {}
    for k, v in paths.items():
        raw = str(v)
        for _ in range(10):
            changed = False
            for pk, pv in paths.items():
                old = raw
                raw = raw.replace('${paths.' + pk + '}', str(pv))
                if raw != old: changed = True
            if not changed: break
        raw = raw.replace('${LAIA_HOME:-/home/laia-hermes/.laia}', laia_home)
        raw = raw.replace('${LAIA_HOME}', laia_home)
        resolved[k] = raw
    return resolved

cmd = sys.argv[1]
config_path = sys.argv[2]

if cmd == 'export':
    env_path = sys.argv[3]
    laia_home = sys.argv[4] if len(sys.argv) > 4 else os.path.expanduser('~/.laia')
else:
    laia_home = sys.argv[3]

with open(config_path) as f:
    cfg = yaml.safe_load(f)
resolved = resolve(cfg, laia_home)

if cmd == 'show':
    for k, v in resolved.items():
        print(f'{k}={v}')
elif cmd == 'get':
    key = sys.argv[4] if len(sys.argv) > 4 else ''
    if key in resolved:
        print(resolved[key])
    else:
        for k, v in resolved.items():
            print(f'{k}={v}')
elif cmd == 'export':
    lines = ['# LAIA Path Registry — auto-generated', f'# Source: {config_path}',
             '# Do not edit. Run: laia-config export-paths', '']
    for k, v in resolved.items():
        upper = k.upper()
        # Remove redundant LAIA_ prefix
        if upper.startswith('LAIA_'):
            upper = upper[5:]
        lines.append(f'export LAIA_{upper}="{v}"')
    with open(env_path, 'w') as f:
        f.write('\n'.join(lines) + '\n')
    print(f'OK: {len(resolved)} paths exported to {env_path}')
