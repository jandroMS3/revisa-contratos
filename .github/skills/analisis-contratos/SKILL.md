---
name: analisis-contratos
description: 'Metodología y checklists para analizar contratos desde la posición de la parte que los recibe: resumen, puntos clave, riesgos con severidad y mejoras negociables. Use when: revisar contrato, analizar cláusulas, detectar cláusulas abusivas o desequilibradas, evaluar riesgos contractuales, proponer contrapropuestas, negociar contrato, arrendamiento, laboral, freelance, servicios, SaaS, NDA, compraventa, préstamo.'
---

# Análisis de contratos

Todo el análisis se hace desde la perspectiva de **la parte que recibe el contrato para firmarlo** (el usuario), salvo que indique lo contrario. Hay que identificar primero qué rol ocupa en el contrato (arrendatario, trabajador, cliente, proveedor, licenciatario...).

## Reglas de rigor

1. **Fidelidad al texto**: cada riesgo o punto clave debe apoyarse en una cláusula concreta y una cita literal breve (máx. ~300 caracteres). No citar de memoria ni parafrasear dentro de `cita`.
2. **Nada inventado**: si algo no aparece en el contrato, no se afirma. Las ausencias se reportan como "cláusula ausente", no como si existieran.
3. **Ubicación**: indicar cláusula/artículo y, si se puede, página (marcadores `=== Página N ===`).
4. **Incertidumbre explícita**: texto ambiguo, ilegible o dependiente de un anexo no incluido va a `advertencias` o `preguntas_abiertas`.
5. **Jurisdicción**: deducirla de la ley aplicable/foro del contrato. Si no consta, decirlo. No afirmar que una cláusula es "nula" o "ilegal" con certeza; usar "podría ser abusiva / de dudosa validez según la normativa de <jurisdicción>; conviene verificarlo con un abogado".
6. **Utilidad**: priorizar lo que afecta al dinero, a la duración/salida, a la responsabilidad y a los derechos del usuario por encima de cuestiones formales menores.
7. **Solo el contrato como fuente de hechos**: no incorporar datos de la conversación, del encargo o de otros documentos (p. ej. "se nos indicó que..."). Lo que no se pueda comprobar en el texto va a `advertencias` o `preguntas_abiertas`. Excepción acotada: lo leído de **imágenes del propio PDF** (anexos, planos, justificantes) se admite con `origen: "anexo-visual"` en `datos_clave`, `fechas_plazos` o, si es la única base de un riesgo (p. ej. una discrepancia entre el cuerpo y un anexo), en `riesgos`; es informativo y no verificable, y el informe lo marca como tal. Cuando la discrepancia se puede anclar en una cláusula del cuerpo, el riesgo cita esa cláusula y menciona el anexo en la descripción como «leído de imagen».
8. **Referencias legales ancladas**: citar normas solo de [normativa-es.md](./references/normativa-es.md) o las que mencione el contrato; en otro caso, "verificar con abogado". Una referencia legal no sustituye a la cita literal del contrato.
9. **Anexos no analizables** (imágenes, planos, páginas sin texto) son una limitación del análisis y van a `advertencias`; no se reportan como riesgo por sí mismos. Si se han podido leer visualmente, aplica la excepción de la regla 7.
10. **Fuera de España**: la normativa de [normativa-es.md](./references/normativa-es.md) solo aplica a contratos sujetos a derecho español. Para otra jurisdicción no cites normas: anota en `advertencias` que no hay normativa de referencia y recomienda un abogado local. El idioma de las citas es el del contrato.

## Calibración y tamaño del análisis

- **Agrupar por tema y fusionar solapamientos**: si varias cláusulas producen el mismo problema (p. ej. aval, cuenta especial y cuotas), es **un** riesgo que cita la cláusula principal, enumera las demás en `clausula` y puede añadir sus citas en `citas`. Tamaño: 10-15 riesgos en un contrato normal; hasta 20 en contratos largos (más de ~25 páginas) o claramente desequilibrados; más de 20 es ruido (el validador lo avisa).
- **Severidad por criterio, no por cupo**: `critico` solo si cumple literalmente el criterio de la tabla. No hay cupo fijo: un contrato de adhesión muy abusivo puede tener varios críticos. Pero si más de la mitad de los riesgos son `critico`/`alto`, hay que revisar cada uno contra la tabla y justificar en `descripcion` por qué no es `medio`; el crítico lo comprueba. Los problemas formales (errores de redacción, referencias cruzadas) son `bajo` o `medio` y se agrupan en uno.
- **Concisión**: `descripcion` <= ~600 caracteres, `impacto` <= ~300, con cifras concretas. Sin repetir la cita.
- **Cita útil**: literal, 40-300 caracteres, que contenga la obligación o restricción (no solo un encabezado ni una frase cortada).

## Escala de severidad de riesgos

| Nivel | Criterio |
|-------|----------|
| `critico` | Puede causar pérdida económica grave, responsabilidad ilimitada, pérdida de derechos esenciales o imposibilidad de salir. No firmar sin cambiarlo. |
| `alto` | Desequilibrio importante o coste relevante probable. Debería negociarse. |
| `medio` | Desventaja real pero acotada o poco probable. Conviene mejorar. |
| `bajo` | Molestia menor o riesgo remoto. Informativo. |

Veredicto global: el nivel más alto presente, matizado por cuántos riesgos graves haya y por su probabilidad.

## Procedimiento

1. **Identificación**: tipo de contrato, partes y roles, objeto, fecha, ley y foro, idioma, anexos mencionados.
2. **Resumen y puntos clave**: qué se acuerda, precio/contraprestación, duración, renovación, terminación, penalizaciones, obligaciones de cada parte, plazos y fechas. Ver [checklist general](./references/checklist-general.md).
3. **Riesgos**: recorrer el checklist general y el del tipo concreto ([tipos de contrato](./references/tipos-contrato.md)). Contrastar cada cláusula contra la posición del usuario: ¿quién asume el riesgo?, ¿es recíproco?, ¿hay topes?, ¿se puede salir? Aplicar la calibración anterior.
4. **Mejoras**: por cada riesgo `medio` o superior (**sin excepción**: el renderizador avisa de los que queden sin mejora) y por cada cláusula ausente relevante, proponer un cambio concreto con redacción sugerida, justificación y dificultad estimada de negociación. Una mejora puede cubrir varios riesgos solapados (`riesgo_relacionado` admite una lista). Ver [patrones de negociación](./references/patrones-mejoras.md).
5. **Preguntas abiertas**: datos que el usuario debería confirmar (anexos, cifras, intenciones) antes de firmar.

## Tono

Claro, directo y sin jerga innecesaria; el usuario no tiene por qué ser abogado. Explicar el impacto práctico ("si pasa X, tendrías que pagar Y"). Idioma del informe: el del usuario (español por defecto), citas en el idioma original.
