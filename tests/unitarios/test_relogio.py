"""Relógio injetável (8B, 00-convencoes §7)."""

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest

from app import relogio as modulo_relogio
from app.relogio import Relogio, RelogioFixo, RelogioSistema

pytestmark = pytest.mark.unitario

INSTANTE = datetime(2026, 10, 13, 19, 20, 0)


def test_relogio_sistema_converte_utc_para_sao_paulo_e_corta_microssegundos():
    utc = datetime(2026, 11, 6, 15, 0, 30, 987654, tzinfo=UTC)

    class DatetimeFalso(datetime):
        @classmethod
        def now(cls, tz=None):
            return utc.astimezone(tz)

    with patch.object(modulo_relogio, "datetime", DatetimeFalso):
        agora = RelogioSistema().agora()

    # Em novembro de 2026 São Paulo está em UTC-3 (sem horário de verão).
    assert agora == datetime(2026, 11, 6, 12, 0, 30)
    assert agora.tzinfo is None


def test_relogio_fixo_recusa_instante_com_fuso():
    with pytest.raises(ValueError):
        RelogioFixo(INSTANTE.replace(tzinfo=UTC))


def test_relogio_fixo_nao_devolve_microssegundos():
    relogio = RelogioFixo(INSTANTE.replace(microsecond=500_000))

    assert relogio.agora() == INSTANTE


def test_relogio_fixo_acumula_frações_ao_avancar():
    relogio = RelogioFixo(INSTANTE)

    relogio.avancar(timedelta(milliseconds=600))
    assert relogio.agora() == INSTANTE

    relogio.avancar(timedelta(milliseconds=600))
    assert relogio.agora() == INSTANTE + timedelta(seconds=1)


def test_relogio_fixo_aceita_avancar_para_tras():
    relogio = RelogioFixo(INSTANTE)

    relogio.avancar(timedelta(days=-1))

    assert relogio.agora() == INSTANTE - timedelta(days=1)


def test_implementacoes_seguem_o_protocolo():
    relogios: list[Relogio] = [RelogioSistema(), RelogioFixo(INSTANTE)]

    for relogio in relogios:
        assert isinstance(relogio.agora(), datetime)
