# Evidências: de onde vem cada número e cada afirmação do README

Tudo abaixo vem de execuções reais feitas em 12/10/2026 (conversas e avaliação) ou do código do repositório. Os dados de loja, pedidos e rótulos são **fictícios**; os rótulos foram escritos com apoio de LLM e **não foram revisados por humanos**.

## Números

| Afirmação no README | Valor | Arquivo que comprova | Como foi gerado |
|---|---|---|---|
| Acurácia top-1 (76 turnos) | MSD1 98,7% · Jev 96,1% · LLM 98,7% | [`evidencias/avaliacao/resumo.json`](evidencias/avaliacao/resumo.json) | `python scripts/avaliar.py`; log em [`terminal_avaliacao.txt`](evidencias/terminal_avaliacao.txt) |
| 100% nos turnos não ambíguos | os 3 provedores | idem (`acuracia_top1_nao_ambiguas`) | idem |
| Taxa de clarificação (τ = 0,75) | 1,3% · 6,6% · 9,2% | idem (`taxa_clarificacao`) | idem |
| Latência mediana por decisão | 232 ms · 195 ms · 897 ms | idem (`latencia_mediana_ms`) | idem (inclui latência de rede da minha máquina) |
| Custo da avaliação | US$0,0007 · 0,0017 · 0,022 | idem (`custo_usd`) | `usage.cost` devolvido pelo OpenRouter |
| "~30×" mais caro (LLM vs MSD1) | 0,022019 / 0,000687 ≈ 32 | idem | divisão dos dois `custo_usd` |
| "~2,5×" mais caro (Jev vs MSD1) | 0,001715 / 0,000687 ≈ 2,5 | idem | idem |
| Jev usa mais tokens de entrada | mediana 638 (14 chamadas, `demo_jev`) vs 254 (3 chamadas, `demo_msd1`); amostra pequena | [`evidencias/traces/`](evidencias/traces) (`extras.usage.input_tokens`) | `python scripts/demo.py --provedor jev` e `--provedor msd1` |
| 20/20 turnos com histórico (follow-ups) roteados corretamente | os 3 provedores | [`evidencias/avaliacao/predicoes.jsonl`](evidencias/avaliacao/predicoes.jsonl) cruzado com [`dados/avaliacao.jsonl`](dados/avaliacao.jsonl) (itens com `historico` não vazio; `top1` = `rotulo`) | contagem feita nesta revisão sobre os arquivos salvos |
| Gasto total da POC | US$0,0709 em 479 chamadas (Gemini 3.5 Flash Lite 0,0667; Jev 0,0029; MSD1 0,0012) | [`runs/ledger.json`](runs/ledger.json) | ledger local, alimentado por `usage.cost` |
| Ledger bateu com a conta | diferença de US$0,0709 em `GET /api/v1/key` | **sem arquivo**: conferi na hora, comparando o `usage` da chave antes e depois | — |

## Demonstrações e traces

| O que mostra | Arquivo |
|---|---|
| Troca de assunto, devolução natural, clarificação e fora de escopo com MSD1 | [`terminal_demo_msd1.txt`](evidencias/terminal_demo_msd1.txt) (saída completa); o JSONL [`traces/demo_msd1.jsonl`](evidencias/traces/demo_msd1.jsonl) tem só a conversa de clarificação, porque foi sobrescrito por uma segunda execução restrita a ela |
| Clarificação com MSD1 (0,68 < τ) | [`terminal_demo_msd1_clarificacao.txt`](evidencias/terminal_demo_msd1_clarificacao.txt) |
| Mesmas conversas com Jev, com A/B e com fallback | [`terminal_demo_jev.txt`](evidencias/terminal_demo_jev.txt), [`terminal_demo_ab.txt`](evidencias/terminal_demo_ab.txt), [`terminal_demo_fallback.txt`](evidencias/terminal_demo_fallback.txt) e os JSONL correspondentes em [`traces/`](evidencias/traces) |
| Fallback: 503 simulado do MSD1 atendido pelo Jev | [`traces/demo_msd1_fallback_queda.jsonl`](evidencias/traces/demo_msd1_fallback_queda.jsonl) (`extras.fallback_motivo`). A queda é **simulada** por um transporte que levanta erro |
| Exemplo de entrada/saída do README | linha da conversa `troca_de_assunto` em [`traces/demo_jev.jsonl`](evidencias/traces/demo_jev.jsonl) |
| Interface rodando | [`gifs/produto.gif`](evidencias/gifs/produto.gif) (gerado por [`scripts/gravar_gif.py`](scripts/gravar_gif.py)), [`screenshots/ui_msd1.png`](evidencias/screenshots/ui_msd1.png), [`ui_jev.png`](evidencias/screenshots/ui_jev.png) |
| Interface em modo mock (sem chave) | [`screenshots/ui_mock.png`](evidencias/screenshots/ui_mock.png): heurística de palavras-chave, não mede nada |
| Diagramas | [`gifs/arquitetura.gif`](evidencias/gifs/arquitetura.gif) e [`arquitetura-thumb.png`](evidencias/arquitetura-thumb.png) (fonte em [`docs/diagrama/`](docs/diagrama)); Mermaid renderizado em [`evidencias/diagramas/`](evidencias/diagramas) |
| Testes | [`tests/test_roteador.py`](tests/test_roteador.py); o CI roda `pytest` e `ruff` sem `OPENROUTER_API_KEY` ([`workflow`](.github/workflows/tests.yml)). A saída da execução de 12/10 está em [`terminal_testes.txt`](evidencias/terminal_testes.txt) (13 testes na época; hoje são 15) |

## Afirmações qualitativas e o que NÃO tem evidência salva

- **Chamada duplicada indevida no GIF** (financeiro abriu chamado de duplicidade para o pedido 10418, que tem uma cobrança só): visível em `produto.gif`; o dado está em [`roteador/dados_loja.py`](roteador/dados_loja.py) (`cobrancas`).
- **Agente de clarificação respondeu ao mérito**: ver a resposta `[clarificacao]` sobre reembolso no cartão em [`terminal_demo_jev.txt`](evidencias/terminal_demo_jev.txt).
- **Agente repetiu "Pix" quando o cliente disse "cartão"**: [`terminal_demo_msd1.txt`](evidencias/terminal_demo_msd1.txt), turno "valeu! e o reembolso cai como? paguei no cartão".
- **Endereço provisório na ferramenta `atualizar_endereco`** e **a sonda manual que comparou MSD1 e Jev com o mesmo payload**: observados durante o desenvolvimento; as saídas dessas rodadas iniciais **não foram guardadas**. O que está salvo são as execuções posteriores.
- **Compatibilidade MSD1 × Jev**: baseada na documentação pública do OpenRouter ([página do modelo](https://openrouter.ai/typesafe/jev-1.13), [guia](https://openrouter.ai/docs/guides/community/jev)) e nos traces acima, que mostram os dois respondendo ao mesmo contrato.

## Reproduzir

Sem chave: `pytest -q` e `python examples/01_offline_mock.py`. Com chave: `python scripts/avaliar.py` e `python scripts/demo.py --provedor msd1` (respeitam o teto de custo do ledger). As respostas dos LLMs variam entre execuções; espere números próximos, não idênticos.
