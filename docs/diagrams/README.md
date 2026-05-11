# Mermaid diagrams

Diagramas de flujos críticos. Cada `.mmd` se renderiza en GitHub/Forgejo automáticamente y se puede previsualizar en VS Code + extension Mermaid.

| Archivo | Flujo |
|---|---|
| [`deposit-single.mmd`](deposit-single.mmd) | Depósito single (1 cuenta, 1 tarjeta) |
| [`deposit-multi-matchmaker.mmd`](deposit-multi-matchmaker.mmd) | Matchmaker (N cuentas × M tarjetas SSE) |
| [`deposit-scheduled.mmd`](deposit-scheduled.mmd) | Programado (N reps cada 1min, aborta-on-fail) |
| [`sse-bus.mmd`](sse-bus.mmd) | Bus SSE backend → frontend |
| [`infra.mmd`](infra.mmd) | Infraestructura KVM4 + Traefik + servicios externos |

## Cómo agregar uno

1. Crear `nombre.mmd` aquí
2. Usar sintaxis Mermaid (sequenceDiagram, graph, flowchart, etc.)
3. Agregar entry a esta tabla
4. Commit junto con el cambio de código que motivó el diagrama

## Cómo renderizar local

- **VS Code**: extension "Markdown Preview Mermaid Support" + abrir el `.mmd` o un `.md` que lo incluya con triple-backtick mermaid
- **CLI**: `npx -p @mermaid-js/mermaid-cli mmdc -i deposit-single.mmd -o deposit-single.png`
- **Mermaid Live**: pegar contenido en [mermaid.live](https://mermaid.live)
