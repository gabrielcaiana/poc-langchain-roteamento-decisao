"""Gera dados/avaliacao.jsonl: turnos FICTÍCIOS rotulados (escritos com apoio de LLM, sem revisão humana).
Cada item: histórico curto (opcional), especialista atual, última mensagem e rótulo esperado.
'ambigua': True marca turnos em que eu mesmo aceitaria uma clarificação como resposta correta."""
import json, pathlib

S = []  # (mensagem, rótulo, historico, agente_atual, ambigua)
def add(msg, lab, hist=None, atual=None, amb=False): S.append((msg, lab, hist or [], atual, amb))

# --- turnos isolados (abertura de conversa) ---
for m in ["quero devolver o liquidificador, não gostei", "a camiseta veio no tamanho errado, como troco?",
          "o fone chegou com o lado esquerdo mudo, quero trocar", "me arrependi da compra do notebook, ainda dá?",
          "como gero a etiqueta pra mandar o tênis de volta?", "posso trocar a mochila por outra cor?",
          "o kit de panelas veio amassado, quero devolver", "a caneca personalizada veio com o nome errado"]:
    add(m, "devolucao")
for m in ["cadê meu pedido 10407?", "o rastreio não atualiza há 4 dias", "quero mudar o endereço de entrega do 10412",
          "dá pra cancelar o pedido 10414 antes de sair?", "não consigo entrar na minha conta", "como pareio o smartwatch com o celular?",
          "a transportadora disse que entregou mas não recebi nada", "qual o prazo de entrega pro meu cep?"]:
    add(m, "suporte")
for m in ["fui cobrado duas vezes no cartão", "quando cai o reembolso do pedido cancelado?", "o boleto venceu, consigo outro?",
          "apareceu juros na fatura e eu paguei em dia", "o estorno do pix ainda não caiu", "o valor cobrado tá maior que o do carrinho",
          "o cupom não foi descontado no total", "quero a nota fiscal com o valor certo, me cobraram a mais"]:
    add(m, "financeiro")
for m in ["qual a previsão do tempo pra amanhã?", "me indica uma receita de bolo", "quem ganhou o jogo ontem?",
          "vocês estão contratando?", "me ajuda com meu dever de matemática", "qual a capital da Austrália?",
          "escreve um poema pra minha namorada", "qual o melhor banco digital?"]:
    add(m, "fora_de_escopo")

# --- follow-ups curtos que dependem do histórico ---
H_DEV = [{"cliente": "quero devolver o tênis do pedido 10422"}, {"atendente": "Está dentro do prazo de 7 dias. Quer que eu abra a solicitação?"}]
H_SUP = [{"cliente": "meu pedido 10407 tá atrasado"}, {"atendente": "Ele está em trânsito com a transportadora."}]
H_FIN = [{"cliente": "me cobraram duas vezes no pedido 10430"}, {"atendente": "Confirmei a duplicidade e abri o chamado de estorno."}]
for m in ["pode abrir sim", "e a etiqueta chega onde?", "preciso mandar na caixa original?", "ok, e se eu quiser trocar em vez de devolver?"]:
    add(m, "devolucao", H_DEV, "devolucao")
for m in ["e quando chega?", "tem como acelerar?", "o código de rastreio é qual?", "e se eu não estiver em casa?"]:
    add(m, "suporte", H_SUP, "suporte")
for m in ["em quantos dias cai?", "volta no mesmo cartão?", "e se não cair até lá?", "tem protocolo?"]:
    add(m, "financeiro", H_FIN, "financeiro")

# --- trocas de assunto no meio da conversa ---
add("aproveitando, me cobraram o frete duas vezes", "financeiro", H_SUP, "suporte")
add("outra coisa: o fone que chegou semana passada veio com defeito, quero trocar", "devolucao", H_SUP, "suporte")
add("e o pedido 10417, já saiu pra entrega?", "suporte", H_DEV, "devolucao")
add("e aquela cobrança de juros no boleto, como fica?", "financeiro", H_DEV, "devolucao")
add("mudando de assunto, como troco a senha da minha conta?", "suporte", H_FIN, "financeiro")
add("ah, e quero devolver a mochila também", "devolucao", H_FIN, "financeiro")
add("por falar nisso, você torce pra qual time?", "fora_de_escopo", H_SUP, "suporte")
add("valeu. sabe me dizer o resultado da mega-sena?", "fora_de_escopo", H_FIN, "financeiro")

# --- linguagem informal / erros de digitação ---
for m, l in [("kd meu pedidoo", "suporte"), ("quero meu dinheiro de volta dessa porcaria", "financeiro"),
             ("essa camisa n serviu quero troca", "devolucao"), ("cobraram 2x no meu cartao socorro", "financeiro"),
             ("o entregador sumiu cm minha encomenda", "suporte"), ("trocar o tenis q veio apertado", "devolucao"),
             ("vcs vendem ingresso de show?", "fora_de_escopo"), ("pix caiu duplicado devolve um", "financeiro")]:
    add(m, l)

# --- casos genuinamente ambíguos (clarificação seria aceitável) ---
for m, l in [("preciso de ajuda", "suporte"), ("não tô satisfeito", "devolucao"), ("quero resolver aquilo do pedido", "suporte"),
             ("o fone veio com defeito e já fui cobrado de novo", "financeiro"), ("deu problema na minha compra", "suporte"),
             ("oi", "suporte"), ("quero cancelar e receber o dinheiro", "financeiro"), ("o produto não é o que eu pedi e cobraram mais caro", "devolucao")]:
    add(m, l, amb=True)

# --- mais variações isoladas para equilibrar classes ---
for m, l in [("o notebook não liga desde que chegou, faz 20 dias", "devolucao"), ("a escova elétrica veio aberta, posso devolver?", "devolucao"),
             ("o pedido aparece como entregue mas não chegou", "suporte"), ("como acompanho o pedido pelo app?", "suporte"),
             ("o reembolso veio faltando 10 reais", "financeiro"), ("paguei o boleto e o pedido continua aguardando pagamento", "financeiro"),
             ("qual o horário de funcionamento do shopping?", "fora_de_escopo"), ("me fala uma piada", "fora_de_escopo")]:
    add(m, l)

out = pathlib.Path(__file__).with_name("avaliacao.jsonl")
out.write_text("\n".join(json.dumps({"id": f"t{i:03d}", "mensagem": m, "rotulo": l, "historico": h, "agente_atual": a,
                                     "ambigua": amb, "origem": "ficticio-llm-assistido-sem-revisao-humana"}, ensure_ascii=False)
                         for i, (m, l, h, a, amb) in enumerate(S)) + "\n")
print(len(S), "turnos")
