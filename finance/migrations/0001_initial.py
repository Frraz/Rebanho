"""
Migração inicial do módulo financeiro.

ADITIVA: cria apenas tabelas novas. Nenhuma tabela existente é alterada, então
o deploy é seguro e reversível — `migrate finance zero` desfaz tudo sem tocar
em nada do sistema atual.

Escrita à mão (o ambiente de desenvolvimento não tem Django instalado). Todos
os índices têm nome explícito justamente para que o
`makemigrations --check --dry-run` do pipeline consiga confirmar que esta
migração corresponde exatamente aos modelos.
"""
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import simple_history.models
import uuid


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("farms", "0001_initial"),
        ("inventory", "0005_timestamp_datefield_only"),
        ("operations", "0001_initial"),
    ]

    operations = [
        # ══════════════════════════════════════════════════════════════════
        # VENDA
        # ══════════════════════════════════════════════════════════════════
        migrations.CreateModel(
            name="Sale",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        help_text="Identificador único universal",
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "date",
                    models.DateField(
                        db_index=True,
                        help_text="Data em que a venda foi realizada",
                        verbose_name="Data da Venda",
                    ),
                ),
                ("notes", models.TextField(blank=True, default="", verbose_name="Observação")),
                (
                    "status",
                    models.CharField(
                        choices=[("ATIVA", "Ativa"), ("CANCELADA", "Cancelada")],
                        db_index=True,
                        default="ATIVA",
                        max_length=10,
                        verbose_name="Situação",
                    ),
                ),
                (
                    "total_quantity",
                    models.PositiveIntegerField(
                        default=0,
                        help_text="Soma das quantidades de todos os lotes",
                        verbose_name="Quantidade Total",
                    ),
                ),
                (
                    "total_weight",
                    models.DecimalField(
                        blank=True,
                        decimal_places=2,
                        help_text="Soma dos pesos de todos os lotes",
                        max_digits=12,
                        null=True,
                        verbose_name="Peso Total (kg)",
                    ),
                ),
                (
                    "total_amount",
                    models.DecimalField(
                        blank=True,
                        decimal_places=2,
                        help_text=(
                            "Soma dos valores dos lotes. Vazio quando a venda foi "
                            "registrada sem informar preço — o valor pode ser "
                            "preenchido depois."
                        ),
                        max_digits=14,
                        null=True,
                        verbose_name="Preço Total (R$)",
                    ),
                ),
                (
                    "origin",
                    models.CharField(
                        choices=[
                            ("APP", "Cadastrada no sistema"),
                            ("BACKFILL", "Importada do histórico"),
                        ],
                        db_index=True,
                        default="APP",
                        help_text=(
                            "BACKFILL identifica vendas criadas pela migração de "
                            "dados a partir do ledger antigo. É o que torna a "
                            "migração reversível com segurança."
                        ),
                        max_length=10,
                        verbose_name="Origem do Registro",
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True, verbose_name="Data de Registro"),
                ),
                (
                    "updated_at",
                    models.DateTimeField(auto_now=True, verbose_name="Última Atualização"),
                ),
                (
                    "client",
                    models.ForeignKey(
                        help_text="Cliente que comprou os animais",
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="sales",
                        to="operations.client",
                        verbose_name="Cliente",
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="sales_created",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Registrado Por",
                    ),
                ),
                (
                    "farm",
                    models.ForeignKey(
                        help_text="Fazenda de onde saíram os animais (uma por venda)",
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="sales",
                        to="farms.farm",
                        verbose_name="Fazenda",
                    ),
                ),
            ],
            options={
                "verbose_name": "Venda",
                "verbose_name_plural": "Vendas",
                "db_table": "sales",
                "ordering": ["-date", "-created_at"],
            },
        ),
        # ══════════════════════════════════════════════════════════════════
        # PAGAMENTO
        # ══════════════════════════════════════════════════════════════════
        migrations.CreateModel(
            name="Payment",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4, editable=False, primary_key=True, serialize=False
                    ),
                ),
                ("date", models.DateField(db_index=True, verbose_name="Data do Pagamento")),
                (
                    "amount",
                    models.DecimalField(
                        decimal_places=2, max_digits=14, verbose_name="Valor (R$)"
                    ),
                ),
                (
                    "payment_type",
                    models.CharField(
                        choices=[
                            ("DINHEIRO", "Dinheiro"),
                            ("PIX", "Pix"),
                            ("TRANSFERENCIA", "Transferência"),
                            ("CHEQUE", "Cheque"),
                            ("DEPOSITO", "Depósito"),
                            ("OUTROS", "Outros"),
                        ],
                        default="DINHEIRO",
                        max_length=20,
                        verbose_name="Tipo de Pagamento",
                    ),
                ),
                (
                    "description",
                    models.TextField(
                        blank=True, default="", help_text="Opcional", verbose_name="Descrição"
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True, verbose_name="Data de Registro"),
                ),
                (
                    "updated_at",
                    models.DateTimeField(auto_now=True, verbose_name="Última Atualização"),
                ),
                (
                    "client",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="payments",
                        to="operations.client",
                        verbose_name="Cliente",
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="payments_created",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Registrado Por",
                    ),
                ),
            ],
            options={
                "verbose_name": "Pagamento",
                "verbose_name_plural": "Pagamentos",
                "db_table": "payments",
                "ordering": ["-date", "-created_at"],
            },
        ),
        # ══════════════════════════════════════════════════════════════════
        # LOTE DA VENDA
        # ══════════════════════════════════════════════════════════════════
        migrations.CreateModel(
            name="SaleItem",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4, editable=False, primary_key=True, serialize=False
                    ),
                ),
                (
                    "quantity",
                    models.PositiveIntegerField(
                        help_text="Número de animais neste lote", verbose_name="Quantidade"
                    ),
                ),
                (
                    "total_weight",
                    models.DecimalField(
                        blank=True,
                        decimal_places=2,
                        max_digits=12,
                        null=True,
                        verbose_name="Peso Total (kg)",
                    ),
                ),
                (
                    "price_per_kg",
                    models.DecimalField(
                        blank=True,
                        decimal_places=4,
                        help_text="Quatro casas decimais para não perder precisão no rateio",
                        max_digits=12,
                        null=True,
                        verbose_name="Preço por kg (R$)",
                    ),
                ),
                (
                    "total_amount",
                    models.DecimalField(
                        blank=True,
                        decimal_places=2,
                        help_text=(
                            "Peso × preço por kg, mas editável: o usuário pode "
                            "sobrescrever para arredondamentos ou valores combinados."
                        ),
                        max_digits=14,
                        null=True,
                        verbose_name="Total (R$)",
                    ),
                ),
                (
                    "line_order",
                    models.PositiveSmallIntegerField(
                        default=0,
                        help_text="Preserva a ordem em que o usuário digitou os lotes",
                        verbose_name="Ordem",
                    ),
                ),
                (
                    "animal_category",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="sale_items",
                        to="inventory.animalcategory",
                        verbose_name="Tipo de Animal",
                    ),
                ),
                (
                    "movement",
                    models.OneToOneField(
                        blank=True,
                        help_text="Baixa de estoque gerada por este lote",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="sale_item",
                        to="inventory.animalmovement",
                        verbose_name="Movimentação de Estoque",
                    ),
                ),
                (
                    "sale",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="items",
                        to="finance.sale",
                        verbose_name="Venda",
                    ),
                ),
            ],
            options={
                "verbose_name": "Lote da Venda",
                "verbose_name_plural": "Lotes da Venda",
                "db_table": "sale_items",
                "ordering": ["line_order", "id"],
            },
        ),
        # ══════════════════════════════════════════════════════════════════
        # LANÇAMENTO FINANCEIRO (extrato do cliente)
        # ══════════════════════════════════════════════════════════════════
        migrations.CreateModel(
            name="FinancialEntry",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4, editable=False, primary_key=True, serialize=False
                    ),
                ),
                (
                    "date",
                    models.DateField(
                        db_index=True,
                        help_text="Data do fato gerador (venda, pagamento ou ajuste)",
                        verbose_name="Data",
                    ),
                ),
                (
                    "entry_type",
                    models.CharField(
                        choices=[("DEBITO", "Débito"), ("CREDITO", "Crédito")],
                        max_length=10,
                        verbose_name="Natureza",
                    ),
                ),
                (
                    "amount",
                    models.DecimalField(
                        decimal_places=2,
                        help_text="Sempre positivo — quem dá o sinal é o campo Natureza",
                        max_digits=14,
                        verbose_name="Valor (R$)",
                    ),
                ),
                (
                    "source_type",
                    models.CharField(
                        choices=[
                            ("VENDA", "Venda"),
                            ("PAGAMENTO", "Pagamento"),
                            ("AJUSTE", "Ajuste manual"),
                        ],
                        max_length=12,
                        verbose_name="Origem",
                    ),
                ),
                (
                    "description",
                    models.TextField(
                        blank=True,
                        default="",
                        help_text="Obrigatória nos ajustes manuais",
                        verbose_name="Descrição",
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True, verbose_name="Data de Registro"),
                ),
                (
                    "client",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="financial_entries",
                        to="operations.client",
                        verbose_name="Cliente",
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="financial_entries_created",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Registrado Por",
                    ),
                ),
                (
                    "payment",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="entries",
                        to="finance.payment",
                        verbose_name="Pagamento de Origem",
                    ),
                ),
                (
                    "sale",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="entries",
                        to="finance.sale",
                        verbose_name="Venda de Origem",
                    ),
                ),
            ],
            options={
                "verbose_name": "Lançamento Financeiro",
                "verbose_name_plural": "Lançamentos Financeiros",
                "db_table": "financial_entries",
                "ordering": ["-date", "-created_at"],
            },
        ),
        # ══════════════════════════════════════════════════════════════════
        # LOG DE EXCLUSÕES
        # ══════════════════════════════════════════════════════════════════
        migrations.CreateModel(
            name="FinanceDeletionLog",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4, editable=False, primary_key=True, serialize=False
                    ),
                ),
                (
                    "object_type",
                    models.CharField(
                        choices=[
                            ("VENDA", "Venda"),
                            ("PAGAMENTO", "Pagamento"),
                            ("AJUSTE", "Ajuste manual"),
                        ],
                        max_length=12,
                        verbose_name="Tipo de Registro",
                    ),
                ),
                (
                    "object_id",
                    models.UUIDField(db_index=True, verbose_name="ID do Registro Apagado"),
                ),
                (
                    "object_date",
                    models.DateField(
                        help_text="Data da venda/pagamento, não a data da exclusão",
                        verbose_name="Data do Registro Apagado",
                    ),
                ),
                (
                    "amount",
                    models.DecimalField(
                        blank=True,
                        decimal_places=2,
                        max_digits=14,
                        null=True,
                        verbose_name="Valor (R$)",
                    ),
                ),
                (
                    "snapshot",
                    models.JSONField(
                        default=dict,
                        help_text=(
                            "Estado integral do registro no momento da exclusão: "
                            "cabeçalho, lotes, lançamentos financeiros e IDs das "
                            "movimentações de estoque."
                        ),
                        verbose_name="Retrato Completo",
                    ),
                ),
                ("reason", models.TextField(blank=True, default="", verbose_name="Motivo")),
                (
                    "deleted_at",
                    models.DateTimeField(
                        auto_now_add=True, db_index=True, verbose_name="Apagado em"
                    ),
                ),
                (
                    "ip_address",
                    models.GenericIPAddressField(
                        blank=True, null=True, verbose_name="Endereço IP"
                    ),
                ),
                (
                    "client",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="finance_deletions",
                        to="operations.client",
                        verbose_name="Cliente",
                    ),
                ),
                (
                    "deleted_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="finance_deletions",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Apagado Por",
                    ),
                ),
            ],
            options={
                "verbose_name": "Exclusão Financeira",
                "verbose_name_plural": "Exclusões Financeiras",
                "db_table": "finance_deletion_logs",
                "ordering": ["-deleted_at"],
            },
        ),
        # ══════════════════════════════════════════════════════════════════
        # HISTÓRICO (django-simple-history)
        # ══════════════════════════════════════════════════════════════════
        migrations.CreateModel(
            name="HistoricalSale",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        db_index=True,
                        default=uuid.uuid4,
                        editable=False,
                        help_text="Identificador único universal",
                    ),
                ),
                (
                    "date",
                    models.DateField(
                        db_index=True,
                        help_text="Data em que a venda foi realizada",
                        verbose_name="Data da Venda",
                    ),
                ),
                ("notes", models.TextField(blank=True, default="", verbose_name="Observação")),
                (
                    "status",
                    models.CharField(
                        choices=[("ATIVA", "Ativa"), ("CANCELADA", "Cancelada")],
                        db_index=True,
                        default="ATIVA",
                        max_length=10,
                        verbose_name="Situação",
                    ),
                ),
                (
                    "total_quantity",
                    models.PositiveIntegerField(
                        default=0,
                        help_text="Soma das quantidades de todos os lotes",
                        verbose_name="Quantidade Total",
                    ),
                ),
                (
                    "total_weight",
                    models.DecimalField(
                        blank=True,
                        decimal_places=2,
                        help_text="Soma dos pesos de todos os lotes",
                        max_digits=12,
                        null=True,
                        verbose_name="Peso Total (kg)",
                    ),
                ),
                (
                    "total_amount",
                    models.DecimalField(
                        blank=True,
                        decimal_places=2,
                        help_text=(
                            "Soma dos valores dos lotes. Vazio quando a venda foi "
                            "registrada sem informar preço — o valor pode ser "
                            "preenchido depois."
                        ),
                        max_digits=14,
                        null=True,
                        verbose_name="Preço Total (R$)",
                    ),
                ),
                (
                    "origin",
                    models.CharField(
                        choices=[
                            ("APP", "Cadastrada no sistema"),
                            ("BACKFILL", "Importada do histórico"),
                        ],
                        db_index=True,
                        default="APP",
                        help_text=(
                            "BACKFILL identifica vendas criadas pela migração de "
                            "dados a partir do ledger antigo. É o que torna a "
                            "migração reversível com segurança."
                        ),
                        max_length=10,
                        verbose_name="Origem do Registro",
                    ),
                ),
                ("history_id", models.AutoField(primary_key=True, serialize=False)),
                ("history_date", models.DateTimeField(db_index=True)),
                ("history_change_reason", models.CharField(max_length=100, null=True)),
                (
                    "history_type",
                    models.CharField(
                        choices=[("+", "Created"), ("~", "Changed"), ("-", "Deleted")],
                        max_length=1,
                    ),
                ),
                (
                    "client",
                    models.ForeignKey(
                        blank=True,
                        db_constraint=False,
                        help_text="Cliente que comprou os animais",
                        null=True,
                        on_delete=django.db.models.deletion.DO_NOTHING,
                        related_name="+",
                        to="operations.client",
                        verbose_name="Cliente",
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        db_constraint=False,
                        null=True,
                        on_delete=django.db.models.deletion.DO_NOTHING,
                        related_name="+",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Registrado Por",
                    ),
                ),
                (
                    "farm",
                    models.ForeignKey(
                        blank=True,
                        db_constraint=False,
                        help_text="Fazenda de onde saíram os animais (uma por venda)",
                        null=True,
                        on_delete=django.db.models.deletion.DO_NOTHING,
                        related_name="+",
                        to="farms.farm",
                        verbose_name="Fazenda",
                    ),
                ),
                (
                    "history_user",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "historical Venda",
                "verbose_name_plural": "historical Vendas",
                "ordering": ("-history_date", "-history_id"),
                "get_latest_by": ("history_date", "history_id"),
            },
            bases=(simple_history.models.HistoricalChanges, models.Model),
        ),
        migrations.CreateModel(
            name="HistoricalPayment",
            fields=[
                (
                    "id",
                    models.UUIDField(db_index=True, default=uuid.uuid4, editable=False),
                ),
                ("date", models.DateField(db_index=True, verbose_name="Data do Pagamento")),
                (
                    "amount",
                    models.DecimalField(
                        decimal_places=2, max_digits=14, verbose_name="Valor (R$)"
                    ),
                ),
                (
                    "payment_type",
                    models.CharField(
                        choices=[
                            ("DINHEIRO", "Dinheiro"),
                            ("PIX", "Pix"),
                            ("TRANSFERENCIA", "Transferência"),
                            ("CHEQUE", "Cheque"),
                            ("DEPOSITO", "Depósito"),
                            ("OUTROS", "Outros"),
                        ],
                        default="DINHEIRO",
                        max_length=20,
                        verbose_name="Tipo de Pagamento",
                    ),
                ),
                (
                    "description",
                    models.TextField(
                        blank=True, default="", help_text="Opcional", verbose_name="Descrição"
                    ),
                ),
                ("history_id", models.AutoField(primary_key=True, serialize=False)),
                ("history_date", models.DateTimeField(db_index=True)),
                ("history_change_reason", models.CharField(max_length=100, null=True)),
                (
                    "history_type",
                    models.CharField(
                        choices=[("+", "Created"), ("~", "Changed"), ("-", "Deleted")],
                        max_length=1,
                    ),
                ),
                (
                    "client",
                    models.ForeignKey(
                        blank=True,
                        db_constraint=False,
                        null=True,
                        on_delete=django.db.models.deletion.DO_NOTHING,
                        related_name="+",
                        to="operations.client",
                        verbose_name="Cliente",
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        db_constraint=False,
                        null=True,
                        on_delete=django.db.models.deletion.DO_NOTHING,
                        related_name="+",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Registrado Por",
                    ),
                ),
                (
                    "history_user",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "historical Pagamento",
                "verbose_name_plural": "historical Pagamentos",
                "ordering": ("-history_date", "-history_id"),
                "get_latest_by": ("history_date", "history_id"),
            },
            bases=(simple_history.models.HistoricalChanges, models.Model),
        ),
        # ══════════════════════════════════════════════════════════════════
        # ÍNDICES E CONSTRAINTS
        # ══════════════════════════════════════════════════════════════════
        migrations.AddIndex(
            model_name="sale",
            index=models.Index(fields=["client", "-date"], name="fin_sale_client_date_idx"),
        ),
        migrations.AddIndex(
            model_name="sale",
            index=models.Index(fields=["farm", "-date"], name="fin_sale_farm_date_idx"),
        ),
        migrations.AddIndex(
            model_name="sale",
            index=models.Index(fields=["status", "-date"], name="fin_sale_status_date_idx"),
        ),
        migrations.AddIndex(
            model_name="sale",
            index=models.Index(
                fields=["-date", "-created_at"], name="fin_sale_date_created_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="saleitem",
            index=models.Index(
                fields=["sale", "line_order"], name="fin_saleitem_sale_ord_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="saleitem",
            index=models.Index(
                fields=["animal_category"], name="fin_saleitem_category_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="payment",
            index=models.Index(fields=["client", "-date"], name="fin_pay_client_date_idx"),
        ),
        migrations.AddIndex(
            model_name="payment",
            index=models.Index(
                fields=["-date", "-created_at"], name="fin_pay_date_created_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="payment",
            index=models.Index(fields=["payment_type"], name="fin_pay_type_idx"),
        ),
        migrations.AddIndex(
            model_name="financialentry",
            index=models.Index(fields=["client", "-date"], name="fin_entry_client_date_idx"),
        ),
        migrations.AddIndex(
            model_name="financialentry",
            index=models.Index(
                fields=["client", "entry_type"], name="fin_entry_client_type_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="financialentry",
            index=models.Index(
                fields=["-date", "-created_at"], name="fin_entry_date_created_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="financialentry",
            index=models.Index(
                fields=["source_type", "-date"], name="fin_entry_source_date_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="financedeletionlog",
            index=models.Index(fields=["-deleted_at"], name="fin_del_deleted_at_idx"),
        ),
        migrations.AddIndex(
            model_name="financedeletionlog",
            index=models.Index(
                fields=["object_type", "-deleted_at"], name="fin_del_type_date_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="financedeletionlog",
            index=models.Index(
                fields=["client", "-deleted_at"], name="fin_del_client_date_idx"
            ),
        ),
        migrations.AddConstraint(
            model_name="financialentry",
            constraint=models.CheckConstraint(
                check=models.Q(("amount__gt", 0)),
                name="financial_entry_amount_positive",
            ),
        ),
        migrations.AddConstraint(
            model_name="financialentry",
            constraint=models.CheckConstraint(
                check=models.Q(
                    models.Q(
                        ("payment__isnull", True),
                        ("sale__isnull", False),
                        ("source_type", "VENDA"),
                    ),
                    models.Q(
                        ("payment__isnull", False),
                        ("sale__isnull", True),
                        ("source_type", "PAGAMENTO"),
                    ),
                    models.Q(
                        ("payment__isnull", True),
                        ("sale__isnull", True),
                        ("source_type", "AJUSTE"),
                    ),
                    _connector="OR",
                ),
                name="financial_entry_source_consistent",
            ),
        ),
    ]
