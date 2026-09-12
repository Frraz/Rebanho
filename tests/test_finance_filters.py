"""
Testes do filtro de período das telas financeiras.

Não toca no banco — é lógica de calendário pura.

O caso que motivou o teste de "Todos"/"Todos" explícito: o formulário sempre
manda `mes=` e `ano=` (vazios) quando o usuário escolhe "Todos" nos dois
selects e envia. Isso precisa ser tratado como uma escolha explícita, não
como "nada informado" — senão, numa tela com `padrao_mes_atual=True`, o
usuário nunca conseguiria sair do mês corrente.
"""
from datetime import date

import pytest

from finance.filters import parse_periodo, rotulo_periodo

HOJE = date(2026, 9, 12)


class FakeRequest:
    def __init__(self, **params):
        self.GET = params


def _periodo(padrao_mes_atual=False, **params):
    return parse_periodo(
        FakeRequest(**params), padrao_mes_atual=padrao_mes_atual, hoje=HOJE
    )


class TestSemFiltro:
    def test_nada_informado_sem_padrao(self):
        p = _periodo()
        assert (p['inicio'], p['fim']) == (None, None)
        assert p['tem_periodo'] is False
        assert p['contiguo'] is True

    def test_nada_informado_com_padrao_usa_mes_atual(self):
        """O Fluxo Financeiro (e agora Venda e Pagamento) abrem no mês atual."""
        p = _periodo(padrao_mes_atual=True)
        assert p['inicio'] == date(2026, 9, 1)
        assert p['fim'] == date(2026, 9, 30)
        assert p['mes'] == '9'
        assert p['ano'] == '2026'

    def test_todos_explicito_nao_reaplica_o_padrao(self):
        """Escolher 'Todos' nos dois selects e enviar deve valer, mesmo com padrão."""
        p = _periodo(padrao_mes_atual=True, mes='', ano='')
        assert (p['inicio'], p['fim']) == (None, None)
        assert p['tem_periodo'] is False


class TestAnoInteiro:
    def test_so_o_ano_abrange_o_ano_todo(self):
        p = _periodo(ano='2025')
        assert p['inicio'] == date(2025, 1, 1)
        assert p['fim'] == date(2025, 12, 31)
        assert p['contiguo'] is True
        assert p['tem_periodo'] is True


class TestMesEAno:
    def test_mes_e_ano_especificos(self):
        p = _periodo(mes='3', ano='2026')
        assert p['inicio'] == date(2026, 3, 1)
        assert p['fim'] == date(2026, 3, 31)
        assert p['contiguo'] is True

    def test_fevereiro_bissexto(self):
        p = _periodo(mes='2', ano='2024')
        assert p['fim'] == date(2024, 2, 29)

    def test_fevereiro_comum(self):
        p = _periodo(mes='2', ano='2026')
        assert p['fim'] == date(2026, 2, 28)


class TestMesSemAno:
    def test_mes_sem_ano_nao_e_continuo(self):
        p = _periodo(mes='12')
        assert (p['inicio'], p['fim']) == (None, None)
        assert p['contiguo'] is False
        assert p['tem_periodo'] is True
        assert p['mes'] == '12'
        assert p['ano'] == ''


class TestEntradaInvalida:
    @pytest.mark.parametrize('params', [
        {'mes': 'lixo'},
        {'ano': '99999'},
        {'mes': '13'},
        {'mes': '0'},
        {'ano': ''},
    ])
    def test_valor_invalido_e_ignorado(self, params):
        p = _periodo(**params)
        assert (p['inicio'], p['fim']) == (None, None)

    def test_ano_com_separador_de_milhar(self):
        """USE_THOUSAND_SEPARATOR faz alguns navegadores enviarem '2.026'."""
        p = _periodo(mes='5', ano='2.026')
        assert p['inicio'] == date(2026, 5, 1)


class TestRotulo:
    def test_mes_e_ano(self):
        assert rotulo_periodo(_periodo(padrao_mes_atual=True)) == 'Setembro de 2026'

    def test_ano_inteiro(self):
        p = _periodo(ano='2025')
        assert rotulo_periodo(p) == 'Ano de 2025'

    def test_sem_periodo(self):
        assert rotulo_periodo(_periodo()) == 'Todo o período'

    def test_mes_sem_ano(self):
        p = _periodo(mes='12')
        assert rotulo_periodo(p) == 'Dezembro (todos os anos)'
