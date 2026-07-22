# skills — Economia de Tokens

Caixinha de **skills do Claude Code** focadas num único problema: **o contexto é caro e finito**. Toda sessão paga pedágio para reler os arquivos de instrução do projeto (`CLAUDE.md`, memória, handovers). Estas skills atacam esse custo por duas frentes complementares — uma **estanca** o vazamento, a outra **enxuga** o que já acumulou.

> São **agnósticas de domínio**: nasceram num projeto real, mas a mecânica serve qualquer repositório com um arquivo de contexto que cresceu demais ou uma memória que precisa sobreviver ao `/clear`. Os exemplos citados dentro de cada `SKILL.md` são só isso — exemplos.

> ⚠️ **Sobre os percentuais:** os números de economia abaixo são **casos reais observados**, não garantias. O ganho depende do tamanho do seu arquivo e de quanto dele é "sempre-relevante" vs "sob demanda". Trate como ordem de grandeza.

---

## `organizador-mem`

**O que faz.** Pega um arquivo de contexto grande (`CLAUDE.md`, README de arquitetura, índice de memória) e o separa em **núcleo sempre-relevante** + **documentos-satélite sob demanda**, ligados por um *mapa* enxuto. O corte de cada pedaço é decidido por um **subagente que lê e entende a semântica** — não é split cego por regex/heading; quando dois trechos parecem acoplados ou uma seção cabe em dois tópicos, a skill **pergunta antes de aplicar**.

**Por que melhora.** O arquivo monolítico era lido **inteiro, toda sessão**, mesmo quando 90% dele não tinha nada a ver com a tarefa. Depois da quebra, o modelo lê o núcleo curto + o mapa, e só abre o satélite que a tarefa realmente toca. O custo de leitura deixa de ser "o arquivo todo" e passa a ser "núcleo + o que importa agora".

**Economia média.** No caso que originou a skill, um `CLAUDE.md` foi de **~1589 → ~150 linhas de núcleo** (o resto virou 16 docs referenciados): **~90% de redução** no custo fixo de leitura por sessão. Faixa típica esperada: **60–90%** para arquivos onde a maior parte é tópico-específico.

**A intuição.** *Nem toda regra é sempre relevante.* Identidade do projeto e princípios inegociáveis são núcleo (todo turno); a lei de um subsistema só importa quando você mexe naquele subsistema. Pagar pela lei toda hora é desperdício. O mapa preserva a *descoberta* ("existe uma regra sobre X, abra tal doc") sem pagar o *conteúdo* até precisar.

**O que controla em `.claude/`.** A skill vive em `.claude/skills/organizador-mem/SKILL.md`. Ela **reorganiza** o seu `.claude/CLAUDE.md` (ou qualquer arquivo de contexto que você apontar) e cria a pasta de satélites ao lado (ex.: `documentacao/regras/`). Não toca em código do projeto — só na camada de instrução que o Claude carrega.

---

## `handover`

**O que faz.** Prepara a **saída limpa** de uma sessão que inchou com uma tarefa **ainda não concluída**, para um `/clear` sem perder o fio. Escreve **um** documento seletivo em `documentacao/` (só o que git + código + memória **não** contam sozinhos: o *porquê* das decisões, o estado pendente, o próximo passo exato, os riscos), atualiza um breadcrumb terso na memória e declara um **modo de retomada** (`rapida` = próximo passo não toca runtime; `verificada` = próximo passo mexe em runtime e precisa ser reconferido).

**Por que melhora.** A alternativa é carregar a **conversa inteira** para a próxima sessão (caríssimo) ou recomeçar do zero reexplicando tudo (lento e sujeito a erro). O handover destila o estado em **3 camadas de custo diferente** — Resume (morre no `/clear`), Memória-índice (breadcrumb terso, carrega toda sessão), Handover-arquivo (detalhe, aberto só quando alguém o abre). Cada bit de contexto fica na camada mais barata que ainda o entrega a tempo.

**Economia média.** O maior ganho é **estrutural, não pontual**: esta versão traz um **cap de histórico** (mantém no máximo as **2** retomadas anteriores na linha de breadcrumb; o resto delega aos ponteiros duráveis). Isso troca um índice de memória que crescia **O(n)** — uma linha permanente por sessão, inflando indefinidamente — por **O(1)**. No caso real, o índice de memória foi de **96 → 65 linhas (~32%)** só ao aplicar o cap + arquivamento do histórico frio; sem o cap, ele voltaria a inflar em semanas.

**A intuição.** *A memória é o ÍNDICE; aponta, não repete.* A camada que carrega toda sessão tem que ser a mais terse possível — ela só precisa dizer **qual arquivo abrir** e **qual o próximo passo**. Profundidade mora no handover, que só custa tokens quando é aberto. E como "o que era verdade quando escrevi" ≠ "o que é verdade agora", o modo `verificada` obriga a reconferir o runtime antes de afirmar — economia de token nunca vale uma afirmação falsa.

**O que controla em `.claude/`.** A skill vive em `.claude/skills/handover/SKILL.md`. Ela **escreve** o handover em `documentacao/` e **mantém** o seu índice de memória (`MEMORY.md` + `memory/*.md`) enxuto e capado. É a disciplina de *entrada* da memória; o `organizador-mem` é a *faxina* dela.

---

## Por que as duas juntas

`handover` **alimenta** a memória a cada saída de sessão; `organizador-mem` a **reorganiza** quando ela incha. Sem a primeira disciplinada (com o cap de histórico), a segunda vira **enxugar gelo** — cada handover deposita mais uma linha permanente e o índice volta a inflar. Juntas fecham o ciclo: entrada capada + faxina agêntica.

## Como usar

Cada pasta tem um `SKILL.md` autocontido (frontmatter `name` + `description`). Coloque a pasta em um diretório de skills que o seu setup leia — tipicamente `.claude/skills/<nome>/SKILL.md` no projeto, ou o diretório global de skills. O Claude carrega a skill quando a tarefa casa com a `description`, ou quando você a invoca por nome.
