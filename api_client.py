"""api_client.py — Cliente da API pública do Consulta DANFE.

Concentra toda a comunicação HTTP com o endpoint /api/v1/consulta:
  1. Valida o contrato da resposta;
  2. Traduz códigos de erro (header X-Error-Code + JSON) para mensagens
     legíveis ao usuário;
  3. Aplica nova tentativa com backoff exponencial para falhas transitórias
     (timeout, rede, 5xx e rate limit).
"""

from __future__ import annotations

import base64
import time
import xml.etree.ElementTree as ET

import requests

import config


class ErroAPI(Exception):
    """Erro de domínio da API, com mensagem pronta para exibição."""

    def __init__(self, mensagem: str, codigo: str = ""):
        super().__init__(mensagem)
        self.mensagem = mensagem
        self.codigo = codigo


# =============================================================================
# Mensagens padronizadas por código de erro da API
# =============================================================================
_MENSAGENS_ERRO = {
    "chave_obrigatoria": "Chave de acesso é obrigatória.",
    "chave_invalida": "Chave inválida: use 44 caracteres entre A-Z e 0-9.",
    "dv_invalido": "Chave inválida: dígito verificador incorreto.",
    "tipo_nao_suportado": "Tipo de documento não suportado.",
    "nao_encontrada": "DANFE não encontrada na SEFAZ.",
    "pendente": "NF-e pendente ou em contingência; tente novamente depois.",
    "servico_indisponivel": "Serviço temporariamente indisponível.",
    "erro_interno": "Erro interno na API.",
}


def _mensagem_por_codigo(codigo: str, fallback: str) -> str:
    return _MENSAGENS_ERRO.get(codigo, fallback)


def _extrair_nnf(xml_base64: str) -> str:
    """Tenta ler o número da nota (<nNF>) a partir do XML retornado.

    Retorna "" quando o XML não está presente ou não pôde ser lido.
    """
    if not xml_base64:
        return ""
    try:
        raiz = ET.fromstring(base64.b64decode(xml_base64))
    except (ET.ParseError, ValueError, base64.binascii.Error):
        return ""
    for elemento in raiz.iter():
        if elemento.tag.rsplit("}", 1)[-1] == "nNF" and elemento.text:
            texto = elemento.text.strip()
            if texto.isdigit():
                return str(int(texto))
    return ""


def consultar_danfe(chave: str) -> dict:
    """Consulta o DANFE de uma chave na API, com retries por falha transitória.

    Args:
        chave: chave de acesso de 44 caracteres (já validada pelo chamador).

    Returns:
        dict com:
          {ok: True,  chave, numero, pdf_bytes, tipo}                em sucesso;
          {ok: False, chave, numero ("" ou valor), mensagem, codigo} em falha.
    """
    ultimo_erro: ErroAPI | None = None
    tentativa = 0

    while tentativa < config.MAX_TENTATIVAS:
        tentativa += 1
        try:
            resp = requests.post(
                config.ENDPOINT_CONSULTA,
                json={"chave": chave, "format": "json"},
                headers=config.HEADERS,
                timeout=config.TIMEOUT_SEGUNDOS,
            )
        except requests.exceptions.Timeout as exc:
            ultimo_erro = ErroAPI(
                "Tempo de resposta excedido (timeout).", "timeout"
            )
            retry = _dependente_de_retry_falha(ultimo_erro.codigo, tentativa)
            if retry:
                time.sleep(retry)
            continue
        except requests.exceptions.RequestException as exc:
            ultimo_erro = ErroAPI(
                "Falha de comunicação com a API.", "falha_comunicacao"
            )
            retry = _dependente_de_retry_falha(ultimo_erro.codigo, tentativa)
            if retry:
                time.sleep(retry)
            continue
        except Exception as exc:  # noqa: BLE001 — fronteira de rede: nunca deixar vazar
            return {
                "ok": False,
                "chave": chave,
                "numero": "",
                "mensagem": f"Falha de comunicação com a API ({type(exc).__name__}).",
                "codigo": "falha_comunicacao",
            }

        # ---- resposta HTTP recebida --------------------------------------
        if resp.status_code == 200:
            try:
                dados = resp.json()
            except ValueError as exc:
                return {
                    "ok": False,
                    "chave": chave,
                    "numero": "",
                    "mensagem": "Resposta inválida (formato inesperado).",
                    "codigo": "resposta_invalida",
                }

            if dados.get("status") == "ok" and dados.get("pdf_base64"):
                try:
                    pdf_bytes = base64.b64decode(dados["pdf_base64"], validate=True)
                except (ValueError, base64.binascii.Error) as exc:
                    return {
                        "ok": False,
                        "chave": chave,
                        "numero": "",
                        "mensagem": "Falha no download: PDF retornado em formato incorreto.",
                        "codigo": "pdf_base64_invalido",
                    }
                if not pdf_bytes.startswith(config.MAGIC_PDF):
                    return {
                        "ok": False,
                        "chave": chave,
                        "numero": "",
                        "mensagem": "Falha no download: PDF retornado vazio ou corrompido.",
                        "codigo": "pdf_corrompido",
                    }
                numero = _extrair_nnf(dados.get("xml_base64") or "") or chave[25:34]
                return {
                    "ok": True,
                    "chave": chave,
                    "numero": str(int(numero)) if str(numero).isdigit() else numero,
                    "pdf_bytes": pdf_bytes,
                    "tipo": dados.get("tipo", ""),
                }

            erro = _extrair_mensagem_erro(dados, resp)
            return {
                "ok": False,
                "chave": chave,
                "numero": "",
                "mensagem": erro.mensagem,
                "codigo": erro.codigo,
            }

        # ---- erro HTTP (4xx/5xx) -----------------------------------------
        erro = _erro_por_status(resp)
        if resp.status_code == 429:
            retry = _dependente_de_retry_rate_limit(resp, tentativa, erro)
            if retry:
                time.sleep(retry)
                continue
        elif resp.status_code >= 500:
            # Falhas de servidor: nova tentativa com backoff exponencial.
            if tentativa < config.MAX_TENTATIVAS:
                time.sleep(min(
                    config.BACKOFF_MAX,
                    config.BACKOFF_BASE ** (tentativa - 1),
                ))
                continue
        else:
            # Erros 4xx determinísticos (400/413/422/404/etc.): sem retry.
            pass

        ultimo_erro = erro

    # Esgotou as tentativas.
    return {
        "ok": False,
        "chave": chave,
        "numero": "",
        "mensagem": ultimo_erro.mensagem,
        "codigo": ultimo_erro.codigo,
    }


def _extrair_mensagem_erro(dados: dict, resp: requests.Response) -> ErroAPI:
    """Monta a mensagem de erro a partir do JSON `{error, message}` e headers."""
    codigo = dados.get("error") or resp.headers.get("X-Error-Code", "")
    mensagem = dados.get("message") or _mensagem_por_codigo(
        codigo, f"Erro ao consultar a chave (HTTP {resp.status_code})."
    )
    return ErroAPI(mensagem, codigo)


def _erro_por_status(resp: requests.Response) -> ErroAPI:
    """Converte o status HTTP em um ErroAPI com mensagem legível."""
    if resp.status_code == 404:
        return ErroAPI("DANFE não encontrada.", "nao_encontrada")
    if resp.status_code == 429:
        return ErroAPI("Limite de requisições atingido.", "rate_limit_exceeded")
    if resp.status_code == 503:
        return ErroAPI("Serviço temporariamente indisponível.", "servico_indisponivel")
    if resp.status_code == 202:
        return ErroAPI("NF-e pendente; tente novamente.", "pendente")
    codigo = resp.headers.get("X-Error-Code", "")
    mensagem = _mensagem_por_codigo(
        codigo, f"Erro na API (HTTP {resp.status_code})."
    )
    return ErroAPI(mensagem, codigo)


def _dependente_de_retry_falha(codigo: str, tentativa: int) -> float:
    """Backoff exponencial para timeout/falha de rede nas tentativas seguintes."""
    if tentativa >= config.MAX_TENTATIVAS:
        return 0.0
    return min(config.BACKOFF_MAX, config.BACKOFF_BASE ** (tentativa - 1))


def _dependente_de_retry_rate_limit(
    resp: requests.Response, tentativa: int, erro: ErroAPI
) -> float:
    """Espera respeitando o Retry-After (capzado) quando ainda houver tentativa."""
    if tentativa >= config.MAX_TENTATIVAS:
        return 0.0
    retry_after = resp.headers.get("Retry-After")
    espera = 0.0
    try:
        espera = float(retry_after) if retry_after else 0.0
    except (TypeError, ValueError):
        espera = 0.0
    if espera <= 0:
        espera = min(config.BACKOFF_MAX, config.BACKOFF_BASE ** (tentativa - 1))
    return min(espera, config.RETRY_429_CAP)