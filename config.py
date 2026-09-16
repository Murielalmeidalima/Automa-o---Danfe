"""config.py — Constantes e configurações centrais da aplicação.

Centraliza URLs da API, timeouts, delays e políticas de nova tentativa para
que os demais módulos não repitam valores soltos.
"""

# =============================================================================
# API pública do Consulta DANFE (sem chave de API, sem cadastro)
# =============================================================================
API_BASE_URL = "https://consultadanfe.com"
ENDPOINT_CONSULTA = f"{API_BASE_URL}/api/v1/consulta"
HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json",
    "User-Agent": "BaixadorDANFE/1.0",
}

# =============================================================================
# Requisições HTTP
# =============================================================================
TIMEOUT_SEGUNDOS = 30          # tempo máximo para cada chamada à API
DELAY_ENTRE_CHAVES = 1.2       # intervalo entre chaves (respeita 60 req/min)

# =============================================================================
# Nova tentativa (retry)
# =============================================================================
MAX_TENTATIVAS = 4             # total de tentativas por chave (1 primeira + retries)
BACKOFF_BASE = 2               # multiplicador exponencial: 2s, 4s, 8s...
BACKOFF_MAX = 8                # teto do backoff em segundos
RETRY_429_CAP = 30             # teto (em s) de espera ao receber rate limit (429)

# =============================================================================
# Arquivos / pastas
# =============================================================================
PREFIXO_PDF = "NF_"
PREFIXO_RELATORIO = "relatorio_danfes"
MAGIC_PDF = b"%PDF-"           # assinatura usada para validar o arquivo baixado

# Status possíveis para o relatório
STATUS_SUCESSO = "sucesso"
STATUS_FALHA = "falha"