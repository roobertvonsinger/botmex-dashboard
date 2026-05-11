# Deploy Checklist (BLOCKING) — {{REPO_NAME}}

## Antes
- [ ] Cambio en repo canónico (NO en monorepo)
- [ ] Si toca schema → migración aditiva
- [ ] Si toca Dockerfile / deps → planificar rebuild

## Durante
- [ ] pscp / git pull en deploy
- [ ] Restart o build correspondiente
- [ ] Logs sin tracebacks

## Después — smoke test funcional
- [ ] Endpoint principal responde
- [ ] Persistencia BD confirmada (si aplica)
- [ ] Flujo end-to-end probado en navegador / cliente
- [ ] HTTPS válido (si aplica)

## Commit + push + docs

- [ ] `git commit` con mensaje descriptivo
- [ ] `git push origin main`
- [ ] `docs/` actualizado (la skill lo enforces)
