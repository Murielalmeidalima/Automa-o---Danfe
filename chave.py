"""chave.py — Validação de chaves de acesso de NF-e (44 caracteres).

A chave de acesso segue o leiaute da SEFAZ e pode conter apenas letras (A-Z)
e dígitos (0-9). Chaves 100% numéricas passam pelo dígito verificador mod-11
tradicional; chaves com letras usam o algoritmo da NT 2026.004 (CNPJ
alfanumérico), portanto o DV é delegado à própria API, evitando rejeitar
chaves válidas com um cálculo incorreto.
"""

import re

# Padrão oficial: 44 caracteres, apenas A-Z e 0-9 (NT 2026.004)
_PADRAO_CHAVE = re.compile(r"^[A-Z0-9]{44}$")
_TAMANHO_CHAVE = 44


def normalizar_chave(texto: str) -> str:
    """Remove espaços, hífens, pontuação e converte para maiúsculas.

    Mantém apenas letras e dígitos. O tamanho original é preservado para
    que a validação possa acusar "quantidade incorreta de dígitos".
    """
    return re.sub(r"[^A-Za-z0-9]", "", texto).upper()


def _dv_mod11(chave: str) -> int:
    """Calcula o dígito verificador mod-11 da chave (somente numérica).

    Pesos de 2 a 9 sobre os 43 primeiros caracteres, da direita para a
    esquerda; DV = 11 - (soma % 11), podendo resultar em 0 ou 1.
    """
    pesos = [item for item in range(2, 10)] * 5 + [2, 3, 4]
    soma = sum(int(digito) * peso for digito, peso in zip(reversed(chave[:43]), pesos))
    resto = soma % 11
    return 0 if resto in (0, 1) else 11 - resto


def validar_chave(chave: str) -> tuple[bool, str]:
    """Valida a chave de acesso.

    Returns:
        (True, "")            se a chave é válida;
        (False, msg_motivo)   caso contrário, com a mensagem legível do erro.
    """
    if not chave:
        return False, "Chave de acesso vazia."

    if len(chave) != _TAMANHO_CHAVE:
        return False, (
            f"Quantidade incorreta de dígitos: encontrados {len(chave)} "
            f"caracteres (esperado {_TAMANHO_CHAVE})."
        )

    if not _PADRAO_CHAVE.fullmatch(chave):
        return False, "Chave inválida: use apenas letras (A-Z) e números (0-9)."

    # DV mod-11 apenas para chaves 100% numéricas (leiaute tradicional).
    # Chaves alfanuméricas têm o DV validado pela API (NT 2026.004).
    if chave.isdigit():
        dv_calculado = _dv_mod11(chave)
        if dv_calculado != int(chave[43]):
            return False, "Chave inválida: dígito verificador incorreto."

    return True, ""


def numero_nota_da_chave(chave: str) -> str:
    """Extrai o número da nota fiscal da chave de acesso.

    Conforme o leiaute SEFAZ, as posições 26 a 34 (índices 25:34) da chave
    contêm o nNF da nota. O valor é devolvido sem zeros à esquerda,
    ex.: "000000269" -> "269".
    """
    if len(chave) < 34 or not chave[25:34].isdigit():
        return ""
    return str(int(chave[25:34]))