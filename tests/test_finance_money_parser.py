"""
Testes do leitor de valores gravados no `metadata`.

Este parser decide quanta dívida cada cliente herda do histórico, então um
erro aqui é um erro no dinheiro de todo mundo. O caso mais importante é o
primeiro: `"1.250"` gravado por `str(Decimal)` vale um e vinte e cinco, e
interpretá-lo como milhar inflaria a dívida em mil vezes.

Não depende de banco nem de Django — roda instantaneamente.
"""
from decimal import Decimal

import pytest

from finance.utils.money import (
    parse_stored_amount,
    parse_stored_money,
    parse_stored_weight,
    quantize_money,
    to_pt_br_input,
)


class TestOPontoESempreDecimalSemVirgula:
    """A regra que separa este parser do de formulário."""

    def test_str_decimal_com_tres_casas_nao_vira_milhar(self):
        # O usuário digitou "1,250" → Decimal("1.250") → gravado como "1.250".
        # Reinterpretar como milhar daria 1250 — erro de 1000×.
        assert parse_stored_money('1.250') == Decimal('1.25')

    def test_str_decimal_comum(self):
        assert parse_stored_money('15000.00') == Decimal('15000.00')
        assert parse_stored_money('15000.50') == Decimal('15000.50')

    def test_com_virgula_o_ponto_e_milhar(self):
        assert parse_stored_money('15.000,50') == Decimal('15000.50')
        assert parse_stored_money('1.250,80') == Decimal('1250.80')


class TestTiposMistosNoJson:
    """As views gravam texto; o seed_data grava float. Os dois existem no banco."""

    def test_float(self):
        assert parse_stored_money(15000.0) == Decimal('15000.00')

    def test_int(self):
        assert parse_stored_money(15000) == Decimal('15000.00')

    def test_decimal(self):
        assert parse_stored_money(Decimal('99.90')) == Decimal('99.90')

    def test_bool_nao_e_dinheiro(self):
        assert parse_stored_money(True) is None


class TestAusenciaDeValor:
    """Muitas vendas antigas foram cadastradas sem preço."""

    @pytest.mark.parametrize('valor', ['', '  ', '-', '—', None, 'abc', 'None', 'nan'])
    def test_vira_none(self, valor):
        assert parse_stored_money(valor) is None

    def test_zero_e_negativo_contam_como_sem_preco(self):
        assert parse_stored_money('0') is None
        assert parse_stored_money('-50') is None

    def test_nunca_levanta_excecao(self):
        """Um valor corrompido não pode derrubar a migração inteira."""
        for lixo in ([], {}, object(), '1.2.3.4', 'R$', '∞'):
            assert parse_stored_money(lixo) is None


class TestLimpeza:
    def test_simbolo_de_moeda_e_espacos(self):
        assert parse_stored_money('R$ 1.500,00') == Decimal('1500.00')
        assert parse_stored_money('  2500.00  ') == Decimal('2500.00')

    def test_espaco_nao_quebravel(self):
        assert parse_stored_money('R$\xa01.500,00') == Decimal('1500.00')


class TestPesoEArredondamento:
    def test_peso_aceita_duas_casas(self):
        assert parse_stored_weight('1250.756') == Decimal('1250.76')

    def test_peso_zero_e_none(self):
        assert parse_stored_weight('0') is None

    def test_arredondamento_comercial(self):
        assert quantize_money(Decimal('10.005')) == Decimal('10.01')
        assert quantize_money(Decimal('10.004')) == Decimal('10.00')

    def test_amount_preserva_zero_e_negativo(self):
        """parse_stored_amount é o cru; só o de dinheiro descarta zero."""
        assert parse_stored_amount('0') == Decimal('0')
        assert parse_stored_amount('-50') == Decimal('-50')


class TestFormatacaoParaOFormulario:
    """
    Regressão: valores que voltam para a tela na EDIÇÃO.

    O masks.js lê o que está no campo e decide se o ponto é decimal ou milhar
    pela quantidade de dígitos depois dele. O preço por quilo guarda 4 casas,
    então `str(Decimal("10.0000"))` = "10.0000" era lido como milhar e um preço
    de R$ 10,00/kg aparecia como R$ 100.000 ao abrir a venda para editar.

    Entregar o valor já em pt-BR resolve: a vírgula elimina a ambiguidade.
    """

    def test_preco_por_kg_com_quatro_casas_nao_vira_milhar(self):
        assert to_pt_br_input(Decimal('10.0000'), casas=4) == '10,00'
        assert to_pt_br_input(Decimal('12.5000'), casas=4) == '12,50'

    def test_preserva_as_casas_que_carregam_informacao(self):
        assert to_pt_br_input(Decimal('10.1234'), casas=4) == '10,1234'

    def test_separador_de_milhar(self):
        assert to_pt_br_input(Decimal('1250.8')) == '1.250,80'
        assert to_pt_br_input(Decimal('1234567.89')) == '1.234.567,89'

    def test_vazio(self):
        assert to_pt_br_input(None) == ''
        assert to_pt_br_input('') == ''

    def test_ida_e_volta(self):
        """O que sai para a tela tem que voltar igual ao ser lido."""
        for valor in (Decimal('10.00'), Decimal('1250.80'), Decimal('1234567.89')):
            assert parse_stored_money(to_pt_br_input(valor)) == valor
