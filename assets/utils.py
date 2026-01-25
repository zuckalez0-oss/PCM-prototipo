from datetime import timedelta
from django.utils import timezone

def formatar_duracao(td):
    """Converte timedelta para uma string amigável (ex: 2d 4h 5m ou 5h 30m)"""
    if not td or td.total_seconds() == 0:
        return "0m"
    
    total_seconds = int(td.total_seconds())
    days = total_seconds // (24 * 3600)
    total_seconds = total_seconds % (24 * 3600)
    hours = total_seconds // 3600
    total_seconds = total_seconds % 3600
    minutes = total_seconds // 60
    
    parts = []
    if days > 0:
        parts.append(f"{days}d")
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0 or not parts:
        parts.append(f"{minutes}m")
        
    return " ".join(parts)

def sequenciar_atividades(atividades_queryset):
    """
    Lógica central que empilha as atividades por colaborador.
    Adaptado para Multiple colaboradores e Tempo Decimal (H.H).
    """
    colaboradores_progresso = {}
    atividades_sequenciadas = []

    # Ordenar: Emergencial primeiro (prioridade máxima), depois por data planejada
    atividades_ordenadas = atividades_queryset.order_by('-eh_emergencial', 'data_planejada')

    for act in atividades_ordenadas:
        # --- CÁLCULO DO TEMPO REAL DECIMAL (PADRÃO DE MERCADO) ---
        if act.tempo_total_gasto:
            total_segundos = act.tempo_total_gasto.total_seconds()
            # Converte segundos para horas com 2 casas decimais
            act.tempo_decimal = round(total_segundos / 3600, 2)
        else:
            act.tempo_decimal = 0.00
        
        act.tempo_gasto_formatado = formatar_duracao(act.tempo_total_gasto)

        # --- SEGURANÇA DE DADOS ---
        data_base = act.data_planejada if act.data_planejada else timezone.now()
        duracao = act.duracao_estimada if act.duracao_estimada and act.duracao_estimada.total_seconds() > 0 else timedelta(hours=1)
        
        # --- LÓGICA DE SEQUENCIAMENTO POR TÉCNICO ---
        tecnicos = act.colaboradores.all()
        
        if tecnicos.exists():
            # Para fins de sequenciamento no gráfico, usamos o "primeiro" técnico como âncora
            tecnico_principal = tecnicos.first()
            tecnico_id = tecnico_principal.id
            
            if tecnico_id not in colaboradores_progresso:
                colaboradores_progresso[tecnico_id] = data_base

            inicio_efetivo = max(data_base, colaboradores_progresso[tecnico_id])
            
            if act.eh_emergencial:
                inicio_efetivo = data_base

            fim_efetivo = inicio_efetivo + duracao
            
            # --- NOVO: Acompanhamento em tempo real para atividades em execução ---
            if act.status == 'executando':
                agora = timezone.now()
                # Puxar para o presente se estava no futuro
                if inicio_efetivo > agora:
                    inicio_efetivo = agora
                
                # Garantir que o fim também seja no mínimo "agora"
                fim_efetivo = max(inicio_efetivo + duracao, agora)
                    
            colaboradores_progresso[tecnico_id] = fim_efetivo
        
        else:
            inicio_efetivo = data_base
            fim_efetivo = inicio_efetivo + duracao
            
            # --- NOVO: Acompanhamento em tempo real (mesmo sem técnico atribuído) ---
            if act.status == 'executando':
                agora = timezone.now()
                # Puxar para o presente se estava no futuro
                if inicio_efetivo > agora:
                    inicio_efetivo = agora
                    
                # Garantir que o fim também seja no mínimo "agora"
                fim_efetivo = max(inicio_efetivo + duracao, agora)

        # --- ANEXA OS DADOS CALCULADOS AO OBJETO ---
        act.inicio_calculado = inicio_efetivo
        act.fim_calculado = fim_efetivo
        act.duracao_formatada = formatar_duracao(duracao)
        
        atividades_sequenciadas.append(act)

    return atividades_sequenciadas