---
name: handover
description: Prepara a saída LIMPA de uma sessão que inchou com uma TAREFA AINDA NÃO CONCLUÍDA, para um /clear sem perder o fio. Escreve UM documento enxuto e SELETIVO em documentacao/ (só o que git+código+memória NÃO contam - porquê das decisões, estado pendente, próximo passo exato, riscos), atualiza o breadcrumb na memória (linha RETOMADA + 1 project_*) e libera o /clear. O handover declara seu MODO DE RETOMADA - "rapida" (próximo passo não toca runtime - decisão, edição, análise; a retomada confia no escrito e fecha com "PRONTO E OPERANTE THIAGO!") ou "verificada" (próximo passo MEXE NO RUNTIME - gate contra backend de pé, deploy de diff, env flag, store/processo; o handover inclui "Caveat de estado vivo" e a retomada REVERIFICA o runtime ANTES de afirmar ou agir, porque a memória diz o que era verdade quando foi escrita, não o estado presente). Use para qualquer saída de sessão inacabada. NÃO use se a tarefa está concluída e verificada (aí basta memória).
---

Você vai preparar a **saída limpa** de uma sessão: destilar o estado de uma tarefa inacabada em artefatos duráveis para que uma sessão NOVA retome sem reexplicação. Esta skill tem **um fluxo com dois modos de retomada** — a decisão do modo é interna (Passo 0.5) e fica **gravada no próprio handover**, não na sua memória.

## Princípio central: as 3 camadas têm funções diferentes

| Camada | Carrega quando? | Função |
|---|---|---|
| **Resume** | usuário retoma *esta* conversa | continua tudo — mas morre no `/clear` |
| **Memória** (`MEMORY.md` + `memory/*.md`) | **toda** sessão nova, automático | breadcrumb: fatos duráveis + "onde estamos + próximo passo + `[[link]]`" |
| **Handover** (`documentacao/HANDOVER_*.md`) | só quando alguém o **abre** | arquivo: detalhe profundo que não cabe na memória — inclusive o MODO de retomada |

> **A memória é o ÍNDICE; o handover é o ARQUIVO.** A memória garante que a próxima sessão saiba qual handover abrir. Detalhe mora só no handover. Nunca duplique.

## Segundo princípio: nunca afirme runtime pela memória

O handover diz o que era verdade **quando foi escrito**. O processo pode ter sido morto, reiniciado com código velho, o env pode ter mudado. `feedback_verificar_codigo_antes_de_afirmar` e `feedback_teste_atesta_erro_nao_passa` valem aqui. Por isso existe o modo `verificada` — e por isso a promoção de modo na retomada (Passo 4) é sempre permitida, nunca o rebaixamento.

## Passo 0 — TRAVA DE VALOR (não pule)

Handover **só vale a pena** se a tarefa tem pelo menos UM de:
1. **estado pendente que importa** (algo meio-feito, plano não executado);
2. **raciocínio caro de reconstruir** (investigação, hipóteses, trade-off decidido);
3. **plano de vários passos ainda não executado**.

Se a tarefa está **concluída e verificada** e o fato durável cabe na memória → **NÃO escreva handover**. Grave só a memória e diga que basta.

## Passo 0.5 — DECIDA O MODO DE RETOMADA

Pergunte: **o próximo passo da retomada toca o runtime?**

- **NÃO toca** (decisão, edição de código/doc, análise, escrita — algo que a próxima sessão faz "do zero"): modo **`rapida`**. A retomada confia no escrito e não verifica nada.
- **TOCA** (rodar gate contra backend de pé, deployar um diff, conferir env flag, estado de store/cache/processo): modo **`verificada`**. O handover DEVE incluir a seção "Caveat de estado vivo" e a retomada a EXECUTA.

**Na dúvida → `verificada`.** Verificar a mais nunca quebrou nada; confiar cego já quebrou.

O modo escolhido vai na **primeira linha do handover** (ver template). É o artefato que carrega o protocolo — a retomada não depende de lembrar qual decisão foi tomada.

## Passo 1 — Escreva o handover (SELETIVO, não dump)

Arquivo: `documentacao/HANDOVER_<slug-da-tarefa>_<YYYYMMDD>.md`.

**Regra de ouro:** só entra o que **git + código + memória NÃO contam sozinhos**.
- ❌ NÃO liste "arquivos/funções tocados" como corpo — `git diff` já mostra. Aponte `arquivo:linha` só para achar rápido.
- ❌ NÃO cole blocos de código — aponte a localização.
- ✅ Entra o **porquê**, a **decisão + alternativa descartada**, o **que falta**, o **próximo passo exato**, os **riscos/colaterais**.

Template:
```markdown
# HANDOVER — <tarefa> (<data>)
> retomada: rapida | verificada

## Onde paramos
1 parágrafo. O estado atual em linguagem de quem vai retomar.

## Próximo passo EXATO
A PRIMEIRA ação concreta da retomada (comando, arquivo, decisão). Sem ambiguidade.

## Decisões + porquê
As escolhas feitas e a RAZÃO (não o quê — o porquê). Inclua a alternativa descartada e por quê.

## Estado pendente
O que falta, com o critério de "pronto". No modo verificada: gates não rodados, deploy não aplicado, validação ao vivo faltando.

## Riscos / colaterais em backlog
Problemas conhecidos NÃO resolvidos (separados da tarefa principal). Severidade.

## Caveat de estado vivo (SÓ no modo verificada — REVERIFICAR antes de afirmar)
O que a retomada PRECISA conferir no runtime antes de agir: backend de pé? qual PID/porta? o patch está no processo rodando (mtime do arquivo vs. start do processo)? env flags no estado esperado? git diff bate? store/cache limpo? Liste itens concretos e checáveis — a retomada vai EXECUTAR isto.

## Refs — arquivo:linha
Pontos de entrada para achar rápido. NÃO é o diff.
```

> **Coerência modo × caveat:** no modo `verificada`, o "Caveat de estado vivo" é **obrigatório** — se você não consegue listar nada checável, o caso é `rapida`. No modo `rapida`, a seção é **omitida** — se você sentiu necessidade de escrevê-la, o caso é `verificada`. A presença/ausência da seção deve sempre bater com a linha `retomada:`.

## Passo 2 — Breadcrumb na memória (o índice)

1. **Atualize a linha `RETOMADA`** no topo do `MEMORY.md`: estado atual + próximo passo + `[[link-da-memoria]]`. Ao promover a atual para o histórico entre parênteses, **DROPE a mais antiga — mantenha no máximo 2 linhas `(Anterior ...)`**. O histórico completo já vive nos `project_*` listados abaixo (cada linha "Anterior" termina em `Ver [project_*]`, que persiste); a linha `RETOMADA` guarda só o pulo atual + os 2 imediatamente anteriores como ponte, nunca a cadeia inteira. Deixar acumular re-cria o monólito que a memória existe para evitar.
2. **Crie/atualize 1 arquivo `project_*`** em `memory/` com o fato durável (decisão + estado + próximo label livre), apontando para o handover e linkando `[[nome]]`.
3. Ajuste a linha-índice no `MEMORY.md`.

O breadcrumb é TERSO — aponta, não repete. O modo NÃO precisa ir no breadcrumb: ele está na primeira linha do handover.

## Passo 3 — Libere o /clear

- Diga ao usuário, explicitamente, que está **seguro dar `/clear`** e o que foi gravado (handover + memória + modo de retomada).
- Lembre que **você não executa `/clear`** — é ação do usuário.
- Em uma frase, diga qual será a **primeira ação da retomada**.

## Passo 4 — (na retomada, sessão nova) O MODO ESTÁ NO ARQUIVO

Quando voltar (usuário pede "retomar", "voltar para o handover"):

1. Leia a linha `RETOMADA` do `MEMORY.md` e abra o `documentacao/HANDOVER_*.md` indicado (ou o mais recente).
2. Leia o handover inteiro e **cheque a linha `retomada:`** na primeira linha.
3. **REGRA DE PROMOÇÃO (vale sempre, antes de seguir o modo escrito):** se o próximo passo — como está escrito OU como evoluiu desde a escrita — envolve agir sobre runtime, trate como `verificada` **mesmo que o arquivo diga `rapida`**. Promoção é sempre permitida; rebaixamento nunca (se o arquivo diz `verificada`, a retomada verifica, ponto).

**Se `rapida` (e a promoção não se aplica):**
- Devolva o fio conciso: onde paramos + próximo passo exato + pendências.
- **NÃO valide estado vivo** — nada de `netstat`, `git diff`, env, restart, gate.
- Feche, **literalmente**, com:

> PRONTO E OPERANTE THIAGO!

**Se `verificada` (ou promovida):**
- Leia com atenção o "Caveat de estado vivo" e as "Refs — arquivo:linha".
- **EXECUTE o caveat** — reverifique cada item no runtime: backend de pé? porta/PID? o código rodando TEM o patch (mtime vs. start do processo, ou force restart)? env flags certas? `git diff --stat` bate? store/cache no estado assumido?
- **Reporte o estado verificado** com sinais claros (✅ / ⚠️ / ❌) — o que você ENCONTROU, não o que o handover afirmava. Destaque **divergências** ANTES de propor agir.
- Se há divergência que afeta a integridade (ex.: backend sem o patch antes de um gate), **proponha corrigir primeiro** (restart, setar env, aplicar diff) em vez de seguir cego.
- Só então feche com:

> PRONTO E OPERANTE THIAGO!

## O que esta skill NÃO é

- Não é dump de conversa — é destilação seletiva.
- Não executa `/clear` nem apaga contexto.
- Não substitui a memória — trabalha com ela (índice + arquivo).
- Não roda para tarefa concluída/verificada — aí é só memória.
- Não confia na memória para afirmar runtime — no modo `verificada` (ou promovido), sempre reverifica.
