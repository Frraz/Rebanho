"""
finance/services/payment_service.py

Pagamentos de clientes e ajustes manuais de saldo.

Muito mais simples que o SaleService: nada aqui toca no estoque de animais.
Cada pagamento gera exatamente um lançamento de crédito no extrato do cliente.

Um pagamento pode ser maior que a dívida, ou existir sem dívida nenhuma — é o
caso do pagamento antecipado. O saldo do cliente simplesmente fica positivo e
será abatido nas próximas compras.
"""
import logging

from django.core.exceptions import ValidationError
from django.db import transaction

from finance.models import (
    DeletedObjectType,
    EntrySource,
    EntryType,
    FinanceDeletionLog,
    FinancialEntry,
    Payment,
)
from finance.utils.money import quantize_money

logger = logging.getLogger(__name__)


class PaymentService:
    """Regras de negócio dos pagamentos."""

    # ────────────────────────────────────────────────────────────────────
    # PAGAMENTOS
    # ────────────────────────────────────────────────────────────────────

    @staticmethod
    def create(*, client, date, amount, payment_type, user, description='') -> Payment:
        """Registra um pagamento e o crédito correspondente no extrato."""
        amount = quantize_money(amount)
        if amount is None or amount <= 0:
            raise ValidationError("O valor do pagamento deve ser maior que zero.")

        with transaction.atomic():
            payment = Payment.objects.create(
                client=client,
                date=date,
                amount=amount,
                payment_type=payment_type,
                description=description or '',
                created_by=user,
            )
            PaymentService._sync_financial_entry(payment, user)

        logger.warning(
            "[PAGAMENTO] Criado %s | Cliente: %s | Valor: %s | Tipo: %s | Por: %s",
            payment.id, client.name, amount, payment_type, user.username,
        )
        return payment

    @staticmethod
    def update(*, payment, client, date, amount, payment_type, user, description='') -> Payment:
        """Altera um pagamento e refaz o lançamento no extrato."""
        amount = quantize_money(amount)
        if amount is None or amount <= 0:
            raise ValidationError("O valor do pagamento deve ser maior que zero.")

        with transaction.atomic():
            payment = Payment.objects.select_for_update().get(pk=payment.pk)
            payment.client = client
            payment.date = date
            payment.amount = amount
            payment.payment_type = payment_type
            payment.description = description or ''
            payment.save()

            PaymentService._sync_financial_entry(payment, user)

        logger.warning(
            "[PAGAMENTO] Editado %s | Cliente: %s | Valor: %s | Por: %s",
            payment.id, client.name, amount, user.username,
        )
        return payment

    @staticmethod
    def delete(*, payment, user, reason='', ip_address=None) -> dict:
        """
        Apaga um pagamento, registrando antes o retrato dele no log de
        exclusões (a única trilha que sobra depois).
        """
        with transaction.atomic():
            payment = (
                Payment.objects
                .select_for_update()
                .select_related('client')
                .get(pk=payment.pk)
            )

            resumo = {
                'cliente': payment.client.name,
                'data': payment.date,
                'valor': payment.amount,
            }

            FinanceDeletionLog.objects.create(
                object_type=DeletedObjectType.PAGAMENTO,
                object_id=payment.id,
                client=payment.client,
                object_date=payment.date,
                amount=payment.amount,
                snapshot={
                    'pagamento': {
                        'id': str(payment.id),
                        'data': payment.date.isoformat(),
                        'cliente': payment.client.name,
                        'cliente_id': str(payment.client_id),
                        'valor': str(payment.amount),
                        'tipo': payment.payment_type,
                        'tipo_label': payment.get_payment_type_display(),
                        'descricao': payment.description,
                        'registrado_por': payment.created_by.username,
                        'registrado_em': (
                            payment.created_at.isoformat() if payment.created_at else None
                        ),
                    },
                },
                reason=reason or '',
                deleted_by=user,
                ip_address=ip_address,
            )

            payment.entries.all().delete()
            payment.delete()

        logger.warning(
            "[PAGAMENTO] APAGADO | Cliente: %s | Data: %s | Valor: %s | "
            "Por: %s | Motivo: %s",
            resumo['cliente'], resumo['data'], resumo['valor'],
            user.username, reason or '(não informado)',
        )
        return resumo

    @staticmethod
    def _sync_financial_entry(payment, user) -> None:
        """Um pagamento = um crédito. Refaz do zero para manter a coerência."""
        payment.entries.all().delete()
        FinancialEntry.objects.create(
            client=payment.client,
            date=payment.date,
            entry_type=EntryType.CREDITO,
            amount=payment.amount,
            source_type=EntrySource.PAGAMENTO,
            payment=payment,
            description=payment.description or payment.get_payment_type_display(),
            created_by=user,
        )


class AdjustmentService:
    """
    Ajustes manuais de saldo.

    Um ajuste é um lançamento avulso no extrato, sem venda nem pagamento por
    trás — serve para corrigir um erro antigo, perdoar uma dívida ou lançar um
    acerto combinado fora do sistema. A descrição é obrigatória justamente
    porque não existe documento de origem para consultar depois.
    """

    @staticmethod
    def create(*, client, date, entry_type, amount, description, user) -> FinancialEntry:
        amount = quantize_money(amount)
        if amount is None or amount <= 0:
            raise ValidationError("O valor do ajuste deve ser maior que zero.")
        if not (description or '').strip():
            raise ValidationError("Descreva o motivo do ajuste.")
        if entry_type not in (EntryType.DEBITO, EntryType.CREDITO):
            raise ValidationError("Selecione se o ajuste é um débito ou um crédito.")

        entry = FinancialEntry.objects.create(
            client=client,
            date=date,
            entry_type=entry_type,
            amount=amount,
            source_type=EntrySource.AJUSTE,
            description=description.strip(),
            created_by=user,
        )
        logger.warning(
            "[AJUSTE] Criado %s | Cliente: %s | %s de %s | Por: %s | Motivo: %s",
            entry.id, client.name, entry_type, amount, user.username, description,
        )
        return entry

    @staticmethod
    def update(*, entry, client, date, entry_type, amount, description, user) -> FinancialEntry:
        if entry.source_type != EntrySource.AJUSTE:
            raise ValidationError(
                "Somente ajustes manuais podem ser editados por aqui. "
                "Para alterar uma venda ou um pagamento, use a tela correspondente."
            )
        amount = quantize_money(amount)
        if amount is None or amount <= 0:
            raise ValidationError("O valor do ajuste deve ser maior que zero.")
        if not (description or '').strip():
            raise ValidationError("Descreva o motivo do ajuste.")

        entry.client = client
        entry.date = date
        entry.entry_type = entry_type
        entry.amount = amount
        entry.description = description.strip()
        entry.save(update_fields=[
            'client', 'date', 'entry_type', 'amount', 'description',
        ])
        logger.warning("[AJUSTE] Editado %s | Por: %s", entry.id, user.username)
        return entry

    @staticmethod
    def delete(*, entry, user, reason='', ip_address=None) -> dict:
        if entry.source_type != EntrySource.AJUSTE:
            raise ValidationError(
                "Somente ajustes manuais podem ser apagados por aqui."
            )

        with transaction.atomic():
            resumo = {
                'cliente': entry.client.name,
                'data': entry.date,
                'valor': entry.amount,
            }
            FinanceDeletionLog.objects.create(
                object_type=DeletedObjectType.AJUSTE,
                object_id=entry.id,
                client=entry.client,
                object_date=entry.date,
                amount=entry.amount,
                snapshot={
                    'ajuste': {
                        'id': str(entry.id),
                        'data': entry.date.isoformat(),
                        'cliente': entry.client.name,
                        'cliente_id': str(entry.client_id),
                        'natureza': entry.entry_type,
                        'valor': str(entry.amount),
                        'descricao': entry.description,
                        'registrado_por': entry.created_by.username,
                    },
                },
                reason=reason or '',
                deleted_by=user,
                ip_address=ip_address,
            )
            entry.delete()

        logger.warning(
            "[AJUSTE] APAGADO | Cliente: %s | Valor: %s | Por: %s",
            resumo['cliente'], resumo['valor'], user.username,
        )
        return resumo
