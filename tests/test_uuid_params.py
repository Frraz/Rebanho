"""
tests/test_uuid_params.py

UUID malformado / "undefined" vindo da query string não pode virar 500
(e, portanto, e-mail de erro). Ver fixbugemail.txt.
"""
import uuid

import pytest
from django.core import mail
from django.core.exceptions import BadRequest
from django.test import RequestFactory, override_settings
from django.urls import reverse

from core.http import uuid_param


def _req(query):
    return RequestFactory().get('/x/', query)


# ── uuid_param ───────────────────────────────────────────────────────────────

class TestUuidParam:
    @pytest.mark.parametrize('valor', ['', 'undefined', 'null', 'None', '   '])
    def test_valores_vazios_sao_ignorados(self, valor):
        assert uuid_param(_req({'a': valor}), 'a') is None

    def test_ausente_retorna_none(self):
        assert uuid_param(_req({}), 'a') is None

    def test_uuid_valido(self):
        u = uuid.uuid4()
        assert uuid_param(_req({'a': str(u)}), 'a') == u

    def test_lixo_levanta_bad_request(self):
        with pytest.raises(BadRequest):
            uuid_param(_req({'a': 'abc'}), 'a')

    def test_primeiro_nome_com_valor_vence(self):
        u = uuid.uuid4()
        assert uuid_param(_req({'b': str(u)}), 'a', 'b') == u

    def test_required(self):
        with pytest.raises(BadRequest):
            uuid_param(_req({}), 'a', required=True)


# ── endpoints htmx ───────────────────────────────────────────────────────────

@pytest.fixture
def logado(client, db_user):
    client.force_login(db_user)
    return client


class TestHtmxCategoriasEntrada:
    url = '/htmx/categorias-entrada/'

    def test_undefined_nao_quebra_e_lista_tudo(self, logado, category, category_b):
        r = logado.get(self.url, {'exclude_category': 'undefined'})
        assert r.status_code == 200
        body = r.content.decode()
        assert str(category.id) in body and str(category_b.id) in body

    def test_uuid_valido_exclui_categoria(self, logado, category, category_b):
        r = logado.get(self.url, {'exclude_category': str(category.id)})
        assert r.status_code == 200
        body = r.content.decode()
        assert str(category.id) not in body
        assert str(category_b.id) in body

    def test_lixo_responde_400(self, logado):
        assert logado.get(self.url, {'exclude_category': 'abc'}).status_code == 400

    def test_nome_da_categoria_e_escapado(self, logado, db):
        from inventory.models import AnimalCategory
        AnimalCategory.objects.create(name='<b>x</b>', is_active=True)
        body = logado.get(self.url).content.decode()
        assert '<b>x</b>' not in body
        assert '&lt;b&gt;x&lt;/b&gt;' in body


class TestHtmxSaldoAtual:
    url = '/htmx/saldo-atual/'

    def test_parametros_invalidos_respondem_400(self, logado):
        r = logado.get(self.url, {'farm': 'abc', 'animal_category': 'xyz'})
        assert r.status_code == 400

    def test_sem_parametros_responde_vazio(self, logado):
        r = logado.get(self.url)
        assert r.status_code == 200 and r.content == b''

    def test_saldo_existente(self, logado, stock_balance_with_animals):
        r = logado.get(self.url, {
            'farm': str(stock_balance_with_animals.farm_id),
            'animal_category': str(stock_balance_with_animals.animal_category_id),
        })
        assert r.status_code == 200
        assert 'data-max-quantity="20"' in r.content.decode()


class TestCategoriasSaida:
    def test_farm_invalida_responde_400(self, logado):
        assert logado.get('/htmx/categorias-saida/', {'farm': 'abc'}).status_code == 400

    def test_farm_undefined_pede_selecao(self, logado):
        r = logado.get('/htmx/categorias-saida/', {'farm': 'undefined'})
        assert r.status_code == 200
        assert 'Selecione uma fazenda' in r.content.decode()


# ── middleware (rede de segurança) ───────────────────────────────────────────

class TestValidationErrorAs400:
    def test_filtro_de_lista_com_uuid_invalido_vira_400(self, logado):
        r = logado.get(reverse('vendas:list'), {'cliente': 'abc'})
        assert r.status_code == 400


# ── correções pontuais ───────────────────────────────────────────────────────

class TestFichaManual:
    def test_mes_invalido_nao_gera_500(self, logado, farm):
        r = logado.get(reverse('reporting:manual_control_pdf'),
                       {'farm': str(farm.id), 'month': 'abc'})
        assert r.status_code == 400

    def test_farm_invalida_vira_400(self, logado):
        r = logado.get(reverse('reporting:manual_control_pdf'), {'farm': 'abc'})
        assert r.status_code == 400


def test_relatorio_consolidado_pdf_categoria_invalida_vira_400(logado):
    r = logado.get(reverse('reporting:consolidated_pdf'), {'category': 'abc'})
    assert r.status_code == 400


# ── e-mail de erro ───────────────────────────────────────────────────────────

class TestThrottledAdminEmailHandler:
    @override_settings(
        ADMINS=[('Admin', 'dono@example.com')],
        CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}},
        EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    )
    def test_mesmo_erro_envia_um_unico_email(self):
        import logging
        from django.core.cache import cache
        from core.logging_handlers import ThrottledAdminEmailHandler

        cache.clear()
        handler = ThrottledAdminEmailHandler()
        record = logging.LogRecord('django.request', logging.ERROR, __file__, 1,
                                   'Internal Server Error: /x/', None, None)
        handler.emit(record)
        handler.emit(record)
        assert len(mail.outbox) == 1

    def test_placeholder_nao_vira_destinatario(self):
        from django.conf import settings
        assert not any('seudominio' in e for _, e in settings.ADMINS)


def test_csrf_cookie_e_mascarado():
    from core.error_reporting import MaskCsrfExceptionReporterFilter
    req = RequestFactory().get('/x/')
    req.META['CSRF_COOKIE'] = 'segredo-csrf'
    meta = MaskCsrfExceptionReporterFilter().get_safe_request_meta(req)
    assert meta['CSRF_COOKIE'] != 'segredo-csrf'
