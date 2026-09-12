"""
finance/models/financial_entry.py

O extrato do cliente. Toda origem de dinheiro — venda, pagamento, ajuste
manual — vira uma linha aqui, e o saldo do cliente é a soma desta tabela.

POR QUE UM LEDGER ÚNICO EM VEZ DE SOMAR AS TABELAS DE ORIGEM:
    O relatório de Fluxo Financeiro precisa ordenar venda, pagamento e ajuste
    numa linha do tempo só, e filtrar por crédito/débito. Fazer isso com UNION
    de três tabelas de formatos diferentes seria frágil; com um ledger, vira
    uma consulta simples e indexada.

POR QUE NÃO EXISTE TABELA DE SALDO (SNAPSHOT):
    O saldo é sempre `Σ créditos − Σ débitos` calculado na hora. Como vendas e
    pagamentos podem ser editados e apagados, um snapshot divergiria em
    silêncio — o mesmo problema que já obrigou este projeto a manter um
    script de reconciliação de estoque. Ver finance/services/balance_service.py.

SINAL DO SALDO (combinado com o cliente):
    negativo = o cliente deve
    zero     = quitado
    positivo = o cliente tem crédito a favor (pagou adiantado ou a mais)
"""
import uuid

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import models

from .enums import EntrySource, EntryType

User = get_user_model()


class FinancialEntry(models.Model):
    """Lançamento de débito ou crédito no extrato de um cliente."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    client = models.ForeignKey(
        'operations.Client',
        on_delete=models.PROTECT,
        related_name='financial_entries',
        verbose_name="Cliente",
    )

    date = models.DateField(
        verbose_name="Data",
        db_index=True,
        help_text="Data do fato gerador (venda, pagamento ou ajuste)",
    )

    entry_type = models.CharField(
        max_length=10,
        choices=EntryType.choices,
        verbose_name="Natureza",
    )

    amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        verbose_name="Valor (R$)",
        help_text="Sempre positivo — quem dá o sinal é o campo Natureza",
    )

    source_type = models.CharField(
        max_length=12,
        choices=EntrySource.choices,
        verbose_name="Origem",
    )

    sale = models.ForeignKey(
        'finance.Sale',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='entries',
        verbose_name="Venda de Origem",
    )

    payment = models.ForeignKey(
        'finance.Payment',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='entries',
        verbose_name="Pagamento de Origem",
    )

    description = models.TextField(
        blank=True,
        default='',
        verbose_name="Descrição",
        help_text="Obrigatória nos ajustes manuais",
    )

    created_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='financial_entries_created',
        verbose_name="Registrado Por",
    )

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Data de Registro")

    class Meta:
        db_table = 'financial_entries'
        verbose_name = 'Lançamento Financeiro'
        verbose_name_plural = 'Lançamentos Financeiros'
        ordering = ['-date', '-created_at']
        indexes = [
            models.Index(fields=['client', '-date'], name='fin_entry_client_date_idx'),
            models.Index(fields=['client', 'entry_type'], name='fin_entry_client_type_idx'),
            models.Index(fields=['-date', '-created_at'], name='fin_entry_date_created_idx'),
            models.Index(fields=['source_type', '-date'], name='fin_entry_source_date_idx'),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(amount__gt=0),
                name='financial_entry_amount_positive',
            ),
            # Um lançamento tem exatamente uma origem, e a FK preenchida tem
            # que bater com o `source_type` declarado. Uma constraint só cobre
            # as duas regras e impede estados impossíveis (ex.: um lançamento
            # apontando ao mesmo tempo para uma venda e um pagamento).
            models.CheckConstraint(
                check=(
                    models.Q(source_type='VENDA', sale__isnull=False, payment__isnull=True)
                    | models.Q(source_type='PAGAMENTO', sale__isnull=True, payment__isnull=False)
                    | models.Q(source_type='AJUSTE', sale__isnull=True, payment__isnull=True)
                ),
                name='financial_entry_source_consistent',
            ),
        ]

    def __str__(self):
        sinal = '-' if self.entry_type == EntryType.DEBITO else '+'
        return f"{self.date:%d/%m/%Y} {self.client.name} {sinal}R$ {self.amount}"

    def clean(self):
        super().clean()
        if self.amount is not None and self.amount <= 0:
            raise ValidationError({
                'amount': 'O valor deve ser maior que zero. Use a Natureza para indicar o sinal.'
            })
        if self.source_type == EntrySource.AJUSTE and not (self.description or '').strip():
            raise ValidationError({
                'description': 'Ajustes manuais exigem uma descrição explicando o motivo.'
            })

    @property
    def signed_amount(self):
        """Valor com sinal: crédito soma, débito subtrai."""
        return self.amount if self.entry_type == EntryType.CREDITO else -self.amount
