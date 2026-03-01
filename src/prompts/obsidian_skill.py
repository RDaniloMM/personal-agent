"""Obsidian formatting skill — injected into LLM system prompts.

Provides detailed instructions so the LLM generates well-structured
Markdown documents fully compatible with Obsidian.
"""

OBSIDIAN_FORMATTING_SKILL = """
## SKILL: Formato Obsidian Markdown

Aplica SIEMPRE las siguientes reglas al generar contenido Markdown:

### 1. Frontmatter YAML
Cada nota inicia con un bloque YAML delimitado por `---`:
```yaml
---
title: Título de la nota
date: 2025-01-15
tags: [#paper, #ia, #agentes]
---
```

### 2. Estructura de Encabezados
- `#`  → Título principal (uno solo por nota)
- `##` → Secciones principales
- `###` → Subsecciones
- NO saltes niveles de encabezado

### 3. Wiki-Links (obligatorio)
Enlaza conceptos, autores, frameworks y metodologías usando wiki-links:
- `[[Concepto]]` – enlace directo
- `[[Nota original|texto visible]]` – con alias
- Ejemplos: [[Transformer]], [[RAG]], [[LangGraph]], [[Multi-Agent Systems|Sistemas Multi-Agente]]

### 4. Callouts de Obsidian
Usa callouts para resaltar información clave:
```markdown
> [!abstract] Resumen
> Texto del resumen aquí.

> [!tip] Punto clave
> Hallazgo importante.

> [!note] Nota
> Contexto adicional.

> [!warning] Limitación
> Advertencia o limitación del estudio.

> [!question] Pregunta abierta
> Pregunta para investigar.

> [!example] Ejemplo
> Caso de uso o ejemplo concreto.
```

### 5. Listas y Bullet Points
- Usa `-` para listas no ordenadas
- Usa `1.` para listas ordenadas
- Indenta con 2 o 4 espacios para sub-items
- Cada punto debe ser conciso pero informativo

### 6. Formato de Texto
- **Negrita** para términos clave y conceptos importantes
- *Cursiva* para énfasis o nombres de modelos/papers
- ==Resaltado== para hallazgos críticos o conclusiones principales
- `código inline` para nombres de modelos, funciones, métricas, hiperparámetros

### 7. Tags
- Usa tags descriptivos: `#paper`, `#idea`, `#metodología`, `#framework`, `#benchmark`
- Usa tags jerárquicos: `#ia/agentes`, `#ia/evaluación`, `#ia/rag`
- Coloca tags tanto en el frontmatter como inline donde sea relevante

### 8. Tablas Comparativas
Usa tablas cuando compares modelos, métricas o enfoques:
```markdown
| Modelo | Precisión | Latencia |
|--------|-----------|----------|
| GPT-4  | 92.3%     | 1.2s     |
```

### 9. Bloques de Código
Usa triple backtick con lenguaje para código:
```python
resultado = modelo.predict(datos)
```

### 10. Matemáticas (LaTeX)
- Inline: `$\\alpha + \\beta$`
- Bloque: `$$\\sum_{i=1}^{n} x_i$$`

### 11. Separadores
- Usa `---` para separar secciones temáticas mayores

### REGLAS GENERALES
- TODO el contenido en **español**, excepto términos técnicos sin traducción estándar
- Sé conciso pero informativo — prioriza calidad sobre cantidad
- Incluye al menos 3-5 wiki-links por nota para maximizar conexiones en el grafo de Obsidian
- Usa al menos 1-2 callouts por nota para resaltar lo más importante
- Estructura la información de mayor a menor importancia
"""
