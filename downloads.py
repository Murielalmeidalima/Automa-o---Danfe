"""downloads.py — Manipulação da pasta de Downloads e gravação dos PDFs.

Responsável por:
  * localizar a pasta padrão de Downloads do Windows (e de outros sistemas);
  * gerar nomes de arquivo no padrão NF_<numero>.pdf sem sobrescrever
    arquivos existentes (sufixo sequencial);
  * gravar os bytes do PDF no disco;
  * abrir a pasta de Downloads no gerenciador de arquivos.
"""

from __future__ import annotations

import os
import platform
import subprocess
from pathlib import Path

import config


def pasta_downloads() -> Path:
    """Retorna a pasta padrão de Downloads, criando-a se necessário.

    No Windows usa %USERPROFILE%\\Downloads; nos demais sistemas usa o
    diretório Downloads do usuário. Se a pasta não existir, é criada.
    """
    if platform.system() == "Windows":
        perfil = os.environ.get("USERPROFILE") or str(Path.home())
        pasta = Path(perfil) / "Downloads"
    else:
        pasta = Path.home() / "Downloads"

    pasta.mkdir(parents=True, exist_ok=True)
    return pasta


def nome_arquivo_unico(diretorio: Path, numero_nota: str) -> Path:
    """Monta um nome de arquivo único no formato NF_<numero>.pdf.

    Se `NF_<numero>.pdf` já existir, acrescenta um sufixo sequencial:
    `NF_<numero> (1).pdf`, `NF_<numero> (2).pdf`, e assim por diante —
    nunca sobrescrevendo arquivos existentes.
    """
    base = f"{config.PREFIXO_PDF}{numero_nota}.pdf"
    candidato = diretorio / base

    sufixo = 1
    while candidato.exists():
        candidato = diretorio / f"{config.PREFIXO_PDF}{numero_nota} ({sufixo}).pdf"
        sufixo += 1

    return candidato


def salvar_pdf(pdf_bytes: bytes, numero_nota: str, diretorio: Path) -> Path:
    """Grava os bytes do PDF em um arquivo de nome único.

    Raises:
        OSError: quando ocorre falha de gravação (permissão, disco cheio etc.).
        ValueError: quando os bytes não correspondem a um PDF válido.
    """
    if not pdf_bytes.startswith(config.MAGIC_PDF):
        raise ValueError("Os dados recebidos não correspondem a um PDF válido.")

    caminho = nome_arquivo_unico(diretorio, numero_nota)
    with open(caminho, "wb") as arquivo:
        arquivo.write(pdf_bytes)

    return caminho


def abrir_pasta(caminho: Path) -> None:
    """Abre a pasta no gerenciador de arquivos do sistema."""
    if platform.system() == "Windows":
        os.startfile(str(caminho))  # type: ignore[attr-defined]
    elif platform.system() == "Darwin":
        subprocess.Popen(["open", str(caminho)])
    else:
        subprocess.Popen(["xdg-open", str(caminho)])