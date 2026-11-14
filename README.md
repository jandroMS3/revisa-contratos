# Revisa Contratos

Sistema de agentes de GitHub Copilot (VS Code) que revisa un contrato en PDF desde la posición de **quien lo recibe para firmarlo** y genera un informe HTML con resumen, puntos clave, riesgos por severidad y mejoras negociables con redacción sugerida.

## Cómo funciona

```
Orquestador de Contratos  ──►  Revisor de Contratos  ──►  contratos-resumen
 (único punto de entrada)       (coordina)                 contratos-riesgos
                                                           contratos-mejoras
                                                           contratos-critico (verifica)
```

1. El **Orquestador** recoge los datos (PDF, tu rol en el contrato) y decide el flujo: revisión nueva, nueva versión, regenerar informe o comparar versiones.
2. Se extrae el texto del PDF y los especialistas escriben fragmentos JSON; el crítico los contrasta con el texto.
3. Un script determinista valida que las citas existan literalmente en el contrato y renderiza el informe HTML (autocontenido, apto para imprimir).

Todo vive en [.github/](.github): agentes en `agents/` y skills (metodología, extracción de PDF y generación del informe) en `skills/`.

## Puesta en marcha

Requisitos: VS Code con GitHub Copilot (modo agente y subagentes personalizados) y Python 3.

```bash
git clone <url-del-repo>
cd revisaContratos
bash .github/skills/extraer-texto-pdf/scripts/setup.sh   # crea .venv e instala pypdf
```

Alternativa manual: `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt`.

## Uso

1. Abre la carpeta en VS Code y copia tu contrato a `contratos/`.
2. En el chat de Copilot elige el agente **Orquestador de Contratos** y pide, por ejemplo:
   - `revisa contratos/alquiler.pdf, soy el inquilino`
   - `nueva versión del informe` / `qué ha cambiado respecto a la versión anterior`
   - `regenera los informes`
3. El informe queda en `informes/<contrato>-informe.html`; ábrelo en cualquier navegador.

## Opcional

- **PDF escaneado** (sin capa de texto): `brew install ocrmypdf`; el agente te lo indicará cuando haga falta.
- **Tests**: `python3 -m unittest discover -s .github/skills/informe-contrato-html/tests` (y lo mismo con `extraer-texto-pdf/tests`).

## Privacidad

Los contratos y todo lo derivado (texto extraído, JSON, informes) son datos sensibles: `contratos/` e `informes/` están en el [.gitignore](.gitignore) y no se suben al repositorio. Nada se envía a servicios externos salvo el propio Copilot.

> Esta herramienta es una ayuda al análisis, no asesoramiento jurídico.
