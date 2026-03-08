/**
 * masks.js — Máscaras de input para o sistema Rebanho
 * Versão 2.0
 *
 * Tipos suportados via atributo data-mask:
 *
 *   data-mask="cpf-cnpj"  → CPF (000.000.000-00) ou CNPJ (00.000.000/0000-00) automático
 *   data-mask="phone"     → Telefone: (00) 00000-0000
 *   data-mask="decimal"   → Decimal pt-BR com milhar: 1.250,80
 *
 * ─────────────────────────────────────────────────────────────────────────────
 * POR QUE data-mask="decimal" e não type="number"?
 *
 *   O browser proíbe vírgula em <input type="number">. Com USE_L10N=True e
 *   máscaras pt-BR, o valor é silenciosamente descartado antes de chegar ao
 *   Django. A solução correta é:
 *
 *     <input type="text" data-mask="decimal" inputmode="decimal" ...>
 *
 *   O campo envia "1.250,80" ao Django e o clean_*() do form normaliza
 *   para Decimal. Nunca use type="number" com máscara de moeda ou peso.
 *
 * ─────────────────────────────────────────────────────────────────────────────
 * PROBLEMAS CORRIGIDOS vs versão anterior:
 *
 *   ✗ maskPeso dividia por 100 automaticamente: "1250" virava "12,50"
 *   ✗ maskWeight usava toFixed(3) com ponto decimal (formato inglês)
 *   ✗ Sem separador de milhar
 *   ✗ Sem reforço para HTMX (htmx:afterSwap)
 *   ✗ Sem formatação de valores já salvos no modo edição
 *   ✗ Sem blur completando casas decimais faltando
 *   ✗ Sem focus selecionando o conteúdo inteiro
 */

(function () {
    'use strict';

    // ═══════════════════════════════════════════════════════════
    // INICIALIZAÇÃO
    // ═══════════════════════════════════════════════════════════

    function initMasks(root) {
        root = root || document;

        // Aplica cada máscara por tipo, evitando duplicar listeners
        root.querySelectorAll('[data-mask="cpf-cnpj"]').forEach(function (el) {
            if (el._maskApplied) return;
            el._maskApplied = true;
            maskCpfCnpj(el);
            if (el.value) el.dispatchEvent(new Event('input', { bubbles: true }));
        });

        root.querySelectorAll('[data-mask="phone"]').forEach(function (el) {
            if (el._maskApplied) return;
            el._maskApplied = true;
            maskPhone(el);
            if (el.value) el.dispatchEvent(new Event('input', { bubbles: true }));
        });

        root.querySelectorAll('[data-mask="decimal"]').forEach(function (el) {
            if (el._maskApplied) return;
            el._maskApplied = true;
            maskDecimal(el);
            // Formata valor já existente (campo pré-preenchido em edição)
            if (el.value) {
                el.value = toDisplayFormat(normalizeExistingValue(el.value));
            }
        });
    }

    // Inicializa ao carregar a página
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function () { initMasks(document); });
    } else {
        initMasks(document);
    }

    // Re-inicializa sempre que HTMX injeta conteúdo novo na página
    document.addEventListener('htmx:afterSwap', function (e) {
        if (e.detail && e.detail.target) {
            initMasks(e.detail.target);
        }
    });


    // ═══════════════════════════════════════════════════════════
    // DECIMAL PT-BR  (peso, preço — principal correção)
    // ═══════════════════════════════════════════════════════════

    /**
     * Aplica máscara de número decimal pt-BR em um <input type="text">.
     *
     * Comportamento ao digitar:
     *   "1"           → "1"
     *   "12"          → "12"
     *   "1250"        → "1.250"
     *   "1250,"       → "1.250,"
     *   "1250,8"      → "1.250,8"
     *   "1250,80"     → "1.250,80"
     *   "1250,801"    → "1.250,80"  ← limita a 2 casas
     *   "12345678,99" → "12.345.678,99"
     *
     * Ao perder foco (blur):
     *   "1.250,"      → "1.250,00"
     *   "1.250,8"     → "1.250,80"
     *   "1.250"       → "1.250"     ← sem vírgula: deixa como inteiro
     */
    function maskDecimal(el) {

        el.addEventListener('input', function () {
            var caret = el.selectionStart;
            var prevLen = el.value.length;

            el.value = toDisplayFormat(toCleanString(el.value));

            // Reposiciona o cursor proporcionalmente após reformatação
            var diff = el.value.length - prevLen;
            var newPos = caret + diff;
            if (newPos < 0) newPos = 0;
            try { el.setSelectionRange(newPos, newPos); } catch (e) {}
        });

        // Completa casas decimais ao sair do campo
        el.addEventListener('blur', function () {
            if (!el.value) return;
            var comma = el.value.indexOf(',');
            if (comma === -1) return; // sem vírgula: deixa como está
            var dec = el.value.substring(comma + 1);
            if (dec.length === 0) el.value = el.value + '00';
            else if (dec.length === 1) el.value = el.value + '0';
        });

        // Seleciona tudo ao focar: facilita apagar e redigitar
        el.addEventListener('focus', function () {
            setTimeout(function () { el.select(); }, 10);
        });
    }

    /**
     * Remove formatação e retorna string interna limpa.
     * Remove pontos de milhar, mantém no máximo uma vírgula e 2 casas decimais.
     *
     * "1.250,80"  → "1250,80"
     * "1.250,801" → "1250,80"
     * "1.250"     → "1250"
     * "abc1.2x"   → "12"
     */
    function toCleanString(value) {
        // Remove tudo que não seja dígito ou vírgula
        var raw = String(value).replace(/[^\d,]/g, '');

        // Garante somente uma vírgula: mantém a primeira, descarta o resto
        var firstComma = raw.indexOf(',');
        if (firstComma !== -1) {
            var intPart  = raw.substring(0, firstComma);
            var decPart  = raw.substring(firstComma + 1).replace(/,/g, '').substring(0, 2);
            // Remove zeros à esquerda da parte inteira (exceto "0" sozinho)
            intPart = intPart.replace(/^0+(?=\d)/, '') || '0';
            raw = intPart + ',' + decPart;
        } else {
            raw = raw.replace(/^0+(?=\d)/, '') || raw;
        }

        return raw;
    }

    /**
     * Formata string limpa para exibição pt-BR com separador de milhar.
     *
     * "1250,80"  → "1.250,80"
     * "1250"     → "1.250"
     * ""         → ""
     */
    function toDisplayFormat(clean) {
        if (!clean) return '';

        var comma = clean.indexOf(',');
        var intPart, decPart;

        if (comma !== -1) {
            intPart = clean.substring(0, comma);
            decPart = clean.substring(comma + 1);
        } else {
            intPart = clean;
            decPart = null;
        }

        // Insere ponto a cada 3 dígitos da direita para a esquerda
        intPart = intPart.replace(/\B(?=(\d{3})+(?!\d))/g, '.');

        return decPart !== null ? intPart + ',' + decPart : intPart;
    }

    /**
     * Normaliza um valor já salvo no banco para o formato interno (limpo).
     * Usado ao carregar campos pré-preenchidos no modo edição.
     *
     * Casos que podem vir do backend:
     *   "1250.80"   → Decimal Python com ponto  → interno: "1250,80"
     *   "1.250,80"  → Já formatado pt-BR         → interno: "1250,80"
     *   "1.250"     → Milhar pt-BR sem decimal   → interno: "1250"
     *   "1250"      → Inteiro puro               → interno: "1250"
     *   "0"         → Zero                        → interno: "0"
     */
    function normalizeExistingValue(value) {
        if (!value) return '';
        value = String(value).trim();

        // Tem vírgula: já é pt-BR — remove apenas os pontos de milhar
        if (value.indexOf(',') !== -1) {
            return value.replace(/\./g, '');
        }

        // Tem ponto e sem vírgula: distingue milhar de decimal inglês
        if (value.indexOf('.') !== -1) {
            var parts = value.split('.');
            // "1250.80": ponto decimal inglês (parte após ponto tem 1 ou 2 dígitos)
            if (parts.length === 2 && parts[1].length >= 1 && parts[1].length <= 2) {
                return parts[0] + ',' + parts[1]; // → "1250,80"
            }
            // "1.250" ou "1.250.000": milhar pt-BR → remove pontos
            return value.replace(/\./g, ''); // → "1250"
        }

        // Só dígitos: retorna como está
        return value;
    }


    // ═══════════════════════════════════════════════════════════
    // CPF / CNPJ DINÂMICO
    // ═══════════════════════════════════════════════════════════

    function maskCpfCnpj(el) {
        el.addEventListener('input', function () {
            var v = el.value.replace(/\D/g, '');

            if (v.length <= 11) {
                // CPF: 000.000.000-00
                v = v.slice(0, 11);
                if      (v.length > 9) v = v.replace(/^(\d{3})(\d{3})(\d{3})(\d{0,2})/,       '$1.$2.$3-$4');
                else if (v.length > 6) v = v.replace(/^(\d{3})(\d{3})(\d{0,3})/,               '$1.$2.$3');
                else if (v.length > 3) v = v.replace(/^(\d{3})(\d{0,3})/,                       '$1.$2');
            } else {
                // CNPJ: 00.000.000/0000-00
                v = v.slice(0, 14);
                if      (v.length > 12) v = v.replace(/^(\d{2})(\d{3})(\d{3})(\d{4})(\d{0,2})/, '$1.$2.$3/$4-$5');
                else if (v.length > 8)  v = v.replace(/^(\d{2})(\d{3})(\d{3})(\d{0,4})/,        '$1.$2.$3/$4');
                else if (v.length > 5)  v = v.replace(/^(\d{2})(\d{3})(\d{0,3})/,                '$1.$2.$3');
                else if (v.length > 2)  v = v.replace(/^(\d{2})(\d{0,3})/,                        '$1.$2');
            }

            el.value = v;
        });
    }


    // ═══════════════════════════════════════════════════════════
    // TELEFONE
    // ═══════════════════════════════════════════════════════════

    function maskPhone(el) {
        el.addEventListener('input', function () {
            var v = el.value.replace(/\D/g, '').slice(0, 11);

            if      (v.length > 6) v = v.replace(/^(\d{2})(\d{4,5})(\d{0,4})/, '($1) $2-$3');
            else if (v.length > 2) v = v.replace(/^(\d{2})(\d{0,5})/,           '($1) $2');
            else if (v.length > 0) v = v.replace(/^(\d{0,2})/,                   '($1');

            el.value = v;
        });
    }

}());