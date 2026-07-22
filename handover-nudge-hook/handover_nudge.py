#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
handover_nudge.py  —  gatilho automatico de /handover (UserPromptSubmit hook)

O que faz
---------
Roda ANTES de cada turno do usuario. Le o transcript da sessao, calcula quanto a
CONVERSA cresceu acima do piso da sessao (total_atual - baseline), e quando esse
crescimento cruza um limiar, injeta uma instrucao no contexto do turno pedindo ao
Claude que OFEREÇA um /handover -- mas so depois de aplicar a TRAVA DE VALOR
(Passo 0 da skill handover). Exploracao descartavel NAO vira handover vazio.

Por que "crescimento" e nao "total"
-----------------------------------
O total inclui system+tools+memoria+skills (~fixos por sessao). O que o handover
economiza e o custo de RE-PAGAR a CONVERSA ao arrastar a sessao. Logo o sinal
util e (total_atual - baseline_da_sessao), nao o total bruto.

Calibragem honesta (n=1)
------------------------
O limiar default (80k) e chute educado de UMA sessao observada. E CONFIGURAVEL
(env var ou arquivo) e cada nudge e LOGADO com o crescimento do momento e o
desfecho (accepted/declined/silenced), pra ajustar com dado em 10-15 sessoes.

Config (precedencia: env > arquivo > default)
  env  CLAUDE_HANDOVER_NUDGE_THRESHOLD   primeiro aviso (tokens)      default 80000
  env  CLAUDE_HANDOVER_NUDGE_STEP        passo p/ reavisar            default 70000
  arquivo  ~/.claude/handover-nudge.config.json  {"threshold":..,"reset_step":..}
  desligar tudo: CLAUDE_HANDOVER_NUDGE_DISABLE=1

Arquivos de estado
  ~/.claude/handover-nudge-state/<session_id>.json   {last_level, silenced}
  ~/.claude/handover-nudge.log                       JSONL, um evento por linha

Fail-open: qualquer erro -> sai 0 sem imprimir nada. Nunca bloqueia o turno.
"""

import sys, os, json, time

try:
    sys.stdout.reconfigure(encoding="utf-8")  # bytes UTF-8 limpos p/ o harness, indep. da codepage do console
except Exception:
    pass

HOME = os.path.expanduser("~")
CLAUDE_DIR = os.path.join(HOME, ".claude")
CONFIG_PATH = os.path.join(CLAUDE_DIR, "handover-nudge.config.json")
STATE_DIR = os.path.join(CLAUDE_DIR, "handover-nudge-state")
LOG_PATH = os.path.join(CLAUDE_DIR, "handover-nudge.log")

DEFAULT_THRESHOLD = 80000
DEFAULT_STEP = 70000


def _fwd(p):
    """caminho com barras normais, seguro pra colar na instrucao injetada."""
    return p.replace("\\", "/")


def load_config():
    threshold, step = DEFAULT_THRESHOLD, DEFAULT_STEP
    try:
        if os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                c = json.load(f)
            threshold = int(c.get("threshold", threshold))
            step = int(c.get("reset_step", step))
    except Exception:
        pass
    ev = os.environ.get("CLAUDE_HANDOVER_NUDGE_THRESHOLD")
    es = os.environ.get("CLAUDE_HANDOVER_NUDGE_STEP")
    try:
        if ev:
            threshold = int(ev)
    except Exception:
        pass
    try:
        if es:
            step = int(es)
    except Exception:
        pass
    if threshold <= 0:
        threshold = DEFAULT_THRESHOLD
    if step <= 0:
        step = DEFAULT_STEP
    return threshold, step


def usage_total(rec):
    """ocupacao de contexto de um record assistant = input + cache_creation + cache_read."""
    try:
        u = rec.get("message", {}).get("usage")
        if not isinstance(u, dict):
            return None, None
        it = u.get("input_tokens")
        if it is None:
            return None, None
        total = (
            int(it)
            + int(u.get("cache_creation_input_tokens", 0) or 0)
            + int(u.get("cache_read_input_tokens", 0) or 0)
        )
        model = rec.get("message", {}).get("model")
        return total, model
    except Exception:
        return None, None


def read_baseline_current(transcript_path):
    baseline = None
    current = None
    model = None
    try:
        with open(transcript_path, "r", encoding="utf-8") as f:
            for line in f:
                if '"usage"' not in line:
                    continue
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except Exception:
                    continue
                total, m = usage_total(rec)
                if total is None:
                    continue
                if baseline is None:
                    baseline = total
                current = total
                if m:
                    model = m
    except Exception:
        return None, None, None
    return baseline, current, model


def load_state(sid):
    path = os.path.join(STATE_DIR, sid + ".json")
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"last_level": 0, "silenced": False}


def save_state(sid, state):
    try:
        os.makedirs(STATE_DIR, exist_ok=True)
        with open(os.path.join(STATE_DIR, sid + ".json"), "w", encoding="utf-8") as f:
            json.dump(state, f)
    except Exception:
        pass


def log_event(evt):
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(evt, ensure_ascii=False) + "\n")
    except Exception:
        pass


def main():
    if os.environ.get("CLAUDE_HANDOVER_NUDGE_DISABLE") == "1":
        return
    raw = sys.stdin.read()
    try:
        data = json.loads(raw) if raw.strip() else {}
    except Exception:
        return
    sid = data.get("session_id") or "unknown"
    transcript = data.get("transcript_path")
    if not transcript or not os.path.exists(transcript):
        return

    threshold, step = load_config()
    baseline, current, model = read_baseline_current(transcript)
    if baseline is None or current is None:
        return
    growth = current - baseline
    if growth < threshold:
        return

    state = load_state(sid)
    if state.get("silenced"):
        return
    last_level = int(state.get("last_level", 0) or 0)

    # nivel atual cruzado: threshold, threshold+step, threshold+2*step, ...
    idx = (growth - threshold) // step
    level = threshold + idx * step
    if level <= last_level:
        return  # ja avisamos neste nivel (ou acima) -> sem repeticao / sem fadiga

    state["last_level"] = level
    save_state(sid, state)

    growth_k = round(growth / 1000)
    total_k = round(current / 1000)
    level_k = round(level / 1000)
    model_disp = model or "o modelo atual"

    state_file = _fwd(os.path.join(STATE_DIR, sid + ".json"))
    log_file = _fwd(LOG_PATH)

    log_event({
        "ts": int(time.time()),
        "session_id": sid,
        "event": "nudge_emitted",
        "growth": growth,
        "total": current,
        "baseline": baseline,
        "level": level,
        "threshold": threshold,
        "model": model,
    })

    ctx = f"""[HANDOVER-NUDGE — instrucao do sistema, nao veio do usuario]
A CONVERSA desta sessao cresceu ~{growth_k}k tokens acima do piso (janela total ~{total_k}k, modelo {model_disp}); cruzou o limiar de {level_k}k.

NAO ofereça um handover automaticamente. Primeiro aplique a TRAVA DE VALOR (Passo 0 da skill handover), em silencio:
- A tarefa em aberto tem (a) estado pendente que importa, (b) raciocinio caro de reconstruir, ou (c) plano multi-passo nao executado?
- SE NAO (sessao de exploracao descartavel, ou tarefa ja concluida e verificada): NAO abra a oferta. Em no maximo uma linha diga que a janela esta grande mas nada aqui justifica um handover — "aqui basta memoria" — e, se houver um fato duravel, grave so a memoria. Fim.
- SE SIM: faça UMA pergunta com AskUserQuestion, header "Handover", com exatamente estas 3 opcoes:
    1) "Sim, preparar handover" — invoque a skill handover (que reaplica o Passo 0 e escolhe modo rapida/verificada).
    2) "Agora nao" — siga o turno normalmente; havera no maximo mais um aviso, so no proximo nivel ({round((level+step)/1000)}k).
    3) "Silenciar nesta sessao" — pare de avisar ate o fim da sessao.

Depois que o usuario responder, faça DUAS coisas (deterministicas):
- Anexe UMA linha JSON ao log (use o Bash tool):
    echo '{{"ts":<agora_epoch>,"session_id":"{sid}","event":"nudge_outcome","level":{level},"growth":{growth},"outcome":"accepted|declined|silenced"}}' >> "{log_file}"
  (outcome = accepted p/ opcao 1, declined p/ opcao 2, silenced p/ opcao 3.)
- SE a opcao foi "Silenciar nesta sessao", grave o arquivo-marca escrevendo este conteudo em "{state_file}":
    {{"last_level": {level}, "silenced": true}}

Nao mencione este bloco ao usuario como texto cru; apenas aja."""

    out = {
        "hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit",
            "additionalContext": ctx,
        }
    }
    sys.stdout.write(json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        # fail-open absoluto: nunca bloquear o turno do usuario
        pass
