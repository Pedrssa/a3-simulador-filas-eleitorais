# Eventos e incidentes

Todos podem ser disparados manualmente. Desde a revisão, todos os cenários (exceto `starvation`, mantido sem incidentes para a comparação) têm eventos aleatórios ligados por padrão: falha de urna 0,25/h, discussão 0,8/h, boca de urna 0,8/h, grupos 1/h; e, por pessoa, celular 6%, impugnação 2,5%, seção errada 3%, documento 2,5%, biometria 10%, votação demorada 7% (barra lateral → **Disparar incidente**). Os aleatórios têm taxa
configurável (`taxa_*_h`, processo de Poisson) e são **sorteados previamente na carga**, com desfechos
incluídos, para que políticas diferentes recebam exatamente os mesmos eventos.

| Evento | Pré-condições | Participantes | Impacto nos recursos | Duração (min, hipótese) | Resolução | Registros | Efeito visual |
|---|---|---|---|---|---|---|---|
| Chegada de grupo | — | 3–6 eleitores (parte com preferência) | nenhum direto; aumenta a fila | instantâneo | todos entram na fila pela regra vigente | INCIDENTE_INICIO/FIM, ENTRADA_FILA de cada um | fila indiana entra pelo portão |
| Aumento de movimento | — | 12 chegadas em 15 min | carga | 15 | — | ACAO_MANUAL, ENTRADA_FILA | fila cresce |
| Seção errada | pessoa chega à identificação | eleitor, Presidente | ocupa o posto de identificação +1 min | identificação + 1 | orientação: procurar o cartório (art. 130, § 2º) | ENCAMINHADO | balão "Seção certa?" → "Ir ao cartório"; sai |
| Problema de documentação | idem | eleitor, Presidente | idem | identificação + 1 | orientação: voltar com documento aceito (art. 131) | ENCAMINHADO | "Documento?" → "Buscar documento" |
| Falha de biometria | eleitor habilitando | eleitor, 1º mesário | urna reservada por mais tempo | +0,8 a 3 | ano de nascimento (arts. 133 §§ 2º–3º, 135); se persistir → procurar a JE | INICIO_HABILITACAO (justificativa), ENCAMINHADO se irrecuperável | "Biometria..." |
| Auxílio acessível | condição de deficiência ou mobilidade reduzida | eleitor, pessoa de confiança, Presidente (autoriza) | urna por mais tempo | +0,5 a 2 | voto com auxílio (art. 140) | INICIO_VOTACAO com `auxilio=true` | acompanhante "A" entra na cabine |
| Votação demorada | eleitor votando | eleitor | urna ×2 | 2× a votação | conclui normalmente | INICIO_VOTACAO `demorada=true` | "Votando" por mais tempo |
| Falha de urna | urna não interrompida; se ocupada, começa ao fim do voto em curso | Presidente, técnico(a), fiscais | urna INTERROMPIDA; posto de identificação pausado enquanto a Presidente religa (exceto com substituto designado) | religar 1–2,5; técnico chega em 10–25 (3–6 de prontidão); reparo 4–10 | religar resolve, ou urna de contingência (art. 147) | RECURSO_INTERROMPIDO/RESTABELECIDO, INCIDENTE_ETAPA, INCIDENTE_FIM | luz vermelha "INTERROMP."; Presidente vai até a cabine; técnico "TÉC"; "CONTING." |
| Discussão / furar fila | fila com ao menos 2 pessoas | eleitor, secretário, Presidente se escalar, polícia se requisitada | **a chave na heap não muda**; se escalar, posto de identificação pausado | 1,5 (secretário) ou 2–6 (Presidente); polícia chega em 5–15 | ordem restabelecida, registro em ata; polícia verifica e sai | INCIDENTE_INICIO/ETAPA/FIM, RECURSO_INTERROMPIDO | balão "Posso passar?"; Presidente vai até a fila; "POL" na porta |
| Boca de urna: manifestação silenciosa | — | eleitor com adesivo | nenhum | 8–15 | nenhuma providência (permitido) | INCIDENTE_INICIO/FIM | pessoa com "(silêncio)" na área externa |
| Boca de urna: tentativa de influenciar | — | pessoa abordando eleitores, apoio logístico, Presidente (comunicada), 2 agentes | **nenhum**: a urna segue funcionando | comunicação 0,5; polícia 5–15; avaliação 3–8 | orientação e cessação, **ou** encaminhamento à autoridade competente; **sem declarar culpa** | INCIDENTE_INICIO/ETAPA/FIM | balão "Vote em…?"; "APOIO: Observando"; "POL" na área externa |
| Recusa do celular | eleitor chega à cabine com o aparelho | eleitor, Presidente, polícia (se necessário) | urna liberada sem voto | orientação 0,5–1,5 | guarda o celular e vota, **ou** recusa → não autorizado(a) a votar (art. 137, § 5º); polícia vem à porta em parte dos casos | INCIDENTE_ETAPA, ENCAMINHADO, INCIDENTE_FIM | eleitor de costas com o celular erguido; viatura e agentes na porta |
| Impugnação de identidade | eleitor em identificação | fiscal, Presidente, Juízo (se persistir) | posto de identificação ocupado por mais tempo | +2–5; +6–14 se persistir | dúvida sanada ou Juízo confirma (art. 132) | INCIDENTE_INICIO/FIM | fiscal de braço erguido: "Impugno!" |
| Encerramento (17h) | — | secretário/mesários | fila congelada; novas chegadas recusadas | instantâneo | senhas do último ao primeiro; chamada em ordem decrescente (art. 160) | ENCERRAMENTO (lista de senhas), CHEGADA_NAO_ADMITIDA | placa "ENCERRADO"; "#n" sobre cada pessoa |

Garantias verificadas por teste (`test_incidentes_manuais_nao_quebram_invariantes`,
`test_invariantes_e_ninguem_duplicado`):

- ninguém fica duas vezes na urna;
- nenhum recurso é liberado duas vezes;
- nenhum personagem é duplicado;
- todas as pessoas terminam num estado final;
- nenhuma prisão é decidida por aparência ou roupa (a palavra "prisão" não aparece em nenhum registro);
- um incidente externo nunca interrompe a urna.
