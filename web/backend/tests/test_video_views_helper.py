"""Testa o helper _video_3s_views_from_row presente nos 3 campaign_facebook_gather.py.
Como o helper é local de cada arquivo, importamos de um dos arquivos (são idênticos)."""

import sys
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3] / "core" / "categorias" / "lead_com_site" / "campaign_facebook_gather.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("cf_gather_lcs", ROOT)
    module = importlib.util.module_from_spec(spec)
    sys.modules["cf_gather_lcs"] = module
    spec.loader.exec_module(module)
    return module


def test_video_3s_views_returns_none_when_key_absent():
    m = _load_module()
    row = {"ad_id": "1", "impressions": "100"}
    assert m._video_3s_views_from_row(row) is None


def test_video_3s_views_reads_video_3_sec_watched_actions():
    m = _load_module()
    row = {
        "video_3_sec_watched_actions": [
            {"action_type": "video_view", "value": "42"},
        ],
    }
    assert m._video_3s_views_from_row(row) == 42


def test_video_3s_views_fallback_to_actions_video_view():
    m = _load_module()
    row = {
        "actions": [
            {"action_type": "post_engagement", "value": "10"},
            {"action_type": "video_view", "value": "15"},
        ],
    }
    assert m._video_3s_views_from_row(row) == 15


def test_video_3s_views_sums_multiple_video_actions():
    m = _load_module()
    row = {
        "video_3_sec_watched_actions": [
            {"action_type": "video_view", "value": "10"},
            {"action_type": "video_view", "value": "20"},
        ],
    }
    assert m._video_3s_views_from_row(row) == 30
