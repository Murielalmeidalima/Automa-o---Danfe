"""main.py — Ponto de entrada do Baixador de DANFE.

Garante que os módulos estejam acessíveis (rodando como script simples
ou via PyInstaller) e inicializa a interface gráfica.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Garante que os módulos do projeto sejam importados quando o arquivo
# é executado diretamente (python main.py) ou empacotado pelo PyInstaller.
sys.path.insert(0, str(Path(__file__).resolve().parent))


def main() -> None:
    import gui

    app = gui.Aplicacao()
    app.mainloop()


if __name__ == "__main__":
    main()