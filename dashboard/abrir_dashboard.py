#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
abrir_dashboard.py — abre o painel O(1)mem JÁ PREENCHIDO, sem upload manual.

Por que existe: uma página file:// no navegador NÃO lê arquivo local sozinha
(segurança do browser). Então este launcher faz o trabalho: acha os logs de nudge
automaticamente, injeta os dados no HTML como `window.__O1MEM_DATA__`, escreve um
HTML temporário e abre no navegador — já com KPIs e gráfico na tela.

USO:  python abrir_dashboard.py
      (sem argumentos; acha os logs sozinho)

Logs lidos (o que existir):
  ~/.claude/handover-nudge.log                     (Claude Code)
  ~/AppData/Local/hermes/handover-nudge.log        (Hermes)
"""
import os, sys, json, tempfile, webbrowser

HERE = os.path.dirname(os.path.abspath(__file__))
INDEX = os.path.join(HERE, "index.html")

LOGS = [
    os.path.expanduser("~/.claude/handover-nudge.log"),
    os.path.expanduser("~/AppData/Local/hermes/handover-nudge.log"),
]


def read_jsonl(path):
    """Lê um .log JSONL; ignora linhas inválidas. Retorna lista de dicts."""
    out = []
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    out.append(json.loads(line))
                except Exception:
                    pass
    except Exception:
        pass
    return out


def main():
    if not os.path.exists(INDEX):
        print(f"ERRO: index.html nao encontrado em {INDEX}")
        return 1

    records, achados = [], []
    for p in LOGS:
        if os.path.exists(p):
            r = read_jsonl(p)
            records += r
            achados.append(f"{len(r):>4} eventos  {p}")

    html = open(INDEX, "r", encoding="utf-8").read()
    # injeta os dados ANTES da tag <script> principal (o global precisa existir
    # quando o gancho de auto-carga rodar, no fim do script).
    payload = json.dumps(records, ensure_ascii=False)
    inject = f"<script>window.__O1MEM_DATA__ = {payload};</script>\n<script>"
    if records and "<script>" in html:
        html = html.replace("<script>", inject, 1)

    out = os.path.join(tempfile.gettempdir(), "o1mem_dashboard.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)

    if achados:
        print("Logs encontrados:")
        for a in achados:
            print("  " + a)
        print(f"Total: {len(records)} eventos embutidos.")
    else:
        print("Nenhum log de nudge encontrado — abrindo vazio (modo upload).")
        print("  (procurei em: " + " ; ".join(LOGS) + ")")

    print(f"Abrindo: {out}")
    webbrowser.open("file:///" + out.replace("\\", "/"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
