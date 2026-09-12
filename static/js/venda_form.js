/**
 * venda_form.js — Formulário de venda com vários tipos de animal.
 *
 * ─────────────────────────────────────────────────────────────────────────────
 * COMO AS LINHAS FUNCIONAM
 *
 * As linhas vêm de um formset do Django. O template renderiza o `empty_form`
 * dentro de um <template id="modelo-linha">, com o prefixo literal `__prefix__`
 * nos nomes e ids. Ao adicionar um lote, clonamos esse modelo, trocamos
 * `__prefix__` pelo próximo índice e incrementamos o TOTAL_FORMS do
 * management form — é o padrão do Django para formsets dinâmicos, sem
 * biblioteca nenhuma.
 *
 * Duas coisas precisam acontecer logo depois de clonar:
 *   1. aplicar as máscaras decimais na linha nova (RebanhoMasks.init)
 *   2. preencher o select de tipo de animal com as categorias da fazenda
 *
 * ─────────────────────────────────────────────────────────────────────────────
 * POR QUE AS CATEGORIAS VÊM POR JSON
 *
 * O endpoint antigo do sistema (/htmx/categorias-saida/) devolve <option> e
 * escreve num alvo de id fixo — serve para um formulário de uma linha só. Aqui
 * são N linhas precisando da MESMA lista, então buscamos uma vez em JSON e
 * preenchemos todas. De quebra, o JSON traz o saldo disponível, que é o que
 * permite avisar na tela quando a soma das quantidades passa do estoque.
 *
 * ─────────────────────────────────────────────────────────────────────────────
 * O CAMPO "TOTAL" É CALCULADO, MAS EDITÁVEL
 *
 * Enquanto o usuário não mexer nele, o total segue peso × preço/kg. No momento
 * em que ele digita ali, a linha é marcada como "manual" e paramos de
 * sobrescrever — é o que permite arredondar ou registrar um valor combinado.
 */

function formularioVenda(config) {
    return {
        enviando: false,
        categorias: [],
        excessos: [],
        totalAnimais: 0,
        totalPeso: 0,
        totalValor: 0,

        // ── Ciclo de vida ───────────────────────────────────────────────

        iniciar: function () {
            var self = this;
            var corpo = document.getElementById('linhas-venda');

            // Um listener no corpo da tabela atende também as linhas criadas
            // depois — não é preciso religar nada a cada clone.
            corpo.addEventListener('input', function (e) { self.aoDigitar(e); });
            corpo.addEventListener('change', function (e) { self.aoDigitar(e); });

            if (config.fazendaInicial) {
                this.carregarCategorias(config.fazendaInicial);
            }
            this.recalcular();
        },

        // ── Categorias da fazenda ───────────────────────────────────────

        carregarCategorias: function (fazendaId) {
            var self = this;

            if (!fazendaId) {
                this.categorias = [];
                this.preencherSelects();
                this.recalcular();
                return;
            }

            fetch(config.categoriasUrl + '?farm=' + encodeURIComponent(fazendaId), {
                headers: { 'X-Requested-With': 'XMLHttpRequest' },
                credentials: 'same-origin'
            })
                .then(function (r) { return r.ok ? r.json() : { categorias: [] }; })
                .then(function (dados) {
                    self.categorias = dados.categorias || [];
                    self.preencherSelects();
                    self.recalcular();
                })
                .catch(function () {
                    // Falha de rede não pode travar o formulário: mantemos as
                    // opções que já estavam na tela e deixamos o servidor
                    // validar o estoque no envio.
                    self.categorias = [];
                });
        },

        preencherSelects: function () {
            var self = this;
            var selects = document.querySelectorAll('#linhas-venda .campo-categoria');

            selects.forEach(function (select) {
                var escolhido = select.value;
                select.innerHTML = '';

                var vazio = document.createElement('option');
                vazio.value = '';
                vazio.textContent = self.categorias.length
                    ? 'Selecione o tipo...'
                    : 'Escolha a fazenda primeiro';
                select.appendChild(vazio);

                self.categorias.forEach(function (cat) {
                    var opt = document.createElement('option');
                    opt.value = cat.id;
                    opt.textContent = cat.nome + ' (disponível: ' + cat.disponivel + ')';
                    select.appendChild(opt);
                });

                // Preserva a escolha anterior — importante na edição e quando o
                // formulário volta com erro de validação.
                if (escolhido) {
                    select.value = escolhido;
                    if (!select.value) {
                        // A categoria escolhida não tem mais saldo nesta fazenda.
                        // Mantemos a opção para o usuário ver o que estava lá.
                        var orfa = document.createElement('option');
                        orfa.value = escolhido;
                        orfa.textContent = 'Tipo sem saldo nesta fazenda';
                        select.appendChild(orfa);
                        select.value = escolhido;
                    }
                }
            });
        },

        // ── Linhas ──────────────────────────────────────────────────────

        adicionarLinha: function () {
            var totalInput = document.querySelector('[name="itens-TOTAL_FORMS"]');
            var indice = parseInt(totalInput.value, 10);

            var modelo = document.getElementById('modelo-linha');
            var html = modelo.innerHTML.replace(/__prefix__/g, indice);

            var temp = document.createElement('tbody');
            temp.innerHTML = html.trim();
            var linha = temp.querySelector('tr');

            document.getElementById('linhas-venda').appendChild(linha);
            totalInput.value = indice + 1;

            // Sem isto, a linha nova fica sem máscara decimal: o masks.js só
            // se inicializa no carregamento da página e após trocas do HTMX.
            if (window.RebanhoMasks) {
                window.RebanhoMasks.init(linha);
            }

            this.preencherSelects();
            this.recalcular();

            var primeiro = linha.querySelector('.campo-categoria');
            if (primeiro) primeiro.focus();
        },

        removerLinha: function (evento) {
            var linha = evento.target.closest('tr');
            var corpo = document.getElementById('linhas-venda');
            var visiveis = corpo.querySelectorAll('tr.linha-lote:not([data-removida])');

            if (visiveis.length <= 1) {
                // A venda precisa de pelo menos um lote. Em vez de remover,
                // limpamos os campos.
                linha.querySelectorAll('input:not([type=hidden]), select').forEach(function (campo) {
                    campo.value = '';
                    delete campo.dataset.manual;
                });
                this.recalcular();
                return;
            }

            var marcarRemocao = linha.querySelector('input[name$="-DELETE"]');
            if (marcarRemocao) {
                // Linha que já existe no servidor: marca para exclusão e some
                // da tela, mas continua no POST para o Django saber.
                marcarRemocao.checked = true;
                linha.style.display = 'none';
                linha.setAttribute('data-removida', '1');
            } else {
                linha.remove();
            }

            this.recalcular();
        },

        // ── Cálculo ─────────────────────────────────────────────────────

        aoDigitar: function (evento) {
            var campo = evento.target;

            // Assim que o usuário digita no Total, ele passa a mandar na linha.
            if (campo.classList && campo.classList.contains('campo-total')) {
                campo.dataset.manual = '1';
            }

            this.recalcular();
        },

        recalcular: function () {
            var M = window.RebanhoMasks;
            var linhas = document.querySelectorAll('#linhas-venda tr.linha-lote:not([data-removida])');

            var animais = 0;
            var peso = 0;
            var valor = 0;
            var porCategoria = {};

            linhas.forEach(function (linha) {
                var selCategoria = linha.querySelector('.campo-categoria');
                var inpQtd = linha.querySelector('.campo-quantidade');
                var inpPeso = linha.querySelector('.campo-peso');
                var inpPrecoKg = linha.querySelector('.campo-preco-kg');
                var inpTotal = linha.querySelector('.campo-total');

                var qtd = parseInt(inpQtd && inpQtd.value, 10) || 0;
                var pesoLinha = (M && inpPeso) ? (M.parse(inpPeso.value) || 0) : 0;
                var precoKg = (M && inpPrecoKg) ? (M.parse(inpPrecoKg.value) || 0) : 0;

                // Total sugerido, a menos que o usuário tenha assumido o campo.
                if (inpTotal && !inpTotal.dataset.manual) {
                    if (pesoLinha > 0 && precoKg > 0) {
                        inpTotal.value = M ? M.format(pesoLinha * precoKg) : '';
                    } else {
                        inpTotal.value = '';
                    }
                }

                var totalLinha = (M && inpTotal) ? (M.parse(inpTotal.value) || 0) : 0;

                animais += qtd;
                peso += pesoLinha;
                valor += totalLinha;

                if (selCategoria && selCategoria.value && qtd > 0) {
                    porCategoria[selCategoria.value] =
                        (porCategoria[selCategoria.value] || 0) + qtd;
                }
            });

            this.totalAnimais = animais;
            this.totalPeso = peso;
            this.totalValor = valor;
            this.excessos = this.conferirEstoque(porCategoria);
        },

        /**
         * Compara a SOMA das quantidades por categoria com o saldo disponível.
         *
         * Somar é o ponto: a mesma categoria pode aparecer em várias linhas, e
         * conferir linha a linha deixaria passar uma venda que no total estoura
         * o estoque. Aqui é só aviso na tela — quem recusa de fato é o
         * servidor, que segura o saldo travado enquanto grava.
         */
        conferirEstoque: function (porCategoria) {
            var self = this;
            var avisos = [];

            Object.keys(porCategoria).forEach(function (id) {
                var cat = self.categorias.find(function (c) { return c.id === id; });
                if (!cat) return;
                var pedido = porCategoria[id];
                if (pedido > cat.disponivel) {
                    avisos.push(
                        'Você somou ' + pedido + ' ' + cat.nome +
                        ', mas há apenas ' + cat.disponivel + ' em estoque nesta fazenda.'
                    );
                }
            });

            return avisos;
        }
    };
}
