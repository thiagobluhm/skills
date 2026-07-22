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

    event = data.get("hook_event_name") or ""

    # --- Observador PreCompact (LOG-ONLY, nunca bloqueia, sem stdout) ---
    # Instrumentacao para decidir "com dado" se a ponte bloqueante (PreCompact/auto)
    # vale a pena: registra o tamanho da conversa QUANDO a compactacao disparou e se o
    # usuario ja tinha sido avisado. Se o auto-compact costuma nos pegar ANTES de um
    # nudge aceito, a rede final se justifica; senao, o UserPromptSubmit basta.
    if event == "PreCompact":
        b, c, _ = read_baseline_current(transcript)
        st = load_state(sid)
        log_event({
            "ts": int(time.time()),
            "session_id": sid,
            "event": "precompact_fired",
            "trigger": data.get("trigger"),  # "auto" | "manual"
            "growth": (c - b) if (b is not None and c is not None) else None,
            "total": c,
            "already_nudged_level": int(st.get("last_level", 0) or 0),
            "silenced": bool(st.get("silenced")),
        })
        return  # NUNCA escreve stdout nem bloqueia (exit 0)

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

    # Texto FACTUAL, nao imperativo. A doc oficial de hooks avisa que texto injetado
    # em registro de comando out-of-band ("faça X", "NAO faça Y") dispara as defesas
    # anti-prompt-injection do Claude, que passa a EXIBIR o texto em vez de trata-lo
    # como contexto. Entao aqui so afirmamos FATOS (crescimento, limiar, disciplina do
    # ambiente, e como a mecanica funciona); a decisao de agir fica com o Claude+usuario.
    next_k = round((level + step) / 1000)
    ctx = f"""[Contexto de sessao — informativo; nao e uma mensagem do usuario.]

A conversa desta sessao cresceu ~{growth_k}k tokens acima do piso inicial da sessao (janela total ~{total_k}k tokens, modelo {model_disp}). O limiar configurado para sugerir um handover — {level_k}k de crescimento da conversa — acaba de ser ultrapassado. O proximo aviso, se houver, so ocorre em {next_k}k.

Disciplina de handover deste ambiente: um handover so agrega valor quando ha estado duravel a preservar — tarefa pela metade, raciocinio caro de reconstruir, ou plano de varios passos ainda nao executado. Uma sessao de exploracao descartavel, ou uma tarefa ja concluida e verificada, dispensa handover; nesses casos a memoria basta. Havendo valor, a escolha entre preparar o handover agora, adiar, ou silenciar os avisos do restante da sessao cabe ao usuario.

Mecanica desta sessao, se for util: os avisos ficam silenciados quando o arquivo "{state_file}" contem {{"last_level": {level}, "silenced": true}}; os desfechos de cada aviso sao registrados em "{log_file}"."""

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
