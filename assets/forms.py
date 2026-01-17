from django import forms
from .models import Atividade, ProcedimentoPreventivo
from django.contrib.auth.models import User

from .models import Atividade, PlanoPreventivo




class AtividadeForm(forms.ModelForm):
    # Campos extras para cálculo de tempo
    tempo_valor = forms.IntegerField(
        label="Quantidade", 
        initial=2, 
        widget=forms.NumberInput(attrs={'class': 'form-control'})
    )
    tempo_unidade = forms.ChoiceField(
        label="Unidade",
        choices=[('horas', 'Horas'), ('dias', 'Dias')],
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    class Meta:
        model = Atividade
        # Atualizado: 'colaboradores' no plural
        fields = [
            'maquina', 'descricao', 'colaboradores', 'data_planejada', 
            'eh_preventiva', 'procedimento_base', 'eh_emergencial'
        ]
        widgets = {
            'maquina': forms.Select(attrs={'class': 'form-select'}),
            'descricao': forms.TextInput(attrs={'class': 'form-control'}),
            # NOVIDADE: SelectMultiple permite selecionar vários com CTRL pressionado
            'colaboradores': forms.SelectMultiple(attrs={
                'class': 'form-select', 
                'style': 'height: 120px;'
            }),
            'data_planejada': forms.DateTimeInput(attrs={
                'class': 'form-control', 
                'type': 'datetime-local'
            }),
            'eh_preventiva': forms.CheckboxInput(attrs={
                'class': 'form-check-input', 
                'id': 'checkPreventiva'
            }),
            'procedimento_base': forms.Select(attrs={
                'class': 'form-select', 
                'id': 'selectPreventiva'
            }),
            'eh_emergencial': forms.CheckboxInput(attrs={
                'class': 'form-check-input', 
                'id': 'id_eh_emergencial'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['descricao'].required = False
        # Define o rótulo amigável para o campo de múltiplos técnicos
        self.fields['colaboradores'].label = "Técnicos Responsáveis (Segure Ctrl para selecionar vários)"


    class PlanoPreventivoForm(forms.ModelForm):
        class Meta:
            model = PlanoPreventivo
            fields = ['nome', 'maquina', 'frequencia_dias', 'proxima_data', 'procedimento_padrao']
            widgets = {
                'nome': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: Lubrificação Quinzenal'}),
                'maquina': forms.Select(attrs={'class': 'form-select'}),
                'frequencia_dias': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Dias'}),
                'proxima_data': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
                'procedimento_padrao': forms.Select(attrs={'class': 'form-select'}),
        }    