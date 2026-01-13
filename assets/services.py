from django.db.models import Sum
from datetime import timedelta
from . import Atividade


def calcular_proxima_disponibilidade(colaborador):
    """Calcula a próxima disponibilidade de um colaborador com base nas atividades atribuídas."""
    atividades_ativas = Atividade.objects.filter(colaborador=colaborador, status_in=['aberta','executando','pausada'])

    tempo_total = atividades_ativas.aggregate(total=Sum('duracao_estimada'))['total'] or timedelta(0)

    return tempo_total