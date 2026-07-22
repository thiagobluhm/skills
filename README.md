# skills — Economia de Tokens

Se você usa Claude Code todo dia, você já sentiu isso: a sessão incha, o `CLAUDE.md` vira um monstro que o modelo relê inteiro toda vez, e dar `/clear` significa perder o fio de uma tarefa pela metade. Eu vivi exatamente esse ciclo — e essas duas skills nasceram dele.

O problema, no fundo, é um só: **contexto é caro e finito, e toda sessão paga pedágio** para reler os arquivos de instrução do projeto (`CLAUDE.md`, memória, handovers). Essas skills atacam esse custo por duas frentes que se completam — uma **estanca** o vazamento, a outra **enxuga** o que já acumulou.

Duas coisas antes de você seguir:

> Elas são **agnósticas de domínio**. Nasceram num projeto real meu, mas a mecânica serve qualquer repositório com um arquivo de contexto que cresceu demais ou uma memória que precisa sobreviver ao `/clear`. Os exemplos dentro de cada `SKILL.md` são só isso — exemplos.

> ⚠️ **Sobre os percentuais:** os números de economia abaixo são **casos reais que eu observei**, não promessa. O ganho depende do tamanho do seu arquivo e de quanto dele é "sempre-relevante" versus "sob demanda". Trate como ordem de grandeza, não como garantia.

---

## `organizador-mem`

**A dor.** Meu `CLAUDE.md` tinha mais de 1500 linhas. Toda sessão lia tudo — mesmo quando 90% daquilo não tinha nada a ver com a tarefa do dia. Eu estava pagando, a cada turno, por regras de subsistemas que eu nem ia tocar.

**O que ela faz.** Pega esse arquivo de contexto grande (`CLAUDE.md`, README de arquitetura, índice de memória) e separa em **núcleo sempre-relevante** + **documentos-satélite sob demanda**, ligados por um *mapa* enxuto. E aqui está o detalhe que importa: o corte de cada pedaço é decidido por um **agente que lê e entende a semântica** — não é split cego por regex ou heading. Quando dois trechos parecem acoplados, ou uma seção cabe em dois tópicos, a skill **para e pergunta** antes de aplicar. Aprendi da pior forma que split mecânico fragmenta raciocínio ao meio.

**Por que melhora.** Depois da quebra, o modelo lê o núcleo curto + o mapa, e só abre o satélite que a tarefa realmente toca. O custo de leitura deixa de ser "o arquivo todo" e vira "núcleo + o que importa agora".

**Quanto rendeu.** No caso que originou a skill, o `CLAUDE.md` foi de **~1589 para ~150 linhas de núcleo** — o resto virou 16 docs referenciados. **~90% de redução** no custo fixo de leitura por sessão. Faixa típica que eu esperaria: **60–90%**, quando a maior parte do arquivo é tópico-específica.

**A intuição, se você só levar uma frase:** *nem toda regra é sempre relevante.* Identidade do projeto e princípios inegociáveis são núcleo — todo turno. A lei de um subsistema só importa quando você mexe naquele subsistema. Pagar pela lei toda hora é desperdício. O mapa preserva a *descoberta* ("existe uma regra sobre X, abra tal doc") sem pagar o *conteúdo* até precisar.

**O que ela controla em `.claude/`.** A skill vive em `.claude/skills/organizador-mem/SKILL.md`. Ela **reorganiza** o seu `.claude/CLAUDE.md` (ou qualquer arquivo de contexto que você apontar) e cria a pasta de satélites ao lado (ex.: `documentacao/regras/`). Não toca em código do projeto — só na camada de instrução que o Claude carrega.

---

## `handover`

**A dor.** Sessão inchou, tarefa pela metade, e você fica no dilema: carregar a conversa inteira pra frente (caríssimo) ou dar `/clear` e recomeçar reexplicando tudo (lento, e você SEMPRE esquece um porquê importante no caminho).

**O que ela faz.** Prepara a **saída limpa** da sessão. Escreve **um** documento seletivo em `documentacao/` — e seletivo aqui é regra, não adjetivo: só entra o que git + código + memória **não** contam sozinhos. O *porquê* das decisões (com a alternativa descartada), o estado pendente, o próximo passo exato, os riscos. Atualiza um breadcrumb enxuto na memória e declara um **modo de retomada**: `rapida` quando o próximo passo não toca runtime, `verificada` quando toca — e aí a sessão nova é obrigada a reconferir o estado vivo antes de afirmar qualquer coisa.

**Por que melhora.** O handover distribui o estado em **3 camadas de custo diferente** — o Resume (morre no `/clear`), a Memória-índice (breadcrumb curto, carrega toda sessão), e o Handover-arquivo (detalhe profundo, só custa quando alguém o abre). Cada informação fica na camada mais barata que ainda a entrega a tempo.

**Quanto rendeu.** O maior ganho aqui é **estrutural, não pontual** — e foi um bug meu que me ensinou isso. A primeira versão preservava o histórico de retomadas para sempre: cada handover depositava uma linha permanente no índice, que crescia **O(n)** sem ninguém perceber. Esta versão traz um **cap de histórico** (no máximo as **2** retomadas anteriores; o resto delega aos ponteiros duráveis), transformando o crescimento em **O(1)**. No meu caso real, o índice foi de **96 para 65 linhas (~32%)** só aplicando o cap + arquivamento do histórico frio. Sem o cap, ele voltaria a inflar em semanas — e eu só descobri isso olhando o painel de context usage e me perguntando por que a memória pesava tanto.

**A intuição, se você só levar uma frase:** *a memória é o ÍNDICE — aponta, não repete.* A camada que carrega toda sessão tem que ser a mais enxuta possível: ela só precisa dizer **qual arquivo abrir** e **qual o próximo passo**. Profundidade mora no handover, que só custa quando é aberto. E como "o que era verdade quando escrevi" ≠ "o que é verdade agora", o modo `verificada` existe para uma coisa: economia de token **nunca** vale uma afirmação falsa sobre o runtime.

**O que ela controla em `.claude/`.** A skill vive em `.claude/skills/handover/SKILL.md`. Ela **escreve** o handover em `documentacao/` e **mantém** o seu índice de memória (`MEMORY.md` + `memory/*.md`) enxuto e capado. É a disciplina de *entrada* da memória; o `organizador-mem` é a *faxina*.

---

## Por que as duas juntas

Aqui está a parte que eu demorei a enxergar: `handover` **alimenta** a memória a cada saída de sessão; `organizador-mem` a **reorganiza** quando ela incha. Sem a primeira disciplinada (com o cap de histórico), a segunda vira **enxugar gelo** — cada handover deposita mais uma linha e o índice que você acabou de emagrecer engorda de novo. Juntas, fecham o ciclo: entrada capada + faxina agêntica.

## Como usar

Cada pasta tem um `SKILL.md` autocontido (frontmatter `name` + `description`). Coloque a pasta em um diretório de skills que o seu setup leia — tipicamente `.claude/skills/<nome>/SKILL.md` no projeto, ou o diretório global. O Claude carrega a skill quando a tarefa casa com a `description`, ou quando você a chama pelo nome.

Se testar num projeto seu e os números baterem (ou não baterem), me conta — os percentuais daqui só valem o que valem porque vieram de caso real, e mais casos reais só melhoram a calibragem.
