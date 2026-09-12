"""
finance/utils/money.py

Leitura de valores monetários que foram gravados no `metadata` (JSONField) do
ledger antigo.

═══════════════════════════════════════════════════════════════════════════════
POR QUE ESTE MÓDULO EXISTE E NÃO SE USA `normalize_pt_br_decimal` AQUI
═══════════════════════════════════════════════════════════════════════════════

`core.utils.decimal_utils.normalize_pt_br_decimal` é o parser de ENTRADA DE
FORMULÁRIO. Ele precisa adivinhar se "1.250" é mil e duzentos e cinquenta
(milhar pt-BR) ou um e vinte e cinco — e escolhe milhar, que é o certo para
quem está digitando.

Mas o que está gravado no JSON não é o que o usuário digitou: é o resultado de
`str(Decimal)`. E aí o ponto é SEMPRE separador decimal. Exemplo real:

    usuário digita  "1,250"
    → normalize_pt_br_decimal → Decimal("1.250")   (um vírgula vinte e cinco)
    → gravado no JSON como     "1.250"
    → reler com normalize_pt_br_decimal → Decimal("1250")   ← ERRO DE 1000×

Por isso a regra aqui é diferente e sem adivinhação:

    • tem vírgula?  → é entrada pt-BR crua: "." é milhar, "," é decimal
    • não tem?      → o "." é decimal, ponto final

Esta distinção é a diferença entre importar a dívida certa do cliente e
importar uma dívida mil vezes maior.
"""
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

# Textos que aparecem no lugar de "sem valor" ao longo do histórico.
_EMPTY_TOKENS = {'', '-', '—', 'none', 'null', 'nan', 'n/a'}

CENTS = Decimal('0.01')


def parse_stored_amount(value):
    """
    Converte um valor vindo do `metadata` para Decimal.

    Aceita o que existe de fato no banco hoje: `str(Decimal)` gravado pelas
    views, `float` gravado pelo `seed_data.py`, `int`, `Decimal`, `None` e
    strings vazias ou de preenchimento.

    Devolve `None` quando não há valor utilizável — nunca levanta exceção.
    Cabe a quem chama decidir o que fazer com a ausência (no backfill, a venda
    fica sem valor financeiro e pode ser completada depois pelo usuário).

    >>> parse_stored_amount("15000.00")
    Decimal('15000.00')
    >>> parse_stored_amount("1.250")          # str(Decimal) — ponto é decimal
    Decimal('1.250')
    >>> parse_stored_amount("15.000,50")      # digitação pt-BR crua
    Decimal('15000.50')
    >>> parse_stored_amount(15000.0)
    Decimal('15000.0')
    >>> parse_stored_amount("") is None
    True
    """
    if value is None:
        return None

    if isinstance(value, Decimal):
        return value if value.is_finite() else None

    if isinstance(value, bool):
        # bool é subclasse de int; nunca é um valor monetário legítimo.
        return None

    if isinstance(value, (int, float)):
        try:
            parsed = Decimal(str(value))
        except (InvalidOperation, ValueError):
            return None
        return parsed if parsed.is_finite() else None

    if not isinstance(value, str):
        return None

    raw = value.strip()
    raw = raw.replace('R$', '').replace('\xa0', '').replace(' ', '').strip()

    if raw.lower() in _EMPTY_TOKENS:
        return None

    if ',' in raw:
        # Digitação pt-BR crua: ponto é milhar, vírgula é decimal.
        raw = raw.replace('.', '').replace(',', '.')
    # Sem vírgula: o ponto é decimal. NÃO tratar como milhar — ver docstring.

    try:
        parsed = Decimal(raw)
    except (InvalidOperation, ValueError):
        return None

    return parsed if parsed.is_finite() else None


def parse_stored_money(value):
    """
    Igual a `parse_stored_amount`, mas para dinheiro: arredonda a 2 casas e
    descarta valores negativos ou zerados (que significam "sem preço").
    """
    parsed = parse_stored_amount(value)
    if parsed is None or parsed <= 0:
        return None
    return quantize_money(parsed)


def parse_stored_weight(value):
    """Peso em kg: 2 casas, descarta zero e negativo."""
    parsed = parse_stored_amount(value)
    if parsed is None or parsed <= 0:
        return None
    return parsed.quantize(CENTS, rounding=ROUND_HALF_UP)


def quantize_money(value):
    """Arredonda para centavos com a regra comercial (meio para cima)."""
    if value is None:
        return None
    return Decimal(value).quantize(CENTS, rounding=ROUND_HALF_UP)


def to_pt_br_input(value, casas=2):
    """
    Formata um Decimal para preencher um campo com máscara pt-BR.

    ═══════════════════════════════════════════════════════════════════════════
    POR QUE NÃO BASTA MANDAR O DECIMAL DIRETO PARA O FORMULÁRIO

    O widget renderiza `str(valor)` e o masks.js reinterpreta o que encontra no
    campo. A heurística dele é: ponto seguido de 1 ou 2 dígitos é decimal;
    qualquer outra coisa é separador de milhar. Isso quebra justamente no preço
    por quilo, que tem 4 casas:

        Decimal("10.0000")  →  str "10.0000"  →  a tela mostra "100.000"

    ou seja, R$ 10,00/kg apareceria como R$ 100.000/kg ao abrir uma venda para
    editar. Entregando o valor já em pt-BR ("10,00"), a vírgula elimina a
    ambiguidade e o campo mostra o número certo.

    >>> to_pt_br_input(Decimal('10.0000'))
    '10,00'
    >>> to_pt_br_input(Decimal('1250.8'))
    '1.250,80'
    >>> to_pt_br_input(None)
    ''
    """
    if value is None or value == '':
        return ''

    try:
        numero = Decimal(value)
    except (InvalidOperation, ValueError, TypeError):
        return ''

    # Preço por quilo guarda 4 casas, mas exibir "10,0000" só polui. Mostramos
    # as casas extras apenas quando elas carregam informação.
    if casas > 2 and numero == numero.quantize(CENTS):
        casas = 2

    texto = f"{numero:,.{casas}f}"          # formato inglês: 1,250.80
    return texto.replace(',', '\x00').replace('.', ',').replace('\x00', '.')
