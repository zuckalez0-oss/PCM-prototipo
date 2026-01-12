from datetime import timedelta
from django.utils import timezone

def formatar_duracao(td):
    """Converte timedelta para uma string amigável (ex: 2d 4h ou 5h)"""
    dias = td.days
    horas = td.seconds // 3600
    if dias > 0:
        return f"{dias}d {horas}h" if horas > 0 else f"{dias}d"
    return f"{horas}h"

def sequenciar_atividades(atividades_queryset):
    """Lógica central que empilha as atividades por colaborador"""
    colaboradores = {}
    atividades_sequenciadas = []

    # Ordenar: Emergencial primeiro, depois por data planejada
    atividades_ordenadas = atividades_queryset.order_by('-eh_emergencial', 'data_planejada')

    for act in atividades_ordenadas:
        tecnico_id = act.colaborador.id if act.colaborador else 0
        
        # Se o técnico ainda não tem "cursor" de tempo, começa na data planejada da OS ou Agora
        if tecnico_id not in colaboradores:
            colaboradores[tecnico_id] = act.data_planejada if act.data_planejada else timezone.now()

        # Início é onde o cursor do técnico parou
        # Mas se a data planejada da OS for no futuro em relação ao cursor, usa a planejada
        inicio_efetivo = max(act.data_planejada, colaboradores[tecnico_id]) if act.data_planejada else colaboradores[tecnico_id]
        
        # Se for emergencial, ela "fura a fila" e começa na sua data planejada
        if act.eh_emergencial and act.data_planejada:
            inicio_efetivo = act.data_planejada

        duracao = act.duracao_estimada if act.duracao_estimada else timedelta(hours=1)
        fim_efetivo = inicio_efetivo + duracao

        # Atualiza o cursor do técnico para a próxima atividade
        colaboradores[tecnico_id] = fim_efetivo

        # Adiciona os dados calculados ao objeto (sem salvar no banco, apenas para exibição)
        act.inicio_calculado = inicio_efetivo
        act.fim_calculado = fim_efetivo
        act.duracao_formatada = formatar_duracao(duracao)
        atividades_sequenciadas.append(act)

    return atividades_sequenciadas