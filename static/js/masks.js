/**
 * Máscaras de input puras em JavaScript.
 * Sem dependências externas.
 */

// CPF: 000.000.000-00
function maskCPF(input) {
    input.addEventListener('input', function () {
        let v = this.value.replace(/\D/g, '').slice(0, 11);
        if (v.length > 9)      v = v.replace(/^(\d{3})(\d{3})(\d{3})(\d{0,2})/, '$1.$2.$3-$4');
        else if (v.length > 6) v = v.replace(/^(\d{3})(\d{3})(\d{0,3})/, '$1.$2.$3');
        else if (v.length > 3) v = v.replace(/^(\d{3})(\d{0,3})/, '$1.$2');
        this.value = v;
    });
}

// CNPJ: 00.000.000/0000-00
function maskCNPJ(input) {
    input.addEventListener('input', function () {
        let v = this.value.replace(/\D/g, '').slice(0, 14);
        if (v.length > 12)      v = v.replace(/^(\d{2})(\d{3})(\d{3})(\d{4})(\d{0,2})/, '$1.$2.$3/$4-$5');
        else if (v.length > 8)  v = v.replace(/^(\d{2})(\d{3})(\d{3})(\d{0,4})/, '$1.$2.$3/$4');
        else if (v.length > 5)  v = v.replace(/^(\d{2})(\d{3})(\d{0,3})/, '$1.$2.$3');
        else if (v.length > 2)  v = v.replace(/^(\d{2})(\d{0,3})/, '$1.$2');
        this.value = v;
    });
}

// CPF ou CNPJ automático
function maskCPFouCNPJ(input) {
    input.addEventListener('input', function () {
        let v = this.value.replace(/\D/g, '');
        if (v.length <= 11) {
            v = v.slice(0, 11);
            if (v.length > 9)      v = v.replace(/^(\d{3})(\d{3})(\d{3})(\d{0,2})/, '$1.$2.$3-$4');
            else if (v.length > 6) v = v.replace(/^(\d{3})(\d{3})(\d{0,3})/, '$1.$2.$3');
            else if (v.length > 3) v = v.replace(/^(\d{3})(\d{0,3})/, '$1.$2');
        } else {
            v = v.slice(0, 14);
            if (v.length > 12)      v = v.replace(/^(\d{2})(\d{3})(\d{3})(\d{4})(\d{0,2})/, '$1.$2.$3/$4-$5');
            else if (v.length > 8)  v = v.replace(/^(\d{2})(\d{3})(\d{3})(\d{0,4})/, '$1.$2.$3/$4');
            else if (v.length > 5)  v = v.replace(/^(\d{2})(\d{3})(\d{0,3})/, '$1.$2.$3');
            else if (v.length > 2)  v = v.replace(/^(\d{2})(\d{0,3})/, '$1.$2');
        }
        this.value = v;
    });
}

// Telefone: (00) 00000-0000
function maskPhone(input) {
    input.addEventListener('input', function () {
        let v = this.value.replace(/\D/g, '').slice(0, 11);
        if (v.length > 6) v = v.replace(/^(\d{2})(\d{4,5})(\d{0,4})/, '($1) $2-$3');
        else if (v.length > 2) v = v.replace(/^(\d{2})(\d{0,5})/, '($1) $2');
        else if (v.length > 0) v = v.replace(/^(\d{0,2})/, '($1');
        this.value = v;
    });
}

// Peso: 0.000,000 kg
function maskWeight(input) {
    input.addEventListener('input', function () {
        let v = this.value.replace(/[^\d,\.]/g, '');
        // Permite apenas números e um ponto/vírgula decimal
        const parts = v.split(/[,\.]/);
        if (parts.length > 2) {
            v = parts[0] + '.' + parts.slice(1).join('');
        }
        this.value = v;
    });
    input.addEventListener('blur', function () {
        const val = parseFloat(this.value.replace(',', '.'));
        if (!isNaN(val)) {
            this.value = val.toFixed(3);
        }
    });
}

// Inicializar máscaras por atributo data-mask
document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('[data-mask="cpf"]').forEach(maskCPF);
    document.querySelectorAll('[data-mask="cnpj"]').forEach(maskCNPJ);
    document.querySelectorAll('[data-mask="cpf-cnpj"]').forEach(maskCPFouCNPJ);
    document.querySelectorAll('[data-mask="phone"]').forEach(maskPhone);
    document.querySelectorAll('[data-mask="weight"]').forEach(maskWeight);
});