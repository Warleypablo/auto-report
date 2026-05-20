from fastapi import APIRouter, Depends, Header, HTTPException

from config import Settings, get_settings
from etl.collect import run_etl

router = APIRouter()


def _require_token(
    x_etl_token: str = Header(default=""),
    settings: Settings = Depends(get_settings),
) -> None:
    if not settings.etl_trigger_token or x_etl_token != settings.etl_trigger_token:
        raise HTTPException(status_code=401, detail="Token inválido")


@router.post("/etl/trigger", dependencies=[Depends(_require_token)])
def trigger_etl() -> dict:
    return run_etl()
