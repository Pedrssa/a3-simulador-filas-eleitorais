# A3 — Programação de Soluções Computacionais

## SEÇÃO 8-BIT — Simulador de Filas Eleitorais

Simulador acadêmico de **filas de prioridade** ambientado numa seção eleitoral brasileira, com animação
pixel art, exibição do código efetivamente executado, eventos aleatórios, auditoria SQL e comparação de
estratégias contra **starvation**. Trabalho da avaliação A3 de Programação de Soluções Computacionais.

> **Simulação acadêmica sem vínculo oficial com a Justiça Eleitoral.** Personagens e dados fictícios.
> Nenhum CPF, título, biometria ou voto é coletado; nenhuma escolha de voto é modelada ou registrada.

## Requisitos

- Python 3.12 ou mais recente (desenvolvido e testado com 3.14.3 no Windows 11)
- Navegador moderno (Chrome, Edge ou Firefox)

## Instalação e execução

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

pip install -r requirements.txt        # versões diretas fixadas
# ou, para reproduzir exatamente o ambiente testado:
pip install -r requirements-lock.txt

streamlit run app.py                    # abre em http://localhost:8501
python -m pytest -q                     # roda a suíte de testes
python scripts/gerar_exemplos.py        # regenera sql/logs.sql e imprime a comparação de políticas
```

O banco de auditoria da interface fica em `dados/auditoria.sqlite3` (criado automaticamente).

## Como usar (roteiro curto)

1. Na barra lateral, escolha o **cenário** (`demo_7min` é o roteiro da apresentação), a **seed** e a **política**, e clique em **Reiniciar com estas opções**.
2. Use **▶ Iniciar / ⏸ Pausar**, **⏭ Avançar 1 evento** e o controle de **velocidade**. A velocidade muda só o ritmo da tela: para a mesma seed e configuração, os resultados são os mesmos.
3. Insira eleitores, gere chegadas ou dispare incidentes em **Interações**.
4. Ative o **Modo apresentação** para ver a cena e o último passo do algoritmo lado a lado.

| Aba | Conteúdo |
|---|---|
| A. Simulação 8 bits | cena animada, detalhes da pessoa selecionada, tabela acessível de quem está onde |
| B. Código em execução | evento → método → linha real → antes/depois → efeito na cena |
| C. Filas e algoritmo | array interno da heap, ordem efetiva, árvore, agenda de eventos, complexidades |
| D. Métricas e SLA | esperas por grupo (incluindo quem ainda espera), SLA, starvation, comparação de políticas |
| E. Auditoria SQL | consulta parametrizada, verificação do hash, exportação e validação de `logs.sql` |
| F. Regras e documentação | matriz de regras eleitorais e documentos do projeto |

## Estrutura

```
app.py                      ponto de entrada Streamlit (fino)
secao8bit/domain/           Eleitor, PerfilPrioridade, FilaPrioridade (heap), políticas, recursos, seção
secao8bit/application/      MotorSimulacao, carga reproduzível, agenda/relógio, métricas, rastreamento, cena
secao8bit/infrastructure/   RepositorioAuditoria (SQLite), exportador de logs.sql
secao8bit/ui/               sessão compartilhada, abas, componente da cena
assets/cena8bit/            Canvas + JavaScript (só apresentação)
sql/schema.sql, sql/logs.sql
tests/                      pytest (domínio, motor, auditoria, coerência, interface)
docs/                       relatório, regras, UML, dicionário, requisitos, testes, roteiro
```

## Documentação

- [Relatório técnico](docs/relatorio_tecnico.md)
- [Regras eleitorais e rastreabilidade](docs/regras_eleitorais.md)
- [Matriz de requisitos do enunciado](docs/matriz_requisitos.md)
- [Eventos e incidentes](docs/eventos.md)
- [UML e dicionário de classes](docs/dicionario_e_uml.md)
- [Testes e evidências](docs/testes.md)
- [Roteiro da apresentação (20 min)](docs/roteiro_apresentacao.md)
- [Ferramentas usadas no desenvolvimento](docs/ferramentas.md)

## Versionamento

O repositório git já está inicializado (branch `main`), **sem nenhum commit**. O enunciado pede um histórico
distribuído entre os integrantes. Por isso, cada pessoa deve commitar a área que estudou e consegue explicar
na arguição (a divisão sugerida está em `docs/roteiro_apresentacao.md`). Exemplo:

```bash
git add secao8bit/domain/prioridade.py tests/test_prioridade.py docs/regras_eleitorais.md
git commit -m "Classificação de prioridade conforme art. 129 da Res. 23.751/2026"

git pull origin main   # o repositório já está no GitHub
git push origin main
```

`.venv/`, `dados/` (banco local) e `exports/` ficam fora do controle de versão (`.gitignore`).
