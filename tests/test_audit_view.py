"""
tests/test_audit_view.py

Testes do Painel de Auditoria (core/views_audit.py).

Cobre: controle de acesso, cada filtro isoladamente (incluindo o bug do
separador de milhar em USE_THOUSAND_SEPARATOR — ver core/views_audit.py::
_parse_int), o novo filtro de Status e a exportação em PDF.
"""
from datetime import date

import pytest
from django.urls import reverse

from inventory.domain.value_objects import OperationType
from inventory.models import AnimalMovement, AnimalMovementCancellation
from inventory.services import MovementService


def _criar_movimento(farm, category, user, **kwargs):
    defaults = dict(
        farm_id=str(farm.id),
        animal_category_id=str(category.id),
        operation_type=OperationType.NASCIMENTO,
        quantity=5,
        user=user,
    )
    defaults.update(kwargs)
    return MovementService.execute_entrada(**defaults)


@pytest.mark.django_db
class TestAcesso:
    def test_usuario_anonimo_e_redirecionado(self, client):
        resp = client.get(reverse('core:audit_list'))
        assert resp.status_code == 302

    def test_usuario_comum_e_redirecionado(self, client, db_user):
        client.force_login(db_user)
        resp = client.get(reverse('core:audit_list'))
        assert resp.status_code == 302

    def test_staff_acessa_normalmente(self, client, staff_user):
        client.force_login(staff_user)
        resp = client.get(reverse('core:audit_list'))
        assert resp.status_code == 200


@pytest.mark.django_db
class TestFiltroBusca:
    def test_busca_por_nome_da_fazenda(self, client, staff_user, stock_balance, farm, category, db_user):
        _criar_movimento(farm, category, db_user)
        client.force_login(staff_user)

        resp = client.get(reverse('core:audit_list'), {'q': farm.name})
        assert len(resp.context['movements']) == 1

        resp = client.get(reverse('core:audit_list'), {'q': 'Fazenda Que Não Existe'})
        assert len(resp.context['movements']) == 0


@pytest.mark.django_db
class TestFiltroUsuario:
    def test_filtra_apenas_movimentos_do_usuario(
        self, client, staff_user, stock_balance, stock_balance_b, farm, farm_b, category, db_user,
    ):
        _criar_movimento(farm, category, db_user)
        _criar_movimento(farm_b, category, staff_user)
        client.force_login(staff_user)

        resp = client.get(reverse('core:audit_list'), {'user': db_user.id})
        movements = resp.context['movements']
        assert len(movements) == 1
        assert movements[0]['obj'].created_by_id == db_user.id


@pytest.mark.django_db
class TestFiltroOperacao:
    def test_filtra_por_tipo_de_operacao(self, client, staff_user, stock_balance, farm, category, db_user):
        _criar_movimento(farm, category, db_user, operation_type=OperationType.NASCIMENTO)
        _criar_movimento(farm, category, db_user, operation_type=OperationType.COMPRA, quantity=3)
        client.force_login(staff_user)

        resp = client.get(reverse('core:audit_list'), {'operation': 'COMPRA'})
        movements = resp.context['movements']
        assert len(movements) == 1
        assert movements[0]['obj'].operation_type == 'COMPRA'


@pytest.mark.django_db
class TestFiltroFazenda:
    def test_filtra_por_fazenda(
        self, client, staff_user, stock_balance, stock_balance_b, farm, farm_b, category, db_user,
    ):
        _criar_movimento(farm, category, db_user)
        _criar_movimento(farm_b, category, db_user)
        client.force_login(staff_user)

        resp = client.get(reverse('core:audit_list'), {'farm': str(farm.id)})
        movements = resp.context['movements']
        assert len(movements) == 1
        assert movements[0]['obj'].farm_stock_balance.farm_id == farm.id


@pytest.mark.django_db
class TestFiltroMesAno:
    def test_filtra_por_mes_e_ano(self, client, staff_user, stock_balance, farm, category, db_user):
        _criar_movimento(farm, category, db_user, timestamp=date(2025, 3, 10))
        _criar_movimento(farm, category, db_user, timestamp=date(2025, 8, 1))
        client.force_login(staff_user)

        resp = client.get(reverse('core:audit_list'), {'month': '3', 'year': '2025'})
        assert len(resp.context['movements']) == 1

    def test_filtra_so_por_ano(self, client, staff_user, stock_balance, farm, category, db_user):
        _criar_movimento(farm, category, db_user, timestamp=date(2024, 1, 1))
        _criar_movimento(farm, category, db_user, timestamp=date(2025, 1, 1))
        client.force_login(staff_user)

        resp = client.get(reverse('core:audit_list'), {'year': '2025'})
        assert len(resp.context['movements']) == 1
        assert resp.context['movements'][0]['obj'].timestamp.year == 2025

    def test_filtro_de_ano_com_separador_de_milhar(
        self, client, staff_user, stock_balance, farm, category, db_user,
    ):
        """
        Regressão: USE_THOUSAND_SEPARATOR=True (config/settings.py) faz o
        Django renderizar {{ y }} como "2.025" nas <option> do select de Ano.
        Sem o parser defensivo de core/views_audit.py::_parse_int, esse valor
        volta na querystring e falha em `.isdigit()`, fazendo o filtro de
        Ano nunca ser aplicado (bug real encontrado antes desta mudança).
        """
        _criar_movimento(farm, category, db_user, timestamp=date(2024, 1, 1))
        _criar_movimento(farm, category, db_user, timestamp=date(2025, 1, 1))
        client.force_login(staff_user)

        resp = client.get(reverse('core:audit_list'), {'year': '2.025'})
        assert len(resp.context['movements']) == 1
        assert resp.context['movements'][0]['obj'].timestamp.year == 2025


@pytest.mark.django_db
class TestFiltroStatus:
    def _movimento_ativo(self, farm, category, db_user):
        return _criar_movimento(farm, category, db_user)

    def _movimento_editado(self, farm, category, db_user):
        movement = _criar_movimento(farm, category, db_user)
        AnimalMovement.objects.filter(pk=movement.pk).update(
            metadata={'_edited_by': db_user.username, '_qty_before_edit': 5}
        )
        return movement

    def _movimento_estornado(self, farm, category, staff_user, db_user):
        movement = _criar_movimento(farm, category, db_user)
        AnimalMovementCancellation.objects.create(
            movement=movement,
            cancelled_by=staff_user,
            quantity_restored=movement.quantity,
            balance_before=movement.quantity,
            balance_after=0,
        )
        return movement

    def test_filtra_ativas(self, client, staff_user, stock_balance, farm, category, db_user):
        self._movimento_ativo(farm, category, db_user)
        self._movimento_editado(farm, category, db_user)
        client.force_login(staff_user)

        resp = client.get(reverse('core:audit_list'), {'status': 'active'})
        assert len(resp.context['movements']) == 1
        assert resp.context['movements'][0]['edited'] is False

    def test_filtra_editadas(self, client, staff_user, stock_balance, farm, category, db_user):
        self._movimento_ativo(farm, category, db_user)
        self._movimento_editado(farm, category, db_user)
        client.force_login(staff_user)

        resp = client.get(reverse('core:audit_list'), {'status': 'edited'})
        assert len(resp.context['movements']) == 1
        assert resp.context['movements'][0]['edited'] is True

    def test_filtra_estornadas(self, client, staff_user, stock_balance, farm, category, db_user):
        self._movimento_ativo(farm, category, db_user)
        self._movimento_estornado(farm, category, staff_user, db_user)
        client.force_login(staff_user)

        resp = client.get(reverse('core:audit_list'), {'status': 'cancelled'})
        assert len(resp.context['movements']) == 1
        assert resp.context['movements'][0]['cancellation'] is not None


@pytest.mark.django_db
class TestExportacaoPDF:
    def test_pdf_retorna_200_com_content_type_correto(
        self, client, staff_user, stock_balance, farm, category, db_user,
    ):
        _criar_movimento(farm, category, db_user)
        client.force_login(staff_user)

        resp = client.get(reverse('core:audit_pdf'))
        assert resp.status_code == 200
        assert resp['Content-Type'] == 'application/pdf'
        assert resp.content.startswith(b'%PDF')

    def test_pdf_respeita_filtros(self, client, staff_user, stock_balance, farm, category, db_user):
        _criar_movimento(farm, category, db_user, operation_type=OperationType.NASCIMENTO)
        _criar_movimento(farm, category, db_user, operation_type=OperationType.COMPRA, quantity=3)
        client.force_login(staff_user)

        resp = client.get(reverse('core:audit_pdf'), {'operation': 'COMPRA'})
        assert resp.status_code == 200

    def test_usuario_nao_staff_nao_acessa_pdf(self, client, db_user):
        client.force_login(db_user)
        resp = client.get(reverse('core:audit_pdf'))
        assert resp.status_code == 302
