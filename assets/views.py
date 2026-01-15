from django.shortcuts import render, redirect, get_object_or_404  # Adicionado: redirect e get_object_or_404
from django.http import HttpResponse, JsonResponse
from django.utils import timezone  # Adicionado: timezone para as datas
from datetime import timedelta     # Adicionado: timedelta para cálculos de tempo
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.models import User
from django.contrib import messages 
# Importe o sistema de mensagens
from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout

# Importe o novo modelo Chamado aqui
from .models import Atividade, Maquina, ProcedimentoPreventivo, Chamado 

# Importe o formulário e a função de sequenciamento
from .forms import AtividadeForm
from .utils import sequenciar_atividades

# IMPORTANTE: Certifique-se de que o arquivo utils.py existe com a função sequenciar_atividades
from .utils import sequenciar_atividades 

@login_required
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
            form.save_m2m()
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

@login_required
def recusar_chamado(request, chamado_id):
    if request.method == 'POST':
        chamado = get_object_or_404(Chamado, id=chamado_id)
        motivo = request.POST.get('motivo')
        chamado.motivo_resposta = motivo
        chamado.status = 'recusado'
        chamado.save()
        messages.warning(request, f"Chamado #{chamado.id} recusado.")
    return redirect('lista_atividades')

@login_required
def cancelar_atividade(request, atividade_id):
    if request.method == 'POST':
        atividade = get_object_or_404(Atividade, id=atividade_id)
        motivo = request.POST.get('motivo')
        atividade.motivo_cancelamento = motivo
        atividade.status = 'cancelada'
        atividade.save()
    return redirect('lista_atividades')

@csrf_exempt
@login_required
def alterar_status(request, atividade_id, novo_status):
    atividade = get_object_or_404(Atividade, id=atividade_id)
    
    # Validação de Técnicos (ManyToManyField)
    if novo_status in ['executando', 'finalizada'] and not atividade.colaboradores.exists():
        return HttpResponse(
            f'<script>alert("AÇÃO INVÁLIDA: Atribua ao menos um técnico!");</script>'
            f'<span id="status-badge-{atividade.id}" class="status-badge status-{atividade.status}">{atividade.get_status_display()}</span>'
        )

    agora = timezone.now()

    if novo_status == 'pausada':
        motivo = request.POST.get(f'justificativa{atividade_id}')
        atividade.motivo_pausa = motivo
    elif novo_status == 'executando':
        atividade.motivo_pausa = "" # Limpa o motivo ao retomar
        atividade.ultima_interacao = agora

    # Lógica de tempo acumulado
    if atividade.status == 'executando' and novo_status in ['pausada', 'finalizada']:
        if atividade.ultima_interacao:
            atividade.tempo_total_gasto += (agora - atividade.ultima_interacao)

    atividade.status = novo_status
    atividade.save()
    
    # Retorna o badge e um comando para recarregar a página e mostrar o motivo abaixo do badge
    return HttpResponse(
        f'<span id="status-badge-{atividade.id}" class="status-badge status-{atividade.status}">'
        f'{atividade.get_status_display()}</span>'
        f'<script>setTimeout(()=>location.reload(), 300)</script>'
    )

@login_required
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

@login_required
def aprovar_chamado(request, chamado_id):
    if request.method == 'POST':
        chamado = get_object_or_404(Chamado, id=chamado_id)
        tecnicos_ids = request.POST.getlist('tecnico') # Pega a lista de IDs
        
        if not tecnicos_ids:
            messages.error(request, "Selecione ao menos um técnico.")
            return redirect('lista_atividades')

        nova_os = Atividade.objects.create(
            maquina=chamado.maquina,
            descricao=f"CHAMADO #{chamado.id}: {chamado.descricao_problema[:50]}",
            data_planejada=timezone.now(),
            duracao_estimada=timedelta(hours=2),
            status='aberta'
        )
        nova_os.colaboradores.set(tecnicos_ids) # Salva a relação ManyToMany
        
        chamado.status = 'aprovado'
        chamado.save()
        messages.success(request, "Chamado aprovado e OS gerada!")
    return redirect('lista_atividades')

@login_required
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
            tecnicos_nomes = ", ".join([t.first_name or t.username for t in act.colaboradores.all()])
            if not tecnicos_nomes:
                tecnicos_nomes = "Sem Técnico"

            dados.append({
                'id': str(act.id),
                'name': f"[{tecnicos_nomes}] {act.maquina.codigo}: {act.descricao[:15]}",
                'start': act.inicio_calculado.isoformat(),
                'end': act.fim_calculado.isoformat(),
                'progress': progresso,
                'custom_class': 'gantt-emergencial' if act.eh_emergencial else f'gantt-status-{act.status}'
            })
        
        return JsonResponse(dados, safe=False)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
    
    except Exception as e:
        print(f"ERRO CRÍTICO NO GANTT: {e}")
        return JsonResponse({'error': str(e)}, status=500)
@login_required
def logout_view(request):
    logout(request)
    messages.info(request, "Você saiu do sistema com sucesso.")
    return redirect('login') # Ou para onde você quiser mandar o usuário após sair