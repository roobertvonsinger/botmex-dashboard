# Template: documentación de bitácora para repos

> Estructura clonable para aplicar la metodología "bitácora viva" a cualquier repo.
> Basado en botmex-dashboard (primera implementación).

## Cómo usar

1. **Copiar la estructura completa** a la raíz del nuevo repo:
   ```bash
   cp -r repos/botmex-dashboard/templates/repo-docs-template/* /ruta/al/nuevo-repo/
   ```
2. **Renombrar la skill local**:
   ```bash
   mv /ruta/al/nuevo-repo/.claude/skills/repo-bitacora \
      /ruta/al/nuevo-repo/.claude/skills/<nombre-del-repo>-bitacora
   ```
3. **Reemplazar placeholders** en los .md plantilla:
   - `{{REPO_NAME}}` → nombre del repo
   - `{{REPO_DESCRIPTION}}` → 1 línea de descripción
   - `{{DEPLOY_HOST}}` → host de prod (e.g. `100.77.154.31` para KVM4)
   - `{{DEPLOY_PATH}}` → carpeta en deploy (e.g. `/docker/<repo>/`)
   - `{{DOMAIN}}` → dominio público (si aplica)
4. **Llenar inventario inicial**: ejecutar grep para endpoints/funciones y poblar `docs/ENDPOINTS.md`, `docs/FRONTEND.md`, etc.

## Estructura provista

```
.
├── README.md                                # entrada visible
├── docs/
│   ├── README.md                            # índice de docs
│   ├── PLAN.md                              # plan del trabajo doc
│   ├── ARCHITECTURE.md                      # stack, capas, diagramas
│   ├── ENDPOINTS.md                         # tabla maestra
│   ├── FRONTEND.md                          # secciones UI (si aplica)
│   ├── SSE_EVENTS.md                        # eventos broadcast (si aplica)
│   ├── ERRORS.md                            # errores comunes + fixes
│   ├── AUDIT.md                             # spec vs actual
│   ├── diagrams/                            # Mermaid .mmd
│   │   └── README.md
│   ├── obsidian/                            # mapa mental
│   │   ├── README.md
│   │   ├── MOC.md
│   │   ├── {{REPO_NAME}}.canvas
│   │   └── bitacora-principles.md
│   └── protocols/
│       ├── deploy-protocol.md
│       ├── deploy-checklist.md
│       ├── maintenance.md
│       └── support.md
└── .claude/skills/repo-bitacora/SKILL.md    # skill auto-update
```

## Principio operativo (heredar siempre)

El repo NO existe para verse bonito. Existe para **trackear + controlar + monitorear + guardar datos**.

Test mental: ¿podés reconstruir lo que pasó dentro de 1 semana desde lo que el repo persiste/expone? Si NO → no está completo.
