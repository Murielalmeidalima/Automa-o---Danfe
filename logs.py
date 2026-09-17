"""logs.py — Registro em arquivo para diagnóstico das execuções.

Escreve em `Downloads/danfe_downloader.log` todas as requisições, status
HTTP, headers de limite (Retry-After) e erros — o essencial para entender
por que a API recusou uma consulta. O arquivo gira automaticamente para
não crescer indefinidamente.
"""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

import downloads

_NOME_LOGGER = "danfe"
_ARQUIVO_LOG = "danfe_downloader.log"
_TAMANHO_MAXIMO = 1_000_000     # ~1 MB por arquivo
_BACKUPS = 3

_configurado = False


def _configurar() -> None:
    """Anexa o handler de arquivo ao logger (executado uma única vez)."""
    global _configurado
    if _configurado:
        return

    logger = logging.getLogger(_NOME_LOGGER)
    logger.setLevel(logging.INFO)
    logger.propagate = False

    try:
        caminho = downloads.pasta_downloads() / _ARQUIVO_LOG
        handler = RotatingFileHandler(
            caminho,
            maxBytes=_TAMANHO_MAXIMO,
            backupCount=_BACKUPS,
            encoding="utf-8",
        )
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s | %(levelname)s | %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
        logger.addHandler(handler)
    except OSError:
        # Sem permissão para gravar: a ferramenta continua funcionando,
        # apenas sem log em arquivo.
        logger.addHandler(logging.NullHandler())

    _configurado = True


def obter_logger() -> logging.Logger:
    """Devolve o logger da aplicação, já configurado para gravar em arquivo."""
    _configurar()
    return logging.getLogger(_NOME_LOGGER)


def caminho_log():
    """Retorna o caminho do arquivo de log (útil para abrir/exibir na interface)."""
    return downloads.pasta_downloads() / _ARQUIVO_LOG
