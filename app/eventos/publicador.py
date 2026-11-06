"""Cliente HTTP do Backend 2: `POST {BACKEND2_URL}/eventos/biblioteca` (CT12, §8)."""

from __future__ import annotations

import json
import ssl
from collections.abc import Mapping
from datetime import datetime
from typing import Any, Protocol

import httpx

from app.config import Config
from app.emprestimos.esquemas import data_hora_para_json

CAMINHO_EVENTOS = "/eventos/biblioteca"

EMPRESTIMO_REGISTRADO = "emprestimo_registrado"
DEVOLUCAO_REGISTRADA = "devolucao_registrada"

# Motivos de falha (§8): textos curtos, sem dados pessoais nem segredos.
FALHA_SEM_URL = "BACKEND2_URL não configurado"
FALHA_TIMEOUT = "timeout"
FALHA_CONEXAO = "falha de conexão"
FALHA_RESPOSTA_INVALIDA = "resposta inválida"
FALHA_NAO_ACEITO = "evento não aceito"
FALHA_INESPERADA = "erro inesperado na publicação"


class PublicadorDeEventos(Protocol):
    """Fronteira com o Backend 2 (§8A): trocar o servidor não muda regra de negócio."""

    def publicar(self, payload: Mapping[str, Any]) -> str | None:
        """Envia o evento uma vez. `None` se o Backend 2 aceitou; senão, o motivo da falha."""
        ...


def montar_payload(
    *,
    tipo: str,
    livro_id: int,
    usuario_id: int,
    emprestimo_id: int,
    status: str,
    quantidade_disponivel: int,
    atualizada_em: datetime,
) -> dict[str, Any]:
    """Corpo do CT12, com exatamente os sete campos."""
    return {
        "tipo": tipo,
        "livroId": livro_id,
        "usuarioId": usuario_id,
        "emprestimoId": emprestimo_id,
        "status": status,
        "quantidadeDisponivel": quantidade_disponivel,
        "atualizadaEm": data_hora_para_json(atualizada_em),
    }


def url_de_eventos(backend2_url: str | None) -> str | None:
    """`{BACKEND2_URL sem a barra final}/eventos/biblioteca`; `None` se não configurado."""
    if not backend2_url:
        return None
    return backend2_url.rstrip("/") + CAMINHO_EVENTOS


def verificacao_tls(config: Config) -> ssl.SSLContext | bool:
    """Certificado próprio (`BACKEND2_CA_BUNDLE`) ou a verificação padrão (§8, P12)."""
    if config.backend2_ca_bundle:
        return ssl.create_default_context(cafile=config.backend2_ca_bundle)
    return config.backend2_verify_tls


def classificar_resposta(resposta: httpx.Response) -> str | None:
    """`None` se 2xx com JSON `{"aceito": true, ...}`; senão, o motivo da falha."""
    if not resposta.is_success:
        return f"HTTP {resposta.status_code}"
    try:
        dados = resposta.json()
    except (ValueError, UnicodeDecodeError):
        return FALHA_RESPOSTA_INVALIDA
    if not isinstance(dados, dict):
        return FALHA_RESPOSTA_INVALIDA
    if dados.get("aceito") is not True:
        return FALHA_NAO_ACEITO
    return None


class PublicadorHttp:
    """Publicador real, com `httpx` síncrono (as rotas com banco são `def`)."""

    def __init__(self, config: Config) -> None:
        self._config = config

    def publicar(self, payload: Mapping[str, Any]) -> str | None:
        url = url_de_eventos(self._config.backend2_url)
        if url is None:
            return FALHA_SEM_URL
        try:
            # D20: `trust_env=False` não herda proxy, `SSL_CERT_*` nem `.netrc` do ambiente.
            with httpx.Client(
                timeout=self._config.backend2_timeout_segundos,
                verify=verificacao_tls(self._config),
                trust_env=False,
            ) as cliente:
                resposta = cliente.post(
                    url,
                    content=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                )
        except httpx.TimeoutException:
            return FALHA_TIMEOUT
        except httpx.TransportError:
            return FALHA_CONEXAO
        except Exception:  # certificado ilegível, URL inválida etc.: nunca derruba a operação
            return FALHA_INESPERADA
        return classificar_resposta(resposta)
