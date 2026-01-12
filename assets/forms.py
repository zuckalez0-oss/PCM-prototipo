from django import forms
from .models import Atividade, ProcedimentoPreventivo
from datetime import timedelta

class AtividadeForm(forms.ModelForm):
    # Campos extras para facilitar a vida do usuário
    tempo_valor = forms.IntegerField(label="Quantidade", initial=2, widget=forms.NumberInput(attrs={'class': 'form-control'}))
    tempo_unidade = forms.ChoiceField(
        label="Unidade",
        choices=[('horas', 'Horas'), ('dias', 'Dias')],
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    class Meta:
        model = Atividade
        fields = ['maquina', 'descricao', 'colaborador', 'data_planejada', 'eh_preventiva', 'procedimento_base','eh_preventiva', 'procedimento_base', 'eh_emergencial' ]
        widgets = {
            'maquina': forms.Select(attrs={'class': 'form-select'}),
            'descricao': forms.TextInput(attrs={'class': 'form-control'}),
            'colaborador': forms.Select(attrs={'class': 'form-select'}),
            'data_planejada': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'eh_preventiva': forms.CheckboxInput(attrs={'class': 'form-check-input', 'id': 'checkPreventiva'}),
            'procedimento_base': forms.Select(attrs={'class': 'form-select', 'id': 'selectPreventiva'}),
            'eh_emergencial': forms.CheckboxInput(attrs={'class': 'form-check-input', 'id': 'id_eh_emergencial'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['descricao'].required = False