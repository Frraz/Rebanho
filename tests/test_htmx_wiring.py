"""
tests/test_htmx_wiring.py

Fiação htmx dos formulários: o badge de saldo (#saldo-badge) e os saldos do
desmame (#desmame-saldos) precisam existir no HTML, senão o htmx aborta o
request (htmx:targetError) e o usuário nunca vê o saldo. Ver
templates/shared/form_field.html.

Usa RequestFactory/render_to_string (e não o django.test.Client) para não
depender do template_rendered, que quebra no Django 4.2 + Python 3.14.
"""
import re
import uuid

import pytest
from django.core.exceptions import BadRequest
from django.template.loader import render_to_string
from django.test import RequestFactory
from django.urls import resolve

from core.http import uuid_param
from inventory.forms.movement_forms import (
    CompraForm, DesmameForm, ManejoForm, MudancaCategoriaForm,
    NascimentoForm, SaldoForm,
)
from operations.forms import AbateForm, DoacaoForm, MorteForm, VendaForm


def _campo(form, nome):
    return render_to_string('shared/form_field.html', {'field': form[nome]})


# ── uuid_param(lenient=True) ─────────────────────────────────────────────────

class TestUuidParamLenient:
    def _req(self, query):
        return RequestFactory().get('/x/', query)

    def test_lixo_e_ignorado(self):
        assert uuid_param(self._req({'a': 'abc'}), 'a', lenient=True) is None

    def test_valido_continua_valido(self):
        u = uuid.uuid4()
        assert uuid_param(self._req({'a': str(u)}), 'a', lenient=True) == u

    def test_modo_estrito_nao_mudou(self):
        with pytest.raises(BadRequest):
            uuid_param(self._req({'a': 'abc'}), 'a')


# ── badge de saldo ───────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestSaldoBadge:
    @pytest.mark.parametrize('form_cls', [
        ManejoForm, MudancaCategoriaForm, MorteForm, AbateForm, VendaForm, DoacaoForm,
    ])
    def test_formularios_de_saida_tem_badge(self, form_cls):
        form = form_cls()
        assert form.show_saldo_badge is True
        html = _campo(form, 'quantity')
        assert 'id="saldo-badge"' in html
        assert 'hx-get="/htmx/saldo-atual/"' in html

    @pytest.mark.parametrize('form_cls', [NascimentoForm, CompraForm, SaldoForm])
    def test_formularios_de_entrada_nao_tem_badge(self, form_cls):
        form = form_cls()
        assert form.show_saldo_badge is False
        assert 'saldo-badge' not in _campo(form, 'quantity')

    def test_select_da_categoria_nao_compete_pelo_badge(self):
        attrs = ManejoForm().fields['animal_category'].widget.attrs
        assert 'hx-target' not in attrs and 'hx-get' not in attrs

    def test_mudanca_categoria_mantem_filtro_do_destino(self):
        attrs = MudancaCategoriaForm().fields['animal_category'].widget.attrs
        assert attrs['hx-get'] == '/htmx/categorias-entrada/'
        assert attrs['hx-target'] == '#id_target_category'
        assert 'getElementById("id_animal_category")' in attrs['hx-vals']


# ── desmame ──────────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestDesmame:
    def test_rota_registrada(self):
        assert resolve('/htmx/saldo-desmame/').url_name == 'saldo_desmame'

    def test_placeholder_no_formulario(self):
        html = _campo(DesmameForm(), 'farm')
        assert 'id="desmame-saldos"' in html
        assert 'hx-get="/htmx/saldo-desmame/"' in html

    def test_outros_formularios_nao_ganham_placeholder(self):
        assert 'desmame-saldos' not in _campo(ManejoForm(), 'farm')

    def _chamar(self, db_user, query):
        from inventory.views.htmx_saldo_desmame import saldo_desmame_view
        req = RequestFactory().get('/htmx/saldo-desmame/', query)
        req.user = db_user
        return saldo_desmame_view(req)

    def test_view_renderiza_saldos(self, db_user, farm):
        from inventory.models import AnimalCategory, FarmStockBalance
        macho = AnimalCategory.objects.create(
            name='B. Macho', slug=AnimalCategory.SystemSlugs.BEZERRO_MACHO, is_active=True)
        femea = AnimalCategory.objects.create(
            name='B. Fêmea', slug=AnimalCategory.SystemSlugs.BEZERRO_FEMEA, is_active=True)
        # Um signal já cria os saldos (zerados) ao criar a categoria.
        FarmStockBalance.objects.filter(farm=farm, animal_category=macho).update(current_quantity=7)
        FarmStockBalance.objects.filter(farm=farm, animal_category=femea).update(current_quantity=3)

        r = self._chamar(db_user, {'farm': str(farm.id)})
        body = r.content.decode()
        assert r.status_code == 200
        # Os dois saldos aparecem, na ordem macho -> fêmea.
        assert re.findall(r'>\s*(\d+)\s*</span>', body) == ['7', '3']

    def test_view_sem_fazenda_pede_selecao(self, db_user):
        r = self._chamar(db_user, {})
        assert r.status_code == 200
        assert 'Selecione uma fazenda' in r.content.decode()

    def test_view_com_uuid_invalido_levanta_bad_request(self, db_user):
        with pytest.raises(BadRequest):
            self._chamar(db_user, {'farm': 'abc'})


# ── filtros de lista tolerantes ──────────────────────────────────────────────

class TestFiltrosDeListaTolerantes:
    def test_movimentacoes_ignora_farm_invalida(self):
        from inventory.views.movimentacoes import _build_filters_context
        f = _build_filters_context(RequestFactory().get('/m/', {'farm': 'abc'}))
        assert f['farm_id'] == '' and f['has_filters'] is False

    def test_movimentacoes_mantem_farm_valida_como_string(self):
        from inventory.views.movimentacoes import _build_filters_context
        u = uuid.uuid4()
        f = _build_filters_context(RequestFactory().get('/m/', {'farm': str(u)}))
        assert f['farm_id'] == str(u) and f['has_filters'] is True

    def test_ocorrencias_ignora_farm_invalida(self):
        from operations.views.ocorrencias import _build_filters_context
        f = _build_filters_context(RequestFactory().get('/o/', {'farm': 'abc'}))
        assert f['farm_id'] == '' and f['has_filters'] is False
