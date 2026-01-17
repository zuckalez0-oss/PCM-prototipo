from django import forms
from django.contrib.auth.models import User
# IMPORTANTE: AQUI ESTAVA O ERRO. É PRECISO IMPORTAR O MODELO PlanoPreventivo
from .models import Atividade, PlanoPreventivo 

class AtividadeForm(forms.ModelForm):
    # Campos extras não vinculados diretamente ao model (para UX)
    tempo_valor = forms.IntegerField(label="Duração", initial=1, required=False)
    tempo_unidade = forms.ChoiceField(
        choices=[('horas', 'Horas'), ('dias', 'Dias')],
        label="Unidade",
        initial='horas',
        required=False
    )
    colaboradores = forms.ModelMultipleChoiceField(
        queryset=User.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=False
    )

    class Meta:
        model = Atividade
        fields = ['maquina', 'descricao', 'data_planejada', 'eh_preventiva', 'procedimento_base', 'eh_emergencial']
        widgets = {
            'data_planejada': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
            'maquina': forms.Select(attrs={'class': 'form-select'}),
            'descricao': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'procedimento_base': forms.Select(attrs={'class': 'form-select'}),
            'eh_preventiva': forms.CheckboxInput(attrs={'class': 'form-check-input', 'role': 'switch'}),
        }

# --- A CLASSE QUE ESTAVA FALTANDO ---
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