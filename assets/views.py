from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, JsonResponse
from .models import Atividade, ProcedimentoPreventivo
from .forms import AtividadeForm
from django.utils import timezone
from datetime import timedelta
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Q
from django.contrib.auth.models import User

# IMPORTANTE: Certifique-se de que o arquivo utils.py existe com a função sequenciar_atividades
from .utils import sequenciar_atividades 

def lista_atividades(request):
    """
    Exibe a fila de trabalho e o histórico, separando as concluídas das demais.
    As datas são calculadas automaticamente pelo motor de sequenciamento.
    """
    if request.method == 'POST':
        form = AtividadeForm(request.POST)
        if form.is_valid():
            atividade = form.save(commit=False)
            
            # 1. Lógica de Duração Flexível
            valor = int(form.cleaned_data.get('tempo_valor', 0))
            unidade = form.cleaned_data.get('tempo_unidade', 'horas')
            
            if unidade == 'dias':
                atividade.duracao_estimada = timedelta(days=valor)
            else:
                atividade.duracao_estimada = timedelta(hours=valor)

            # 2. Lógica de Manutenção Preventiva
            if atividade.eh_preventiva and atividade.procedimento_base:
                atividade.descricao = f"PREVENTIVA: {atividade.procedimento_base.nome}"
                atividade.duracao_estimada = atividade.procedimento_base.duracao_estimada_padrao
            
            atividade.save()
            return redirect('lista_atividades')
    else:
        form = AtividadeForm()

    # BUSCA TODAS AS ATIVIDADES
    atividades_queryset = Atividade.objects.all()
    
    # CALCULANDO O SEQUENCIAMENTO (Datas de Início e Fim dinâmicas)
    atividades_sequenciadas = sequenciar_atividades(atividades_queryset)
    
    # MELHORIA: SEPARAÇÃO DAS LISTAS
    # Atividades que NÃO estão finalizadas vão para a "Fila de Trabalho"
    atividades_pendentes = [a for a in atividades_sequenciadas if a.status != 'finalizada']
    
    # Atividades finalizadas vão para o "Histórico"
    atividades_concluidas = [a for a in atividades_sequenciadas if a.status == 'finalizada']
    
    return render(request, 'assets/lista_ativos.html', {
        'atividades': atividades_pendentes, 
        'atividades_concluidas': atividades_concluidas,
        'form': form
    })

@csrf_exempt
def alterar_status(request, atividade_id, novo_status):
    """
    Gerencia o cronômetro de tempo real via HTMX.
    """
    atividade = get_object_or_404(Atividade, id=atividade_id)
    agora = timezone.now()

    if atividade.status == 'executando' and novo_status in ['pausada', 'finalizada']:
        if atividade.ultima_interacao:
            decorrido = agora - atividade.ultima_interacao
            atividade.tempo_total_gasto += decorrido
            
    if novo_status == 'executando':
        atividade.ultima_interacao = agora

    atividade.status = novo_status
    atividade.save()
    
    return HttpResponse(
        f'<span id="status-badge-{atividade.id}" class="status-badge status-{atividade.status}">'
        f'{atividade.get_status_display()}</span>'
    )

def pagina_gantt(request):
    return render(request, 'assets/gantt.html')

def dados_gantt(request):
    """
    API para o Gantt com correção na captura do nome do colaborador.
    """
    try:
        atividades_db = Atividade.objects.all()
        atividades = sequenciar_atividades(atividades_db)
        
        dados = []
        for act in atividades:
            progresso = 0
            if act.status == 'executando': progresso = 50
            elif act.status == 'finalizada': progresso = 100
            elif act.status == 'pausada': progresso = 25

            # MELHORIA: Captura robusta do nome do técnico
            tecnico_nome = "Sem Técnico"
            if act.colaborador:
                # Tenta primeiro o nome, se não tiver usa o login (username)
                tecnico_nome = act.colaborador.first_name if act.colaborador.first_name else act.colaborador.username

            dados.append({
                'id': str(act.id),
                'name': f"[{tecnico_nome}] ({act.duracao_formatada}) {act.maquina.codigo}: {act.descricao[:15]}",
                'start': act.inicio_calculado.isoformat(),
                'end': act.fim_calculado.isoformat(),
                'progress': progresso,
                'custom_class': 'gantt-emergencial' if act.eh_emergencial else f'gantt-status-{act.status}'
            })
        
        return JsonResponse(dados, safe=False)
    
    except Exception as e:
        print(f"ERRO CRÍTICO NO GANTT: {e}")
        return JsonResponse({'error': str(e)}, status=500)