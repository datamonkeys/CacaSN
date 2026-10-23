# CacaSN

Caçador de supernovas nos alertas públicos do ZTF, via ALeRCE (sem cadastro).

    python3 cacasn.py            # candidatos detectados nos últimos 3 dias
    python3 cacasn.py --dias 1   # só os mais frescos
    open report.html

Para cada candidato: recortes ciência · referência · diferença, curva de brilho,
nota e se já está no TNS (Transient Name Server, o registro oficial).

Nota sobe com: probabilidade de SN (stamp classifier), drb (real/bogus da rede neural),
detecção em 2+ noites (asteroide não volta ao mesmo lugar), g e r, brilho subindo.
Nota cai com: detecção única, "estelar" para a ALeRCE, estrela do Gaia em 1.5" (variável).

## Como ter o crédito de descoberta

Quem reporta primeiro ao TNS fica como descobridor (nome no registro, ex.: "AT 2026abc,
discovered by ..."). Não pode reportar o que já está lá.

1. Crie conta em https://www.wis-tns.org (gratuita).
2. Em *My account → Bots* crie um bot e anote: id, nome e API key.
3. Salve aqui como `tns.json` (fica fora do git):

        {"bot_id": 12345, "bot_name": "cacasn_louis", "api_key": "..."}

4. Rode de novo: cada candidato mostra "NÃO está no TNS — dá para reportar" ou o nome já dado.
5. Para reportar: TNS → *Submit → AT report*, com RA/Dec, data e magnitude da primeira
   detecção (no relatório) e "ZTF" como instrumento/fonte dos dados.

Realidade: o ZTF tem grupos (o próprio ALeRCE, ZTF/Fritz) que reportam quase tudo em
horas. A chance está nos candidatos fracos/ambíguos que os robôs pulam — por isso o
relatório mostra os recortes para você julgar.

## Nota e alarme (23/10/2026)

Medido contra o que os grupos profissionais reportaram ao TNS (97 candidatos, 42 no TNS):

| Nota | AUC |
|---|---|
| prob. SN do classificador antigo | 0.71 |
| prob. SN do classificador 2025 (beta) da ALeRCE | 0.79 |
| nota do CacaSN (antigo + drb + noites + filtros) | 0.92 |
| + 10·P(SN 2025) − 5·P(AGN 2025) − 5 se a fonte tem histórico longo | **0.96** |

Os 15 primeiros colocados estavam todos no TNS. Os que sobram fora do TNS com nota alta
eram núcleos ativos (AGN) ou variáveis em cima de fonte que já existia.

    python3 cacasn.py --dias 1 --avisar   # notifica candidato fora do TNS com nota >= 18

A vantagem é a velocidade: rodar a cada poucas horas com `--avisar` e reportar antes dos robôs.
