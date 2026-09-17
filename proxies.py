"""proxies.py — Carregamento, validação e rotação de proxies.

Lê a lista de proxies de um arquivo texto (um por linha), valida a
conectividade e fornece o endereço de saída a cada requisição, permitindo
espalhar o limite por-IP entre vários proxies.

Formatos aceitos por linha (linhas em branco ou começando com `#` são
ignoradas):

    http://usuario:senha@host:porta
    https://usuario:senha@host:porta
    host:porta            (assume http://)

Uso rápido para testar os proxies do arquivo:

    python proxies.py --testar
"""

from __future__ import annotations

import threading

import requests

import config


def _normalizar_linha(linha: str) -> str:
    """Limpa uma linha do arquivo e garante o esquema do proxy."""
    texto = linha.strip()
    if not texto or texto.startswith("#"):
        return ""
    if "://" not in texto:
        texto = "http://" + texto
    return texto


def carregar_proxies(caminho: str | None = None) -> list[str]:
    """Lê o arquivo de proxies e devolve uma lista sem duplicatas."""
    caminho = caminho or config.ARQUIVO_PROXIES
    from pathlib import Path

    arquivo = Path(caminho)
    if not arquivo.is_absolute():
        arquivo = Path(__file__).resolve().parent / caminho
    if not arquivo.exists():
        return []

    proxies: list[str] = []
    for linha in arquivo.read_text(encoding="utf-8").splitlines():
        proxy = _normalizar_linha(linha)
        if proxy and proxy not in proxies:
            proxies.append(proxy)
    return proxies


def normalizar(proxy: str) -> dict[str, str]:
    """Formato exigido pelo requests, aplicando o mesmo proxy a http e https."""
    return {"http": proxy, "https": proxy}


def mascarar(proxy: str | None) -> str:
    """Esconde usuário:senha para uso seguro em logs."""
    if not proxy:
        return "direto"
    esquema, separador, resto = proxy.partition("://")
    if not separador:
        return proxy
    if "@" in resto:
        _, _, endereco = resto.rpartition("@")
        return f"{esquema}://***@{endereco}"
    return proxy


def validar(proxy: str, timeout: float | None = None) -> tuple[bool, str]:
    """Testa o proxy consultando o IP de saída.

    Returns:
        (True, "<ip>") quando responde; (False, "<motivo>") caso contrário.
    """
    tempo = timeout or config.TIMEOUT_TESTE_PROXY
    try:
        resp = requests.get(
            config.URL_TESTE_PROXY,
            proxies=normalizar(proxy),
            timeout=tempo,
        )
    except requests.exceptions.RequestException as exc:
        return False, type(exc).__name__
    if resp.status_code == 200:
        return True, resp.text.strip()
    return False, f"HTTP {resp.status_code}"


def _normalizar_candidato(texto: str) -> str:
    texto = texto.strip()
    if not texto or texto.startswith("#"):
        return ""
    if "://" in texto or ":" not in texto:
        return texto if "://" in texto else ""
    return "http://" + texto


def baixar_listas_gratis(fontes: list[str] | None = None) -> list[str]:
    """Baixa as listas públicas e devolve candidatos "http://ip:porta" únicos."""
    fontes = fontes or config.FONTES_PROXIES_GRATIS
    candidatos: list[str] = []
    vistos: set[str] = set()
    for url in fontes:
        try:
            resp = requests.get(url, timeout=20)
        except requests.exceptions.RequestException:
            continue
        if resp.status_code != 200:
            continue
        for linha in resp.text.splitlines():
            proxy = _normalizar_candidato(linha)
            if proxy and proxy not in vistos:
                vistos.add(proxy)
                candidatos.append(proxy)
    return candidatos


def validar_alvo(proxy: str, url: str, timeout: float | None = None) -> tuple[bool, str]:
    """Testa o proxy contra uma URL protegida (ex.: para checar o Cloudflare).

    Considera aprovado quando a URL responde normalmente (redireciona para 200).
    Bloqueios de Cloudflare costumam vir como 403/503.
    """
    tempo = timeout or config.TIMEOUT_TESTE_PROXY
    try:
        resp = requests.get(url, proxies=normalizar(proxy), timeout=tempo)
    except requests.exceptions.RequestException as exc:
        return False, type(exc).__name__
    if resp.status_code == 200:
        return True, "200"
    return False, f"HTTP {resp.status_code}"


def _testar_paralelo(
    candidatos: list[str], funcao, timeout: float
) -> list[tuple[str, bool, str]]:
    """Executa a validação em paralelo e devolve os resultados na ordem."""
    from concurrent.futures import ThreadPoolExecutor

    resultados: list[tuple[str, bool, str]] = []
    with ThreadPoolExecutor(max_workers=config.MAX_TESTE_CONCORRENTE) as pool:
        futuros = {
            pool.submit(funcao, proxy, timeout): proxy for proxy in candidatos
        }
        for futuro in futuros:
            proxy = futuros[futuro]
            try:
                ok, info = futuro.result()
            except Exception as exc:  # noqa: BLE001 — teste isolado nunca derruba
                ok, info = False, type(exc).__name__
            resultados.append((proxy, ok, info))
    # Preserva a ordem original dos candidatos.
    ordem = {proxy: i for i, proxy in enumerate(candidatos)}
    resultados.sort(key=lambda item: ordem[item[0]])
    return resultados


def buscar_proxies_gratis(url_alvo: str | None = None) -> list[str]:
    """Baixa listas grátis e valida em dois estágios, devolvendo os funcionais.

    Estágio 1: conectividade (consulta o IP de saída).
    Estágio 2: acesso ao alvo real (passa pelo Cloudflare?).
    """
    alvo = url_alvo or config.API_BASE_URL
    candidatos = baixar_listas_gratis()
    if not candidatos:
        return []

    limite = config.MAX_CANDIDATOS_BUSCA
    if len(candidatos) > limite:
        # Intercala as fontes para não testar só a primeira lista.
        passo = len(candidatos) / limite
        candidatos = [candidatos[int(i * passo)] for i in range(limite)]

    print(f"Candidatos a testar: {len(candidatos)}")
    print("Estágio 1/2 — testando conectividade...")
    estagio1 = _testar_paralelo(candidatos, validar, config.TIMEOUT_TESTE_BUSCA)
    vivos = [proxy for proxy, ok, _ in estagio1 if ok]
    print(f"  {len(vivos)} responderam.")

    if not vivos:
        return []

    print("Estágio 2/2 — testando acesso ao alvo (Cloudflare)...")
    estagio2 = _testar_paralelo(
        vivos, validar_alvo_por_url(alvo), config.TIMEOUT_TESTE_BUSCA
    )
    aprovados = [proxy for proxy, ok, _ in estagio2 if ok]
    print(f"  {len(aprovados)} passaram no alvo.")
    return aprovados


def validar_alvo_por_url(url: str):
    """Devolve uma função (proxy, timeout) -> (ok, info) fixando a URL alvo."""
    def _testar(proxy: str, timeout: float):
        return validar_alvo(proxy, url, timeout)

    return _testar


def salvar_proxies(lista: list[str], caminho: str | None = None) -> str:
    """Grava a lista em um arquivo (padrão: config.ARQUIVO_PROXIES)."""
    from pathlib import Path

    caminho = caminho or config.ARQUIVO_PROXIES
    destino = Path(caminho)
    if not destino.is_absolute():
        destino = Path(__file__).resolve().parent / caminho
    cabecalho = (
        "# Gerado automaticamente por 'python proxies.py --buscar'.\n"
        "# Proxies grátis: instáveis e, em boa parte, bloqueados pelo Cloudflare.\n"
    )
    destino.write_text(cabecalho + "\n".join(lista) + "\n", encoding="utf-8")
    return str(destino)


class GerenciadorProxies:
    """Mantém a lista de proxies e o índice do proxy em uso (thread-safe)."""

    def __init__(self, lista: list[str] | None = None):
        self._lock = threading.RLock()
        self._proxies: list[str] = list(lista or [])
        self._indice = 0
        self._falhas: dict[str, int] = {}
        self._requisicoes = 0
        self._carregado = False

    # -- carga / recarga ------------------------------------------------
    def carregar(self, caminho: str | None = None) -> int:
        """(Re)lê o arquivo de proxies e reinicia a rotação."""
        with self._lock:
            self._proxies = carregar_proxies(caminho)
            self._indice = 0
            self._falhas = {}
            self._requisicoes = 0
            self._carregado = True
            return len(self._proxies)

    def garantir_carregado(self) -> None:
        """Carrega o arquivo uma única vez, de forma preguiçosa."""
        if not self._carregado:
            self.carregar()

    # -- consultas ------------------------------------------------------
    def total(self) -> int:
        with self._lock:
            return len(self._proxies)

    def vazio(self) -> bool:
        return self.total() == 0

    def atual(self) -> str:
        with self._lock:
            if not self._proxies:
                return ""
            return self._proxies[self._indice % len(self._proxies)]

    def atual_normalizado(self) -> dict[str, str] | None:
        proxy = self.atual()
        return normalizar(proxy) if proxy else None

    def falhas(self, proxy: str) -> int:
        with self._lock:
            return self._falhas.get(proxy, 0)

    def descricao(self) -> str:
        with self._lock:
            if not self._proxies:
                return "direto"
            posicao = self._indice % len(self._proxies)
            return f"{mascarar(self._proxies[posicao])} ({posicao + 1}/{len(self._proxies)})"

    # -- rotação --------------------------------------------------------
    def proximo(self) -> str:
        """Avança para o próximo proxy e o devolve."""
        with self._lock:
            if not self._proxies:
                return ""
            if len(self._proxies) > 1:
                self._indice = (self._indice + 1) % len(self._proxies)
            return self._proxies[self._indice]

    def marcar_falha(self) -> None:
        """Registra uma falha no proxy atual (não o remove; serve de métrica)."""
        with self._lock:
            proxy = self.atual()
            if proxy:
                self._falhas[proxy] = self._falhas.get(proxy, 0) + 1

    def contar_requisicao(self) -> None:
        """Conta a requisição e rotaciona a cada N, se configurado."""
        with self._lock:
            self._requisicoes += 1
            intervalo = config.ROTACIONAR_A_CADA_N
            if intervalo > 0 and self._requisicoes % intervalo == 0:
                self.proximo()


_gerenciador_global = GerenciadorProxies()


def obter_gerenciador() -> GerenciadorProxies:
    """Instância única compartilhada por toda a aplicação."""
    return _gerenciador_global


def _testar() -> int:
    lista = carregar_proxies()
    if not lista:
        print(f"Nenhum proxy encontrado em '{config.ARQUIVO_PROXIES}'.")
        print("Crie o arquivo com um proxy por linha, por exemplo:")
        print("  http://usuario:senha@host:porta")
        return 1

    print(f"Testando {len(lista)} proxy(es)...\n")
    vivos = 0
    for proxy in lista:
        ok, info = validar(proxy)
        marca = "OK   " if ok else "FALHA"
        print(f"[{marca}] {mascarar(proxy)} -> {info}")
        vivos += int(ok)

    print(f"\n{vivos}/{len(lista)} proxy(es) respondendo.")
    return 0 if vivos else 1


def _buscar(salvar: bool) -> int:
    aprovados = buscar_proxies_gratis()
    print()
    if not aprovados:
        print("Nenhum proxy grátis passou no alvo (esperado).")
        print("Listas grátis são quase todas datacenter e o Cloudflare bloqueia.")
        print("\nAlternativas grátis reais:")
        print("  - Rodar o robô pela rede do celular (hotspot 4G/5G).")
        print("  - Tentar em outra rede/horário (cada IP tem cota própria).")
        return 1

    print(f"Aprovados ({len(aprovados)}):")
    for proxy in aprovados:
        print(f"  {mascarar(proxy)}")
    if salvar:
        print(f"\nGravados em {salvar_proxies(aprovados)}")
    else:
        print("\nPara gravar em proxies.txt: python proxies.py --buscar --salvar")
    return 0


if __name__ == "__main__":
    import sys

    if "--testar" in sys.argv:
        raise SystemExit(_testar())
    if "--buscar" in sys.argv:
        raise SystemExit(_buscar("--salvar" in sys.argv))
    print(__doc__)
