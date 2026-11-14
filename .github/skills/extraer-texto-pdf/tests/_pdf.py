"""Genera PDF mínimos con texto para las pruebas (sin dependencias)."""


def _esc(linea: str) -> str:
    return linea.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def pdf_bytes(paginas):
    """`paginas`: lista de textos (líneas separadas por \\n). Devuelve el contenido de un PDF válido."""
    n = len(paginas)
    kids = " ".join(f"{4 + 2 * i} 0 R" for i in range(n))
    objs = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        f"<< /Type /Pages /Kids [{kids}] /Count {n} >>".encode(),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
    ]
    for i, texto in enumerate(paginas):
        flujo = "BT /F1 11 Tf 14 TL 50 780 Td " + " ".join(f"({_esc(ln)}) Tj T*" for ln in texto.split("\n")) + " ET"
        datos = flujo.encode("cp1252")
        objs.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 3 0 R >> >> "
            f"/Contents {5 + 2 * i} 0 R >>".encode())
        objs.append(b"<< /Length %d >>\nstream\n" % len(datos) + datos + b"\nendstream")

    salida, offsets = bytearray(b"%PDF-1.4\n"), []
    for k, obj in enumerate(objs, start=1):
        offsets.append(len(salida))
        salida += f"{k} 0 obj\n".encode() + obj + b"\nendobj\n"
    xref = len(salida)
    salida += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
    for off in offsets:
        salida += f"{off:010d} 00000 n \n".encode()
    salida += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return bytes(salida)
