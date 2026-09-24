"""Leitura de documento/imagem: PDF de cotacao e foto de nota fiscal.
Dona futura: faixa A9 (Fase 7). Extraido de claude_client.py sem mudar
comportamento; claude_client.py reexporta estes nomes."""
import base64

from ia.legado import SONNET, _extract_json, _usage, client


COTACAO_PDF_PROMPT = """Leia esse PDF de orcamento/cotacao de um fornecedor de material de
construcao e extraia em JSON:
{"fornecedor": nome da empresa/fornecedor (texto curto) ou null se nao identificar,
 "valor": valor TOTAL do orcamento em reais (numero puro, sem "R$" nem separador de milhar) ou
 null se nao achar um valor total claro, "prazo_texto": prazo de entrega mencionado, em texto
 livre (ex: "15 dias uteis") ou null, "observacao": um detalhe curto relevante (frete incluso,
 validade da proposta, forma de pagamento) ou null}

So extraia o que estiver escrito no documento - nunca estime ou arredonde um valor que nao
esteja explicito. Responda SO com o JSON, sem explicacao, sem markdown."""


def extrair_item_cotacao_pdf(pdf_bytes: bytes) -> tuple[dict, dict]:
    """Le um PDF de cotacao/orcamento de fornecedor e extrai fornecedor/valor/prazo -
    extracao pura (mesmo espirito de classify_capture: a IA so le e devolve estruturado,
    nunca decide nada sozinho, quem compara os valores depois e o Python)."""
    pdf_b64 = base64.standard_b64encode(pdf_bytes).decode("utf-8")
    response = client.messages.create(
        model=SONNET,
        max_tokens=400,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "document",
                        "source": {"type": "base64", "media_type": "application/pdf", "data": pdf_b64},
                    },
                    {"type": "text", "text": COTACAO_PDF_PROMPT},
                ],
            }
        ],
    )
    texto = "".join(b.text for b in response.content if b.type == "text")
    return _extract_json(texto), _usage(response)


NOTA_FISCAL_PROMPT = """Leia essa foto de nota fiscal/cupom fiscal e extraia em JSON:
{"valor": valor TOTAL da compra em reais (numero puro, sem "R$" nem separador de milhar) ou null
 se nao achar um valor total claro, "estabelecimento": nome do estabelecimento/loja (texto curto)
 ou null se nao identificar, "data": data da compra no formato "AAAA-MM-DD" ou null se nao achar
 uma data legivel}

So extraia o que estiver escrito na foto - nunca estime ou arredonde um valor que nao esteja
explicito, e nunca invente estabelecimento ou data que a foto nao mostre com clareza. Responda SO
com o JSON, sem explicacao, sem markdown."""

MEDIA_TYPES_IMAGEM_VALIDOS = {"image/jpeg", "image/png", "image/webp", "image/heic"}


def extrair_nota_fiscal_foto(image_bytes: bytes, media_type: str) -> tuple[dict, dict]:
    """Le uma foto de nota fiscal e extrai valor/estabelecimento/data - mesmo
    espirito de extrair_item_cotacao_pdf (extracao pura via API de visao da
    Anthropic, decisao ja tomada com o Alex pra nao usar OCR local/Tesseract):
    a IA so le a foto e devolve estruturado, nunca decide categoria nem
    grava nada sozinha - quem confirma e categoriza e o fluxo de gasto
    existente (US-C9)."""
    image_b64 = base64.standard_b64encode(image_bytes).decode("utf-8")
    response = client.messages.create(
        model=SONNET,
        max_tokens=300,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {"type": "base64", "media_type": media_type, "data": image_b64},
                    },
                    {"type": "text", "text": NOTA_FISCAL_PROMPT},
                ],
            }
        ],
    )
    texto = "".join(b.text for b in response.content if b.type == "text")
    return _extract_json(texto), _usage(response)
