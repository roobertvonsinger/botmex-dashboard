# Figma First Protocol — botmex-dashboard

## Regla de Oro
**Todo mocking up y diseño de UI debe pasar primero por Figma.** 

Se terminaron las iteraciones a ciegas tocando HTML/CSS y deployando a KVM4 solo para que Robert vea si quedó bien. El diseño centralizado permite modificar y validar visualmente sin quemar tiempo de desarrollo.

## Flujo de trabajo con Figma (vía MCP `html-to-design`)

1. **Ideación:** Robert solicita un cambio visual o una nueva feature de UI.
2. **Mocking up / Import:** 
   - Si es un componente nuevo, se diseña el esqueleto inicial en Figma.
   - Si es modificar algo existente, uso el MCP `html-to-design` (`import-html`) para inyectar el HTML/CSS actual de producción directo al canvas de Figma de Robert.
3. **Iteración Visual:** Robert (y el Dev Chief aportando) iteran en Figma hasta lograr el diseño premium deseado.
4. **Traducción a Código:** Una vez aprobado el diseño en Figma, recién ahí se baja a `app.js` / `style.css` y se deploya.

## Integración técnica MCP
- Server: `html-to-design` (`https://mcp.to.design`)
- Herramientas activas: `import-html`, `import-url`
- Uso típico: Tomar una sección de `static/index.html` + `static/style.css` inlined y mandarla al canvas para que Robert ajuste tamaños, layouts (ej: las 3 columnas de La Pantalla), colores (ej: tintes de grade).
