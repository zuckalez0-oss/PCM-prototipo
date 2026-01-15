from datetime import timedelta
from django.utils import timezone

def formatar_duracao(td):
    """Converte timedelta para uma string amigável (ex: 2d 4h ou 5h)"""
    if not td:
        return "0h"
    
    dias = td.days
    horas = td.seconds // 3600
    
    if dias > 0:
        return f"{dias}d {horas}h" if horas > 0 else f"{dias}d"
    return f"{horas}h"

def sequenciar_atividades(atividades_queryset):
    """
    Lógica central que empilha as atividades por colaborador.
    Adaptado para Multiple colaboradores.
    """
    colaboradores_progresso = {}
    atividades_sequenciadas = []

    # Ordenar: Emergencial primeiro (prioridade máxima), depois por data planejada
    atividades_ordenadas = atividades_queryset.order_by('-eh_emergencial', 'data_planejada')

    for act in atividades_ordenadas:
        # --- SEGURANÇA DE DADOS ---
        data_base = act.data_planejada if act.data_planejada else timezone.now()
        duracao = act.duracao_estimada if act.duracao_estimada and act.duracao_estimada.total_seconds() > 0 else timedelta(hours=1)
        
        # --- LÓGICA DE SEQUENCIAMENTO POR TÉCNICO ---
        # Buscamos todos os técnicos associados à atividade
        tecnicos = act.colaboradores.all()
        
        if tecnicos.exists():
            # Para fins de sequenciamento no gráfico, usamos o "primeiro" técnico como âncora
            tecnico_principal = tecnicos.first()
            tecnico_id = tecnico_principal.id
            
            # Se é a primeira vez que vemos este técnico, o cursor de tempo dele começa na data da OS
            if tecnico_id not in colaboradores_progresso:
                colaboradores_progresso[tecnico_id] = data_base

            # Início é o máximo entre: Quando o técnico principal ficou livre OU a data planejada da OS
            inicio_efetivo = max(data_base, colaboradores_progresso[tecnico_id])
            
            # Se for emergencial, ela "fura a fila"
            if act.eh_emergencial:
                inicio_efetivo = data_base

            fim_efetivo = inicio_efetivo + duracao

            # Atualiza o cursor do técnico principal
            colaboradores_progresso[tecnico_id] = fim_efetivo
        
        else:
            # --- ATIVIDADES SEM TÉCNICO ---
            inicio_efetivo = data_base
            fim_efetivo = inicio_efetivo + duracao

        # --- ANEXA OS DADOS CALCULADOS AO OBJETO ---
        act.inicio_calculado = inicio_efetivo
        act.fim_calculado = fim_efetivo
        act.duracao_formatada = formatar_duracao(duracao)
        
        atividades_sequenciadas.append(act)

    return atividades_sequenciadas