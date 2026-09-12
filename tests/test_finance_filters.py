"""
Testes do filtro de período das telas financeiras.

Não toca no banco — é lógica de calendário pura.

O caso que motivou boa parte destes testes é o do intervalo invertido: se o
usuário escolher "Agosto/2026 até Fevereiro/2026", trocar as DATAS já
calculadas produziria 28/02 como início e 01/08 como fim — um intervalo
errado. A troca precisa acontecer no par mês/ano, antes de calcular o
primeiro e o último dia.
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


class TestIntervalo:
    def test_sem_filtro_nao_limita_nada(self):
        p = _periodo()
        assert (p['inicio'], p['fim']) == (None, None)
        assert p['tem_periodo'] is False

    def test_padrao_e_o_mes_corrente(self):
        """O relatório de Fluxo Financeiro abre no mês e ano atuais."""
        p = _periodo(padrao_mes_atual=True)
        assert p['inicio'] == date(2026, 9, 1)
        assert p['fim'] == date(2026, 9, 30)

    def test_so_o_inicio_vale_ate_hoje(self):
        """O cliente pediu explicitamente para poder informar só o início."""
        p = _periodo(mes_inicio='3', ano_inicio='2026')
        assert p['inicio'] == date(2026, 3, 1)
        assert p['fim'] == HOJE

    def test_so_o_fim(self):
        p = _periodo(mes_fim='2', ano_fim='2026')
        assert p['inicio'] is None
        assert p['fim'] == date(2026, 2, 28)

    def test_intervalo_completo(self):
        p = _periodo(mes_inicio='3', ano_inicio='2026', mes_fim='6', ano_fim='2026')
        assert p['inicio'] == date(2026, 3, 1)
        assert p['fim'] == date(2026, 6, 30)

    def test_ano_sem_mes_abrange_o_ano(self):
        p = _periodo(ano_inicio='2025', ano_fim='2025')
        assert p['inicio'] == date(2025, 1, 1)
        assert p['fim'] == date(2025, 12, 31)

    def test_virada_de_ano(self):
        p = _periodo(mes_inicio='12', ano_inicio='2025', mes_fim='1', ano_fim='2026')
        assert p['inicio'] == date(2025, 12, 1)
        assert p['fim'] == date(2026, 1, 31)


class TestIntervaloInvertido:
    def test_troca_o_par_mes_ano_e_nao_as_datas(self):
        p = _periodo(mes_inicio='8', ano_inicio='2026', mes_fim='2', ano_fim='2026')
        assert p['inicio'] == date(2026, 2, 1)
        assert p['fim'] == date(2026, 8, 31)

    def test_troca_entre_anos_diferentes(self):
        p = _periodo(mes_inicio='1', ano_inicio='2027', mes_fim='12', ano_fim='2025')
        assert p['inicio'] == date(2025, 12, 1)
        assert p['fim'] == date(2027, 1, 31)

    def test_os_selects_refletem_a_troca(self):
        """A tela precisa mostrar o intervalo que realmente foi aplicado."""
        p = _periodo(mes_inicio='8', ano_inicio='2026', mes_fim='2', ano_fim='2026')
        assert (p['mes_inicio'], p['ano_inicio']) == ('2', '2026')
        assert (p['mes_fim'], p['ano_fim']) == ('8', '2026')


class TestEntradaInvalida:
    @pytest.mark.parametrize('params', [
        {'mes_inicio': 'lixo'},
        {'ano_inicio': '99999'},
        {'mes_inicio': '13'},
        {'mes_inicio': '0'},
        {'ano_inicio': ''},
    ])
    def test_valor_invalido_e_ignorado(self, params):
        p = _periodo(**params)
        assert (p['inicio'], p['fim']) == (None, None)

    def test_ano_com_separador_de_milhar(self):
        """USE_THOUSAND_SEPARATOR faz alguns navegadores enviarem '2.026'."""
        p = _periodo(mes_inicio='5', ano_inicio='2.026')
        assert p['inicio'] == date(2026, 5, 1)


class TestFevereiro:
    def test_ano_bissexto(self):
        p = _periodo(mes_inicio='2', ano_inicio='2024', mes_fim='2', ano_fim='2024')
        assert p['fim'] == date(2024, 2, 29)

    def test_ano_comum(self):
        p = _periodo(mes_inicio='2', ano_inicio='2026', mes_fim='2', ano_fim='2026')
        assert p['fim'] == date(2026, 2, 28)


class TestRotulo:
    def test_mes_unico(self):
        assert rotulo_periodo(_periodo(padrao_mes_atual=True)) == 'Setembro de 2026'

    def test_intervalo(self):
        p = _periodo(mes_inicio='3', ano_inicio='2026', mes_fim='6', ano_fim='2026')
        assert rotulo_periodo(p) == 'Março/2026 a Junho/2026'

    def test_sem_periodo(self):
        assert rotulo_periodo(_periodo()) == 'Todo o período'

    def test_apenas_inicio(self):
        p = _periodo(mes_inicio='3', ano_inicio='2026')
        assert rotulo_periodo(p).startswith('Março/2026 a ')
