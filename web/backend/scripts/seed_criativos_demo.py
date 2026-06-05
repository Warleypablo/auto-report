"""Seed de DEMONSTRAÇÃO de criativos para testar a página /gestor/performance localmente.

Aditivo e re-runnable: limpa apenas as linhas cujo ad_id começa com 'demo-'.
NÃO toca em clientes / snapshots / usuários — só popula criativos, criativo_thumbs e
ad_insights de exemplo (Meta + Google, com thumbs geradas, últimos 30 dias) para os
primeiros clientes ativos, de modo a dar o que ver na página de criativos.

Uso (a partir de web/backend/):
    .venv/bin/python -m scripts.seed_criativos_demo [N_CLIENTES]
"""
from __future__ import annotations

import io
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from PIL import Image, ImageDraw  # noqa: E402
from sqlalchemy import select, text  # noqa: E402

from db import SessionLocal  # noqa: E402
from etl.thumbnails import fetch_e_redimensionar  # noqa: E402
from models import AdInsight, Cliente, Criativo, CriativoThumb, RedeAnuncio, ThumbStatus  # noqa: E402

_CORES = [
    (214, 69, 65), (38, 128, 235), (52, 168, 83), (251, 188, 5),
    (142, 68, 173), (26, 188, 156), (230, 126, 34), (52, 73, 94),
]

# (rede, tipo, tem_imagem)
_DEFS = [
    ("META", "imagem", True),
    ("META", "video", True),
    ("META", "imagem", True),
    ("META", "carrossel", True),
    ("GOOGLE", "display", True),
    ("GOOGLE", "pmax", True),
    ("GOOGLE", "search", False),
]


def _thumb_jpeg(cor: tuple[int, int, int], rotulo: str) -> bytes:
    img = Image.new("RGB", (320, 320), cor)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 250, 320, 320], fill=(0, 0, 0))
    d.text((12, 270), rotulo[:28], fill=(255, 255, 255))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=82)
    return buf.getvalue()


def main() -> None:
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 8
    hoje = date.today()
    thumbs_tasks: list = []  # (criativo_id, ad_id, cor_fallback, rotulo) — baixadas em paralelo no fim
    with SessionLocal() as s:
        # limpa qualquer demo anterior (idempotente)
        s.execute(text("DELETE FROM ad_insights WHERE ad_id LIKE 'demo-%'"))
        s.execute(
            text(
                "DELETE FROM criativo_thumbs WHERE criativo_id IN "
                "(SELECT id FROM criativos WHERE ad_id LIKE 'demo-%')"
            )
        )
        s.execute(text("DELETE FROM criativos WHERE ad_id LIKE 'demo-%'"))
        s.commit()

        clientes = s.scalars(
            select(Cliente).where(Cliente.ativo.is_(True)).order_by(Cliente.nome).limit(n)
        ).all()
        slugs = [c.slug for c in clientes]

        n_cri = 0
        n_ins = 0
        for ci, cliente in enumerate(clientes):
            eh_lead = cliente.categoria.name.startswith("LEAD")
            for di, (rede, tipo, tem_img) in enumerate(_DEFS):
                ad_id = f"demo-{cliente.slug}-{rede.lower()}-{di}"
                # 3 coortes escalonadas em 90 dias para que os filtros de período
                # mostrem QUANTIDADES diferentes de criativos:
                #   cohort 0 (recente) [hoje-29, hoje] · 1 (médio) [hoje-59, hoje-30]
                #   · 2 (antigo) [hoje-89, hoje-60]
                cohort = (ci + di) % 3
                win_fim = hoje - timedelta(days=30 * cohort)
                win_ini = win_fim - timedelta(days=29)
                if rede == "META":
                    preview = f"https://www.facebook.com/ads/library/?id=demo{ci}{di}"
                elif tem_img:
                    preview = f"https://ads.google.com/aw/ads?ocid=demo&adId={ci}{di}"
                else:
                    preview = None

                cr = Criativo(
                    cliente_id=cliente.id,
                    rede=RedeAnuncio[rede],
                    ad_id=ad_id,
                    nome=f"{cliente.nome} · {tipo} #{di + 1}",
                    tipo=tipo,
                    preview_link=preview,
                    thumb_status=ThumbStatus.OK if tem_img else ThumbStatus.SEM_IMAGEM,
                    primeiro_dia=win_ini,
                    ultimo_dia=win_fim,
                )
                s.add(cr)
                s.flush()
                if tem_img:
                    thumbs_tasks.append((cr.id, ad_id, _CORES[(ci + di) % len(_CORES)], cr.nome))
                n_cri += 1

                base_inv = Decimal(50 + 30 * di + 20 * ci)
                # ROAS variado e determinístico, SEM correlação com o tipo do anúncio.
                # (Antes era monotônico em `di`: o search ad — que não tem imagem — caía
                # no maior `di` e ganhava o ROAS mais alto, liderando o ranking de Criativos
                # e empurrando todos os criativos COM foto para baixo da dobra.)
                roas_alvo = Decimal("1.0") + Decimal((ci * 5 + di * 3) % 9) * Decimal("0.5")  # 1.0x .. 5.0x
                for d in range(30):
                    dia = win_ini + timedelta(days=d)
                    inv = (base_inv * (Decimal(1) + Decimal(d % 5) / Decimal(10))).quantize(Decimal("0.01"))
                    fat = (inv * roas_alvo).quantize(Decimal("0.01"))
                    imp = 1000 + 50 * d + 100 * di
                    conv = (fat / Decimal(120)).quantize(Decimal("0.01"))
                    s.add(
                        AdInsight(
                            cliente_id=cliente.id,
                            rede=RedeAnuncio[rede],
                            ad_id=ad_id,
                            dia=dia,
                            investimento=inv,
                            faturamento=fat,
                            conversoes=conv,
                            leads=(int(conv) if eh_lead else None),
                            impressoes=imp,
                            clicks=20 + d + di,
                            video_3s=(imp // 3 if tipo == "video" else None),
                            reach=int(imp * 0.8),
                        )
                    )
                    n_ins += 1
        s.commit()  # criativos + ad_insights persistidos (ids válidos p/ as thumbs)

        # Baixa as thumbs em PARALELO (determinísticas por ad_id) pelo mesmo pipeline
        # de rehospedagem da produção; cai pra cor sólida se algum download falhar.
        def _baixar(task):
            cid, ad_id_, cor, rotulo = task
            try:
                conteudo, mime = fetch_e_redimensionar(f"https://picsum.photos/seed/{ad_id_}/600/600")
            except Exception:
                conteudo, mime = _thumb_jpeg(cor, rotulo), "image/jpeg"
            return cid, conteudo, mime

        with ThreadPoolExecutor(max_workers=12) as ex:
            for cid, conteudo, mime in ex.map(_baixar, thumbs_tasks):
                s.add(CriativoThumb(criativo_id=cid, conteudo=conteudo, mime=mime))
        s.commit()

    print(f"Seed demo concluído: {len(slugs)} clientes, {n_cri} criativos, {n_ins} ad_insights, {len(thumbs_tasks)} thumbs.")
    print("Clientes semeados:", ", ".join(slugs))
    print("Período (escalonado, 3 coortes):", (hoje - timedelta(days=89)).isoformat(), "→", hoje.isoformat())
    print("Para limpar: DELETE FROM ad_insights/criativo_thumbs/criativos WHERE ad_id LIKE 'demo-%'")


if __name__ == "__main__":
    main()
