from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from datetime import timedelta
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout
from django.contrib import messages
from itertools import chain 
from operator import attrgetter
from django.db.models import Count, Q

from .models import Atividade, AtividadeLog, Maquina, Chamado, PlanoPreventivo

from .forms import AtividadeForm
from .utils import sequenciar_atividades
from .forms import AtividadeForm, PlanoPreventivoForm 
# --- ROBÔ (Mantido igual) ---
def verificar_e_gerar_preventivas():
    hoje = timezone.now().date()
    planos_vencidos = PlanoPreventivo.objects.filter(ativo=True, proxima_data__lte=hoje)
    geradas = 0
    for plano in planos_vencidos:
        Atividade.objects.create(
            maquina=plano.maquina,
            descricao=f"[AUTO] {plano.nome}",
            data_planejada=plano.proxima_data,
            eh_preventiva=True,
            procedimento_base=plano.procedimento_padrao,
            duracao_estimada=timedelta(hours=2),
            status='aberta'
        )
        plano.proxima_data = plano.proxima_data + timedelta(days=plano.frequencia_dias)
        plano.save()
        geradas += 1
    return geradas

# --- API DO GANTT (CORRIGIDA: NOME DA MÁQUINA) ---
@login_required
def dados_gantt(request):
    try:
        # Trazemos Logs e Usuários para evitar consultas repetidas
        atividades_db = Atividade.objects.select_related('maquina').prefetch_related('colaboradores', 'logs__usuario').all()
        atividades = sequenciar_atividades(atividades_db)
        
        dados = []
        agora = timezone.now()

        for act in atividades:
            progresso = 0
            if act.status == 'executando': progresso = 50
            elif act.status == 'finalizada': progresso = 100
            elif act.status == 'pausada': progresso = 25

            tecnicos_nomes = [t.first_name or t.username for t in act.colaboradores.all()]
            tecnicos_ids = [str(t.id) for t in act.colaboradores.all()]
            
            # --- NOVO: Preparar Histórico para o JSON ---
            logs_list = []
            for log in act.logs.all().order_by('-data_registro'):
                logs_list.append({
                    'data': log.data_registro.strftime('%d/%m/%Y %H:%M'),
                    'usuario': log.usuario.username,
                    'descricao': log.descricao
                })

            nome_maquina_full = f"[{act.maquina.codigo}] {act.maquina.nome}"
            label_barra = f"{nome_maquina_full}: {act.descricao[:20]}.."

            custom_class = f'gantt-status-{act.status}'
            if act.status not in ['finalizada', 'cancelada'] and act.fim_calculado < agora:
                custom_class = 'gantt-atrasado'
            elif getattr(act, 'eh_emergencial', False):
                custom_class = 'gantt-emergencial'

            dados.append({
                'id': str(act.id),
                'name': label_barra,
                'full_name': f"#{act.id} - {act.descricao}",
                'description': act.descricao,
                'start': act.inicio_calculado.isoformat(),
                'end': act.fim_calculado.isoformat(),
                'progress': progresso,
                'custom_class': custom_class,
                'tech_ids': tecnicos_ids, 
                'tech_names': ", ".join(tecnicos_nomes),
                'status': act.status,
                'maquina': nome_maquina_full,
                'logs': logs_list, # Enviando o histórico
                'motivo_pausa': act.motivo_pausa or "" # Enviando motivo da pausa
            })
        
        return JsonResponse(dados, safe=False)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required
def dashboard_analitico(request):
    # 1. Robô de Preventivas
    novas_ops = verificar_e_gerar_preventivas()
    if novas_ops > 0:
        messages.info(request, f"{novas_ops} preventivas geradas automaticamente.")

    # Inicializa os forms vazios (prefix evita conflito de nomes)
    form_atividade = AtividadeForm(prefix='atividade')
    form_plano = PlanoPreventivoForm(prefix='plano')

    if request.method == 'POST':
        # Verifica se o botão clicado foi o de Nova Atividade
        if 'btn_nova_atividade' in request.POST:
            form_atividade = AtividadeForm(request.POST, prefix='atividade')
            if form_atividade.is_valid():
                atividade = form_atividade.save(commit=False)
                
                # CORREÇÃO DE ERRO: Tratamento seguro para valores vazios
                valor_raw = form_atividade.cleaned_data.get('tempo_valor')
                valor = int(valor_raw) if valor_raw else 0
                
                unidade = form_atividade.cleaned_data.get('tempo_unidade', 'horas')
                
                if unidade == 'dias': 
                    atividade.duracao_estimada = timedelta(days=valor)
                else: 
                    atividade.duracao_estimada = timedelta(hours=valor)

                # Se for preventiva baseada em procedimento, puxa o nome
                if atividade.eh_preventiva and atividade.procedimento_base:
                    atividade.descricao = f"PREV: {atividade.procedimento_base.nome}"
                    # Opcional: puxar duração padrão do procedimento
                    # atividade.duracao_estimada = atividade.procedimento_base.duracao_estimada_padrao
                
                atividade.save()
                form_atividade.save_m2m() # Salva os técnicos
                messages.success(request, "Nova atividade agendada com sucesso!")
                return redirect('dashboard_analitico')

        # Verifica se o botão clicado foi o de Novo Plano Preventivo
        elif 'btn_novo_plano' in request.POST:
            form_plano = PlanoPreventivoForm(request.POST, prefix='plano')
            if form_plano.is_valid():
                plano = form_plano.save(commit=False)
                plano.ativo = True # Garante que nasce ativo
                plano.save()
                messages.success(request, "Novo Plano de Manutenção cadastrado!")
                return redirect('dashboard_analitico')
            else:
                messages.error(request, "Erro ao cadastrar plano. Verifique os dados.")

    # 3. Dados para os Gráficos e Listas
    quebras_por_maquina = Atividade.objects.filter(eh_preventiva=False).values('maquina__codigo').annotate(total=Count('id')).order_by('-total')[:5]
    labels_quebra = [item['maquina__codigo'] for item in quebras_por_maquina]
    data_quebra = [item['total'] for item in quebras_por_maquina]
    
    planos_futuros = PlanoPreventivo.objects.filter(ativo=True).select_related('maquina').order_by('proxima_data')
    
    tecnicos = User.objects.all()

    context = {
        'labels_quebra': labels_quebra,
        'data_quebra': data_quebra,
        'planos_futuros': planos_futuros,
        'form_atividade': form_atividade, # Manda o form 1 para o template
        'form_plano': form_plano,         # Manda o form 2 para o template
        'tecnicos': tecnicos,
        'today': timezone.now().date()
    }
    
    return render(request, 'assets/dashboard_completo.html', context)

@login_required
def lista_atividades(request):
    # Lógica mantida, apenas garantindo o select_related para performance
    if request.method == 'POST':
        form = AtividadeForm(request.POST)
        if form.is_valid():
            atividade = form.save(commit=False)
            valor = int(form.cleaned_data.get('tempo_valor', 0)) 
            unidade = form.cleaned_data.get('tempo_unidade', 'horas')
            if unidade == 'dias': atividade.duracao_estimada = timedelta(days=valor)
            else: atividade.duracao_estimada = timedelta(hours=valor)
            
            if atividade.eh_preventiva and atividade.procedimento_base:
                atividade.descricao = f"PREVENTIVA: {atividade.procedimento_base.nome}"
                atividade.duracao_estimada = atividade.procedimento_base.duracao_estimada_padrao
            
            atividade.save()
            form.save_m2m()
            return redirect('lista_atividades')
    else:
        form = AtividadeForm()

    atividades_queryset = Atividade.objects.select_related('maquina').all()
    atividades_sequenciadas = sequenciar_atividades(atividades_queryset)

    atividades_pendentes = [a for a in atividades_sequenciadas if a.status not in ['finalizada', 'cancelada']]
    concluidas = [a for a in atividades_sequenciadas if a.status == 'finalizada']
    
    chamados_pendentes = Chamado.objects.select_related('maquina', 'requisitante').filter(status='pendente').order_by('-prioridade_indicada')
    recusados = Chamado.objects.select_related('maquina').filter(status='recusado').order_by('-data_abertura')

    historico_geral = sorted(
        chain(concluidas, recusados),
        key=lambda x: getattr(x, 'fim_calculado', getattr(x, 'data_abertura', None)),
        reverse=True
    )

    tecnicos = User.objects.all()
    
    return render(request, 'assets/lista_ativos.html', {
        'atividades': atividades_pendentes, 
        'chamados_pendentes': chamados_pendentes,
        'historico_unificado': historico_geral,
        'tecnicos': tecnicos,
        'form': form
    })

# ... (Mantenha as outras views auxiliares: cancelar, aprovar, recusar, etc.) ...
@login_required
def recusar_chamado(request, chamado_id):
    if request.method == 'POST':
        chamado = get_object_or_404(Chamado, id=chamado_id)
        chamado.motivo_resposta = request.POST.get('motivo')
        chamado.status = 'recusado'
        chamado.save()
        messages.warning(request, f"Chamado #{chamado.id} recusado.")
    return redirect('lista_atividades')

@login_required
def cancelar_atividade(request, atividade_id):
    if request.method == 'POST':
        atividade = get_object_or_404(Atividade, id=atividade_id)
        atividade.motivo_cancelamento = request.POST.get('motivo')
        atividade.status = 'cancelada'
        atividade.save()
    return redirect(request.META.get('HTTP_REFERER', 'lista_atividades'))

@csrf_exempt
@login_required
def alterar_status(request, atividade_id, novo_status):
    atividade = get_object_or_404(Atividade, id=atividade_id)
    justificativa = request.POST.get('justificativa', '')
    usuario = request.user
    
    agora = timezone.now()
    if atividade.status == 'executando' and novo_status in ['pausada', 'finalizada']:
        if atividade.ultima_interacao:
            decorrido = agora - atividade.ultima_interacao
            atividade.tempo_total_gasto += decorrido

    atividade.status = novo_status
    if novo_status == 'pausada':
        atividade.motivo_pausa = justificativa
    elif novo_status == 'executando':
        atividade.motivo_pausa = None
        atividade.ultima_interacao = timezone.now()
    atividade.save()
    AtividadeLog.objects.create(atividade=atividade, usuario=usuario, status_novo=novo_status, descricao=f"Status: {novo_status} | {justificativa}")
    cor_status = {'aberta': 'status-aberta', 'executando': 'status-executando', 'pausada': 'status-pausada', 'finalizada': 'status-finalizada'}.get(novo_status, '')
    html_retorno = f'<span class="status-badge {cor_status}">{atividade.get_status_display()}</span>'
    if novo_status == 'pausada' and justificativa:
        html_retorno += f'<div class="pause-reason fade-in"><i class="fas fa-exclamation-circle me-1"></i>{justificativa}</div>'
    return HttpResponse(html_retorno)

@login_required
def atribuir_tecnicos(request, atividade_id):
    if request.method == 'POST':
        atividade = get_object_or_404(Atividade, id=atividade_id)
        tecnicos_ids = request.POST.getlist('tecnicos') 
        atividade.colaboradores.clear()
        if tecnicos_ids:
            for t_id in tecnicos_ids: atividade.colaboradores.add(t_id)
            messages.success(request, "Equipe atualizada!")
        else: messages.warning(request, "OS sem técnicos.")
        return redirect(request.META.get('HTTP_REFERER', 'lista_atividades'))

@login_required
def abrir_chamado(request):
    if request.method == 'POST':
        Chamado.objects.create(
            maquina_id=request.POST.get('maquina'), requisitante=request.user,
            descricao_problema=request.POST.get('descricao'), prioridade_indicada=request.POST.get('prioridade'),
            maquina_parada=request.POST.get('maquina_parada') == 'on'
        )
        messages.success(request, "Chamado registrado!")
        return redirect('abrir_chamado') 
    return render(request, 'assets/abrir_chamado.html', {'maquinas': Maquina.objects.all()})

@login_required
def aprovar_chamado(request, chamado_id):
    if request.method == 'POST':
        chamado = get_object_or_404(Chamado, id=chamado_id)
        tecnicos_ids = request.POST.getlist('tecnico')
        if not tecnicos_ids:
             messages.error(request, "Selecione um técnico.")
             return redirect('lista_atividades')
        nova_os = Atividade.objects.create(
            maquina=chamado.maquina, descricao=f"CHAMADO #{chamado.id}: {chamado.descricao_problema[:50]}",
            data_planejada=timezone.now(), duracao_estimada=timedelta(hours=2), status='aberta'
        )
        nova_os.colaboradores.set(tecnicos_ids)
        chamado.status = 'aprovado'
        chamado.save()
        messages.success(request, "Chamado Aprovado.")
    return redirect('lista_atividades')

@login_required
def logout_view(request):
    logout(request)
    return redirect('login')