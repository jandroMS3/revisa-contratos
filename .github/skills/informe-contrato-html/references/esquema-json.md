# Esquema JSON del informe

Cada fragmento es un objeto JSON con claves de primer nivel; el renderizador las fusiona. Textos en español. Los campos marcados (*) son obligatorios en el conjunto final. Los saltos de párrafo en textos largos se escriben como `\n\n`.

## meta.json (orquestador)
```json
{
  "titulo": "Contrato de arrendamiento de vivienda",   // (*)
  "archivo": "alquiler.pdf",
  "fecha_analisis": "2026-01-15",                       // ISO; la escribe el Revisor el día del análisis
  "rol_usuario": "Arrendatario",                        // (*)
  "tipo_contrato": "Arrendamiento de vivienda",
  "jurisdiccion": "España (Derecho común)",
  "advertencias": ["Páginas 7-8 sin texto extraíble: anexo de tarifas no analizado"]
}
```
`fecha_analisis` debe fijarse al analizar (`date +%F`): así regenerar el informe otro día no cambia la fecha. Si falta, el renderizador usa la del día y el validador avisa. Las `advertencias` se muestran justo debajo del veredicto; las páginas sin texto o anexos no analizables van **aquí**, no como riesgo.

## resumen.json (contratos-resumen)
```json
{
  "partes": [{"nombre": "Ana Pérez", "rol": "Arrendadora", "detalle": "DNI 123..."}],
  "resumen": "Texto de 1-3 párrafos: qué se acuerda, condiciones principales y para quién es más favorable.",   // (*)
  "datos_clave": [{"concepto": "Renta mensual", "valor": "950 €", "clausula": "Cláusula 3"}],
  "puntos_clave": [{"titulo": "Duración 5 años", "descripcion": "...", "clausula": "Cláusula 4", "cita": "opcional, literal"}],
  "fechas_plazos": [{"concepto": "Preaviso de no renovación", "fecha_o_plazo": "30 días", "clausula": "Cláusula 4.2"}],
  "obligaciones": {"usuario": ["Pagar la renta antes del día 5"], "contraparte": ["Entregar la vivienda en buen estado"]}
}
```
`cita` es opcional en `datos_clave`, `puntos_clave`, `fechas_plazos` y `clausulas_ausentes`; si se incluye, se verifica contra el texto igual que en los riesgos.

`origen` (opcional, en `datos_clave`, `fechas_plazos` y `riesgos`): `"texto"` (por defecto) o `"anexo-visual"` para datos leídos de páginas en imagen (anexos, planos, justificantes) que no se pueden citar literalmente. No se verifican con cita y el HTML los marca como «Leído de imagen · sin verificar».

## riesgos.json (contratos-riesgos)
```json
{
  "riesgos": [{                                          // (*)
    "id": "R1",                                          // único
    "titulo": "Responsabilidad ilimitada",
    "severidad": "critico",                              // critico | alto | medio | bajo
    "clausula": "Cláusula 9.1 (pág. 4)",
    "cita": "El Cliente responderá de todos los daños...",   // literal, 40-300 caracteres
    "citas": ["...otra cláusula fusionada en este riesgo..."], // opcional: citas adicionales (25-300 car.), cada una verificada
    "origen": "texto",                                   // opcional: texto | anexo-visual (sin cita literal)
    "descripcion": "Qué dice y por qué es un problema para el usuario (<= ~600 caracteres).",
    "impacto": "Consecuencia práctica concreta si ocurre (<= ~300 caracteres).",
    "probabilidad": "Media",                             // opcional
    "recomendacion": "Qué hacer: negociar, aceptar con cautela, etc."
  }],
  "clausulas_ausentes": [{"titulo": "Tope de responsabilidad", "por_que_importa": "..."}]
}
```

## mejoras.json (contratos-mejoras)
```json
{
  "mejoras": [{                                          // (*)
    "titulo": "Limitar la responsabilidad",
    "prioridad": "alta",                                 // alta | media | baja
    "riesgo_relacionado": "R1",                          // id, lista ["R1","R4"] o "R1, R4"
    "clausula_afectada": "Cláusula 9.1",
    "situacion_actual": "Responsabilidad sin límite.",
    "propuesta": "Tope igual a lo abonado en los últimos 12 meses.",
    "redaccion_sugerida": "La responsabilidad total de cada parte no excederá...",
    "justificacion": "Por qué te beneficia.",
    "dificultad_negociacion": "Media"                    // opcional
  }],
  "preguntas_abiertas": ["¿El anexo de tarifas forma parte del contrato?"]
}
```
Una mejora puede cubrir varios riesgos solapados (lista de ids).

## veredicto.json (orquestador)
```json
{
  "veredicto": {                                         // (*)
    "nivel": "alto",                                     // critico | alto | medio | bajo
    "recomendacion": "No firmar sin negociar los riesgos R1 y R3.",
    "texto": "Valoración global en 2-4 frases.",
    "prioridades": ["R1", "R3", "R2"]                    // opcional: orden de negociación (máx. ~5); por defecto, los 5 más graves
  }
}
```
El recuento de riesgos por severidad lo calcula el renderizador; no lo escribas a mano en `texto`.

## Validaciones del renderizador
- **Errores (salida 1, no se genera HTML)**: campos obligatorios ausentes, `severidad`/`prioridad`/`nivel` fuera del enum, ids de riesgo ausentes o duplicados, `riesgo_relacionado` o `prioridades` que apuntan a ids inexistentes.
- **Avisos de calidad (salida 3)**: cita no encontrada en el texto, cita < 40 o > 300 caracteres o ausente en un riesgo, **cita en una página distinta de la que indica `clausula`** (`pág. N`, `págs. N-M`; se tolera ±1 por saltos de página), riesgo `medio` o superior sin mejora asociada, veredicto inferior al riesgo más alto, **recuentos escritos a mano en `veredicto.texto` que no coinciden con los riesgos reales**, más de 20 riesgos, falta de `fecha_analisis`, ejecución sin `--texto`.

## Validar solo un fragmento (especialistas)
`render_report.py --fragmento resumen|riesgos|mejoras --texto texto.txt <fragmento.json> [riesgos.json]` valida la estructura y las citas de un único fragmento sin exigir el resto del informe. Con `mejoras`, si se añade `riesgos.json` también se comprueban referencias y cobertura. Salida igual que `--validar` (0 / 1 / 3).
