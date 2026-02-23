/**
 * Máscaras de input com formatação automática
 * Versão unificada e otimizada
 * Suporta: CPF, CNPJ (dinâmico), Telefone, Peso
 */

(function() {
    'use strict';

    // ═══════════════════════════════════════════════════════════
    // MÁSCARA DE CPF/CNPJ DINÂMICA
    // ═══════════════════════════════════════════════════════════
    
    function maskCPFouCNPJ(input) {
        input.addEventListener('input', function() {
            let v = this.value.replace(/\D/g, '');
            
            if (v.length <= 11) {
                // CPF: 000.000.000-00
                v = v.slice(0, 11);
                if (v.length > 9)      v = v.replace(/^(\d{3})(\d{3})(\d{3})(\d{0,2})/, '$1.$2.$3-$4');
                else if (v.length > 6) v = v.replace(/^(\d{3})(\d{3})(\d{0,3})/, '$1.$2.$3');
                else if (v.length > 3) v = v.replace(/^(\d{3})(\d{0,3})/, '$1.$2');
            } else {
                // CNPJ: 00.000.000/0000-00
                v = v.slice(0, 14);
                if (v.length > 12)     v = v.replace(/^(\d{2})(\d{3})(\d{3})(\d{4})(\d{0,2})/, '$1.$2.$3/$4-$5');
                else if (v.length > 8) v = v.replace(/^(\d{2})(\d{3})(\d{3})(\d{0,4})/, '$1.$2.$3/$4');
                else if (v.length > 5) v = v.replace(/^(\d{2})(\d{3})(\d{0,3})/, '$1.$2.$3');
                else if (v.length > 2) v = v.replace(/^(\d{2})(\d{0,3})/, '$1.$2');
            }
            
            this.value = v;
        });
    }

    // ═══════════════════════════════════════════════════════════
    // MÁSCARA DE TELEFONE
    // ═══════════════════════════════════════════════════════════
    
    function maskPhone(input) {
        input.addEventListener('input', function() {
            let v = this.value.replace(/\D/g, '').slice(0, 11);
            
            if (v.length > 6) {
                // (00) 00000-0000 ou (00) 0000-0000
                v = v.replace(/^(\d{2})(\d{4,5})(\d{0,4})/, '($1) $2-$3');
            } else if (v.length > 2) {
                v = v.replace(/^(\d{2})(\d{0,5})/, '($1) $2');
            } else if (v.length > 0) {
                v = v.replace(/^(\d{0,2})/, '($1');
            }
            
            this.value = v;
        });
    }

    // ═══════════════════════════════════════════════════════════
    // MÁSCARA DE PESO
    // ═══════════════════════════════════════════════════════════
    
    function maskPeso(input) {
        input.addEventListener('input', function() {
            let v = this.value.replace(/\D/g, '');
            
            if (v) {
                v = (parseInt(v) / 100).toFixed(2);
                v = v.replace('.', ',');
            }
            
            this.value = v;
        });
    }

    function maskWeight(input) {
        input.addEventListener('input', function() {
            let v = this.value.replace(/[^\d,\.]/g, '');
            // Permite apenas números e um ponto/vírgula decimal
            const parts = v.split(/[,\.]/);
            if (parts.length > 2) {
                v = parts[0] + '.' + parts.slice(1).join('');
            }
            this.value = v;
        });
        
        input.addEventListener('blur', function() {
            const val = parseFloat(this.value.replace(',', '.'));
            if (!isNaN(val)) {
                this.value = val.toFixed(3);
            }
        });
    }

    // ═══════════════════════════════════════════════════════════
    // INICIALIZAÇÃO
    // ═══════════════════════════════════════════════════════════
    
    function initMasks() {
        // CPF/CNPJ dinâmico
        document.querySelectorAll('[data-mask="cpf-cnpj"]').forEach(maskCPFouCNPJ);
        
        // Telefone
        document.querySelectorAll('[data-mask="phone"]').forEach(maskPhone);
        
        // Peso (formato simples com vírgula)
        document.querySelectorAll('[data-mask="peso"]').forEach(maskPeso);
        
        // Weight (formato decimal com 3 casas)
        document.querySelectorAll('[data-mask="weight"]').forEach(maskWeight);
        
        // Aplicar máscaras em campos já preenchidos (modo edição)
        document.querySelectorAll('[data-mask="cpf-cnpj"], [data-mask="phone"]').forEach(function(input) {
            if (input.value) {
                input.dispatchEvent(new Event('input', { bubbles: true }));
            }
        });
    }

    // Executar quando o DOM estiver pronto
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initMasks);
    } else {
        initMasks();
    }

})();