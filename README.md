# Baixador de DANFE

Aplicação desktop (Python + CustomTkinter) que baixa DANFEs de várias notas
fiscais de uma vez usando a **API pública gratuita** do
[Consulta DANFE](https://consultadanfe.com/api), a partir apenas da
**chave de acesso (44 dígitos)** de cada NF-e — sem XML.

Os PDFs são salvos na pasta **Downloads** do Windows com o nome
`NF_<numero_da_nota>.pdf` (o número da nota é lido do próprio retorno da API).
Caso o arquivo já exista, é criado `NF_<numero> (1).pdf`, `NF_<numero> (2).pdf`,
etc. — sem sobrescrever. Ao final, um relatório `relatorio_danfes_<data>.xlsx`
com o resultado de cada chave também é salvo na Downloads.

## Fluxo

1. Cole várias chaves de acesso (uma por linha).
2. Clique em **Processar DANFEs**.
3. Cada chave é validada (44 dígitos + dígito verificador) e consultada na API.
4. O PDF é baixado e renomeado com o número da nota.
5. Barra de progresso + contadores em tempo real (processadas / sucesso / falhas).
6. Resumo final na própria tela + relatório `relatorio_danfes_<data>.xlsx`.

## Recursos da interface

- **Processar DANFEs** — executa a consulta das chaves.
- **Copiar Chaves com Erro** — copia apenas as chaves que falharam (para nova tentativa).
- **Abrir Downloads** — abre a pasta de Downloads.
- **Nova Consulta** — limpa a tela para uma nova execução.
- **Fechar** — encerra o programa.

## Instalação (para desenvolvedor)

Requer Python 3.10+ com `venv`.

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

pip install -r requirements.txt
python main.py
```

> Dica: no Windows basta dar duplo clique em `abrir_danfe.bat` — ele cria o
> ambiente, instala as dependências e abre o programa sozinho.

## Gerar o executável único (.exe) — para enviar via WhatsApp

Existem **duas formas** de gerar o `BaixadorDANFE.exe`. O resultado é o
mesmo: um único arquivo que roda em qualquer Windows **sem Python instalado**.

### Opção 1 — `gerar_exe.bat` (1 duplo clique, com ou sem Python)

No PC **Windows** (pode ser qualquer um), dê duplo clique em **`gerar_exe.bat`**:

- Se houver Python → usa o existente.
- Se **não houver Python** → o próprio script **instala automaticamente**
  (via `winget`, ou baixando o instalador oficial do python.org em modo
  silencioso, sem precisar de administrador) e depois compila.

Em ~2–5 minutos é gerado:

```
dist\BaixadorDANFE.exe
```

### Opção 2 — GitHub Actions (build na nuvem, NENHUM Python necessário)

Ideal quando não há nenhum Windows com Python disponível. O build roda na
nuvem do GitHub (que já tem Python):

1. Crie/use um repositório no GitHub e suba a pasta `danfe_downloader`
   (o arquivo de pipeline já está em `.github/workflows/gerar-exe.yml`).
2. Na aba **Actions** do repositório, abra **"Gerar BaixadorDANFE.exe"** e
   clique em **"Run workflow"**.
3. Aguarde o build (~2–4 min), abra o job e baixe o artefato
   **BaixadorDANFE** — dentro dele está o `BaixadorDANFE.exe`.

### Como rodar o .exe

1. Salve `BaixadorDANFE.exe` em qualquer pasta do PC da empresa.
2. Duplo clique para abrir.
3. Se o Windows SmartScreen avisar "Protegido/Desconhecido" (arquivo sem
   assinatura digital), clique em **Mais informações → Executar mesmo assim**.

## API utilizada

| Item | Valor |
|---|---|
| Endpoint | `POST https://consultadanfe.com/api/v1/consulta` |
| Corpo | `{"chave": "<44 digitos>"}` |
| Resposta | `{status, chave, tipo, pdf_base64, xml_base64}` |
| Limite | 60 requisições/minuto (a ferramenta aguarda ~1,2s entre chaves) |
| Erros | `{error, message}` + header `X-Error-Code` |

## Tratamento de erros

- Chave com quantidade incorreta de dígitos ou inválida (dígito verificador);
- Falha de comunicação com a API e timeout (nova tentativa com backoff);
- Rate limit (429) — aguarda o `Retry-After` e tenta novamente;
- DANFE não encontrada (404);
- PDF retornado vazio/corrompido (falha no download);
- Erro de gravação do arquivo (permissão, disco cheio) — registrado no relatório.

## Observações

- A consulta atende apenas NF-e (modelo 55) pela chave; o número da nota é
  extraído do `xml_base64` retornado pela API (fallback: posição 26–34 da chave).
- Se já existir um `NF_<numero>.pdf` na pasta, a ferramenta cria
  `NF_<numero> (1).pdf`, `NF_<numero> (2).pdf` etc., sem sobrescrever.
- O IP da rede onde a ferramenta roda é compartilhado entre os usuários:
  o limite de 60 req/min é por IP, então evite rodar simultaneamente com
  outras ferramentas no mesmo IP.