from django.shortcuts import render, redirect, get_object_or_404  # Adicionado: redirect e get_object_or_404
from django.http import HttpResponse, JsonResponse
from django.utils import timezone  # Adicionado: timezone para as datas
from datetime import timedelta     # Adicionado: timedelta para cálculos de tempo
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.models import User
from django.contrib import messages 
# Importe o sistema de mensagens
from django.contrib.auth.decorators import login_required

# Importe o novo modelo Chamado aqui
from .models import Atividade, Maquina, ProcedimentoPreventivo, Chamado 

# Importe o formulário e a função de sequenciamento
from .forms import AtividadeForm
from .utils import sequenciar_atividades

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
    
    chamados_pendentes = Chamado.objects.filter(status='pendente').order_by('-prioridade_indicada')
    # Atividades que NÃO estão finalizadas vão para a "Fila de Trabalho"
    atividades_pendentes = [a for a in atividades_sequenciadas if a.status != 'finalizada' and a.status != 'cancelada']
    
    # Atividades finalizadas vão para o "Histórico"
    atividades_concluidas = [a for a in atividades_sequenciadas if a.status == 'finalizada']
    
    # NOVO: Buscar todos os usuários (técnicos) para o dropdown de triagem
    tecnicos = User.objects.all()
    
    return render(request, 'assets/lista_ativos.html', {
        'atividades': atividades_pendentes, 
        'atividades_concluidas': atividades_concluidas,
        'chamados_pendentes': chamados_pendentes,
        'tecnicos': tecnicos,
        'form': form
    })

def recusar_chamado(request, chamado_id):
    if request.method == 'POST':
        chamado = get_object_or_404(Chamado, id=chamado_id)
        motivo = request.POST.get('motivo')
        chamado.motivo_resposta = motivo
        chamado.status = 'recusado'
        chamado.save()
        messages.warning(request, f"Chamado #{chamado.id} recusado.")
    return redirect('lista_atividades')

def cancelar_atividade(request, atividade_id):
    if request.method == 'POST':
        atividade = get_object_or_404(Atividade, id=atividade_id)
        motivo = request.POST.get('motivo')
        atividade.motivo_cancelamento = motivo
        atividade.status = 'cancelada'
        atividade.save()
    return redirect('lista_atividades')

@csrf_exempt
def alterar_status(request, atividade_id, novo_status):
    """
    Gerencia o cronômetro de tempo real via HTMX.
    """
    atividade = get_object_or_404(Atividade, id=atividade_id)
    
    # REGRA DE NEGÓCIO: Não pode finalizar ou iniciar sem técnico
    if novo_status in ['executando', 'finalizada'] and not atividade.colaborador:
        return HttpResponse(
            f'<script>alert("AÇÃO INVÁLIDA: Atribua um técnico à OS #{atividade.id} antes de prosseguir!");</script>'
            f'<span id="status-badge-{atividade.id}" class="status-badge status-{atividade.status}">{atividade.get_status_display()}</span>'
        )

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
# ---------------------------------------------
@login_required
def abrir_chamado(request):
    if request.method == 'POST':
        maquina_id = request.POST.get('maquina')
        descricao = request.POST.get('descricao')
        prioridade = request.POST.get('prioridade')
        parada = request.POST.get('maquina_parada') == 'on'

        Chamado.objects.create(
            maquina_id=maquina_id,
            requisitante=request.user,
            descricao_problema=descricao,
            prioridade_indicada=prioridade,
            maquina_parada=parada
        )
        # CORREÇÃO: Em vez de 'sucesso_chamado', manda para a mesma página com um alerta
        messages.success(request, "Chamado registrado com sucesso! A equipe de PCM foi notificada.")
        return redirect('abrir_chamado') 

    maquinas = Maquina.objects.all()
    return render(request, 'assets/abrir_chamado.html', {'maquinas': maquinas})
# ---------------------------------------------

def aprovar_chamado(request, chamado_id):
    if request.method == 'POST':
        chamado = get_object_or_404(Chamado, id=chamado_id)
        tecnico_id = request.POST.get('tecnico')
        
        if not tecnico_id:
            messages.error(request, "Selecione um técnico para aprovar o chamado.")
            return redirect('lista_atividades')

        # Cria a OS já com o técnico
        Atividade.objects.create(
            maquina=chamado.maquina,
            colaborador_id=tecnico_id, # Atribui o técnico escolhido
            descricao=f"CHAMADO #{chamado.id}: {chamado.descricao_problema[:50]}",
            data_planejada=timezone.now(),
            duracao_estimada=timedelta(hours=2),
            status='aberta'
        )
        
        chamado.status = 'aprovado'
        chamado.save()
        messages.success(request, "Chamado aprovado e OS gerada!")
    return redirect('lista_atividades')

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
    