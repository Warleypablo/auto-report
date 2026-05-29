import io

import httpx
import pytest
import respx
from PIL import Image

from etl.thumbnails import fetch_e_redimensionar


def _png_bytes(w: int, h: int) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (w, h), (123, 45, 67)).save(buf, format="PNG")
    return buf.getvalue()


@respx.mock
def test_redimensiona_para_320_no_maior_lado():
    url = "https://example.com/img.png"
    respx.get(url).mock(
        return_value=httpx.Response(200, content=_png_bytes(1000, 500),
                                    headers={"Content-Type": "image/png"})
    )

    conteudo, mime = fetch_e_redimensionar(url, lado_max=320)

    assert mime == "image/jpeg"
    img = Image.open(io.BytesIO(conteudo))
    assert max(img.size) == 320          # maior lado vira 320
    assert img.size == (320, 160)        # proporção 2:1 mantida


@respx.mock
def test_nao_aumenta_imagem_menor_que_lado_max():
    url = "https://example.com/small.png"
    respx.get(url).mock(
        return_value=httpx.Response(200, content=_png_bytes(100, 80),
                                    headers={"Content-Type": "image/png"})
    )

    conteudo, mime = fetch_e_redimensionar(url, lado_max=320)

    assert mime == "image/jpeg"
    img = Image.open(io.BytesIO(conteudo))
    assert img.size == (100, 80)         # não faz upscale


@respx.mock
def test_levanta_excecao_em_http_erro():
    url = "https://example.com/broken.png"
    respx.get(url).mock(return_value=httpx.Response(404))

    with pytest.raises(Exception):
        fetch_e_redimensionar(url, lado_max=320)


@respx.mock
def test_levanta_excecao_em_conteudo_invalido():
    url = "https://example.com/notimage"
    respx.get(url).mock(
        return_value=httpx.Response(200, content=b"isto nao eh uma imagem")
    )

    with pytest.raises(Exception):
        fetch_e_redimensionar(url, lado_max=320)
