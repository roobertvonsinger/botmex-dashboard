# Protocolo de Deploy ({{REPO_NAME}})

> Stack actual: {{DEPLOY_HOST}}, carpeta {{DEPLOY_PATH}}.

## Tipos de cambio + flujo

### A) Cambio sin restart (hot-mount)
…

### B) Cambio con restart
…

### C) Cambio con rebuild
…

### D) Cambio en schema BD (migración aditiva)
…

### E) Cambio en `.env`
…

## Estándar de commit + push

```bash
git add <archivos>
git commit -m "<tipo>(<scope>): <mensaje corto>"
git push origin main
```

## Después de cualquier deploy

Ver `deploy-checklist.md`.
