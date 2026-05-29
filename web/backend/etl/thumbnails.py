from __future__ import annotations

import io

import httpx
from PIL import Image

TIMEOUT = 30


def fetch_e_redimensionar(url: str, *, lado_max: int = 320) -> tuple[bytes, str]:
    """Baixa a imagem da URL, redimensiona para `lado_max` px no maior lado
    (mantém proporção, sem upscale) e retorna (bytes, mime).

    Sempre re-codifica como JPEG (mime 'image/jpeg'). Levanta exceção em
    falha de download (status != 2xx) ou decode (caller marca thumb_status=ERRO).
    """
    resp = httpx.get(url, timeout=TIMEOUT, follow_redirects=True)
    resp.raise_for_status()

    img = Image.open(io.BytesIO(resp.content))
    img.load()  # força o decode aqui (levanta se o conteúdo for inválido)

    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")

    largura, altura = img.size
    maior = max(largura, altura)
    if maior > lado_max:
        escala = lado_max / maior
        nova = (max(1, round(largura * escala)), max(1, round(altura * escala)))
        img = img.resize(nova, Image.Resampling.LANCZOS)

    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="JPEG", quality=82)
    return buf.getvalue(), "image/jpeg"
