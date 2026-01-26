from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from datetime import timedelta, datetime, time
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from zoneinfo import ZoneInfo # Para fuso horário fixo (Brasília)
from django.contrib.auth import logout
from django.contrib import messages
from itertools import chain 
from operator import attrgetter
from django.db.models import Count, Q
from django.db import transaction
import json

from .models import Atividade, AtividadeLog, Maquina, Chamado, PlanoPreventivo

from .utils import sequenciar_atividades, formatar_duracao
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

@login_required
def dados_gantt(request):
    """
    API do Gantt Sincronizada: Precisão Absoluta com Fuso Horário de Brasília.
    Garante que barras e detalhes batam 100% com a realidade da fábrica.
    """
    try:
        # 1. Definir Fuso e Momento Atual (Brasília)
        tz_br = ZoneInfo("America/Sao_Paulo")
        agora_local = timezone.now().astimezone(tz_br)
        
        # Prefetch para performance
        qs = Atividade.objects.select_related('maquina').prefetch_related('colaboradores', 'logs__usuario')
        atividades_db = qs.all().order_by('-eh_emergencial', 'data_planejada')
        
        dados = []
        for act in atividades_db:
            # 2. Determinar o Início (Real ou Planejado)
            log_inicio_real = act.logs.filter(status_novo='executando').order_by('data_registro').first()
            
            if log_inicio_real:
                inicio_v = log_inicio_real.data_registro.astimezone(tz_br)
            elif act.status in ['executando', 'pausada']:
                inicio_v = act.ultima_interacao.astimezone(tz_br) if act.ultima_interacao else agora_local
            else:
                inicio_v = act.data_planejada.astimezone(tz_br) if act.data_planejada else agora_local

            # 3. Determinar o Fim (Dinamismo de Acompanhamento)
            if act.status == 'executando':
                # Fim é AGORA TOTAL para a barra crescer com o tempo
                fim_v = agora_local
                end_label = None 
                progresso = 100 # Barra sólida (100% dinâmica)
            elif act.status == 'finalizada':
                log_fim = act.logs.filter(status_novo='finalizada').order_by('-data_registro').first()
                if log_fim:
                    fim_v = log_fim.data_registro.astimezone(tz_br)
                else:
                    fim_v = inicio_v + (act.duracao_estimada or timedelta(hours=1))
                end_label = fim_v.strftime('%d/%m %H:%M')
                progresso = 100
            else:
                # Aberta/Pausada: Fim visual baseado no estimado
                dur_est = act.duracao_estimada if (act.duracao_estimada and act.duracao_estimada.total_seconds() > 0) else timedelta(hours=2)
                fim_v = inicio_v + dur_est
                end_label = None
                progresso = 25 if act.status == 'pausada' else 0

            # Cálculo de Duração Efetiva (Puro delta matemático)
            duracao_efetiva = fim_v - inicio_v

            tecnicos_obj = act.colaboradores.all()
            tecnicos_nomes = [t.first_name or t.username for t in tecnicos_obj]
            tecnicos_ids = [str(t.id) for t in tecnicos_obj]
            
            label_barra = f"[{act.maquina.codigo}] {act.maquina.nome}: {act.descricao[:30]}.."

            # CSS Classes
            if act.status not in ['finalizada', 'cancelada'] and (fim_v < agora_local and act.status != 'executando'):
                custom_class = 'gantt-atrasado'
            elif act.status == 'executando': custom_class = 'gantt-status-executando'
            elif act.status == 'pausada': custom_class = 'gantt-status-pausada'
            elif act.status == 'finalizada': custom_class = 'gantt-status-finalizada'
            else: custom_class = 'gantt-status-aberta'

            logs_list = [{
                'data': l.data_registro.astimezone(tz_br).strftime('%d/%m %H:%M'),
                'usuario': l.usuario.username,
                'descricao': l.descricao
            } for l in act.logs.all().order_by('-data_registro')[:10]]

            dados.append({
                'id': str(act.id),
                'name': label_barra,
                'full_name': act.descricao,
                'description': act.instrucoes_tecnicas or act.descricao or "Sem descrição.",
                'start': inicio_v.strftime('%Y-%m-%d %H:%M'), 
                'end': fim_v.strftime('%Y-%m-%d %H:%M'),
                'start_formatted': inicio_v.strftime('%d/%m %H:%M'),
                'end_formatted': end_label,
                'duration': formatar_duracao(duracao_efetiva),
                'progress': progresso,
                'custom_class': custom_class,
                'dependencies': '',
                'maquina': act.maquina.nome,
                'status': act.status,
                'status_display': act.get_status_display(),
                'tech_names': ", ".join(tecnicos_nomes) if tecnicos_nomes else "Sem técnicos",
                'tecnicos': ", ".join(tecnicos_nomes) if tecnicos_nomes else "Pendente",
                'tech_ids': tecnicos_ids,
                'tempo_pausa': act.tempo_total_pausa.total_seconds(),
                'logs': logs_list
            })

        # 4. Preventivas Futuras
        planos_futuros = PlanoPreventivo.objects.filter(ativo=True).select_related('maquina', 'procedimento_padrao')
        for plano in planos_futuros:
            inicio_p = timezone.make_aware(datetime.combine(plano.proxima_data, time(8, 0)))
            inicio_p_local = timezone.localtime(inicio_p)
            dur_p = plano.procedimento_padrao.duracao_estimada_padrao if (plano.procedimento_padrao and plano.procedimento_padrao.duracao_estimada_padrao) else timedelta(hours=2)
            fim_p_local = inicio_p_local + dur_p
            
            dados.append({
                'id': f"plano-{plano.id}",
                'name': f"[AGRND] {plano.maquina.nome}: {plano.nome}",
                'full_name': f"Preventiva: {plano.nome}",
                'description': f"Procedimento: {plano.procedimento_padrao.nome if plano.procedimento_padrao else 'Padrão'}",
                'start': inicio_p_local.strftime('%Y-%m-%d %H:%M'),
                'end': fim_p_local.strftime('%Y-%m-%d %H:%M'),
                'start_formatted': inicio_p_local.strftime('%d/%m %H:%M'),
                'end_formatted': fim_p_local.strftime('%d/%m %H:%M'),
                'duration': formatar_duracao(dur_p),
                'progress': 0,
                'custom_class': 'gantt-status-aberta',
                'dependencies': '',
                'maquina': plano.maquina.nome,
                'status': 'Agendada',
                'status_display': 'Agendada',
                'tech_names': "Industrial",
                'tecnicos': "Sincronização Automática",
                'tech_ids': [],
                'tempo_pausa': 0,
                'logs': []
            })

        return JsonResponse(dados, safe=False)
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return JsonResponse([], safe=False)
            
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
    
    planos_futuros = PlanoPreventivo.objects.filter(ativo=True).select_related('maquina', 'procedimento_padrao').order_by('proxima_data')
    
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
    
    tecnicos = User.objects.all()
    
    return render(request, 'assets/lista_ativos.html', {
        'atividades': atividades_pendentes, 
        'chamados_pendentes': chamados_pendentes,
        'chamados_pendentes_count': chamados_pendentes.count(), # Notification Badge
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
    return redirect('kanban_view')

@login_required
def cancelar_atividade(request, atividade_id):
    if request.method == 'POST':
        atividade = get_object_or_404(Atividade, id=atividade_id)
        atividade.motivo_cancelamento = request.POST.get('motivo')
        atividade.status = 'cancelada'
        atividade.save()
    return redirect(request.META.get('HTTP_REFERER', 'kanban_view'))

@csrf_exempt
@login_required
def alterar_status(request, atividade_id, novo_status):
    atividade = get_object_or_404(Atividade, id=atividade_id)
    justificativa = request.POST.get('justificativa', '')
    usuario = request.user
    
    agora = timezone.now()
    
    # --- NOVO: Cálculo de duração do status anterior ---
    ultimo_log = atividade.logs.order_by('-data_registro').first()
    if ultimo_log:
        segundos_decorridos = (agora - ultimo_log.data_registro).total_seconds()
        duracao_decorrida = timedelta(seconds=segundos_decorridos)
        ultimo_log.duracao = duracao_decorrida
        ultimo_log.save()
        
        # Se o status sendo encerrado era 'pausada', somamos ao contador
        if atividade.status == 'pausada':
            atividade.tempo_total_pausa += duracao_decorrida

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
    ativ_log = AtividadeLog.objects.create(atividade=atividade, usuario=usuario, status_novo=novo_status, descricao=f"Status: {novo_status} | {justificativa}")
    
    # Lógica de Retorno Dinâmico baseada no Target do HTMX
    hx_target = request.headers.get('HX-Target')
    
    if hx_target == 'kanban-container':
        # Detecta parâmetros vindos do HTMX (via hx-include ou hx-vals)
        ctx = get_kanban_context(request)
        view_mode = ctx['view_mode']
        
        if view_mode == 'list':
            return render(request, 'assets/partials/_kanban_list.html', ctx)
        else:
            return render(request, 'assets/partials/_kanban_board.html', ctx)

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
        if request.headers.get('HX-Request'):
            # Recalcular dados para o Kanban (Board)
            atividades_queryset = Atividade.objects.select_related('maquina', 'procedimento_base').prefetch_related('colaboradores').all()
            atividades_sequenciadas = sequenciar_atividades(atividades_queryset)
            
            abertas = [a for a in atividades_sequenciadas if a.status == 'aberta']
            executando = [a for a in atividades_sequenciadas if a.status == 'executando']
            pausadas = [a for a in atividades_sequenciadas if a.status == 'pausada']
            concluidas = [a for a in atividades_sequenciadas if a.status == 'finalizada'][:10]
            chamados_pendentes = Chamado.objects.select_related('maquina', 'requisitante').filter(status='pendente').order_by('-data_abertura')
            
            ctx = {
                'abertas': abertas,
                'executando': executando,
                'pausadas': pausadas,
                'concluidas': concluidas,
                'chamados_pendentes': chamados_pendentes,
                'tecnicos': User.objects.all()
            }
            
            response = render(request, 'assets/partials/_kanban_board.html', ctx)
            response['HX-Trigger'] = json.dumps({
                "showToast": {"message": "Equipe atualizada com sucesso!", "type": "success"}
            })
            return response

        return redirect(request.META.get('HTTP_REFERER', 'kanban_view'))

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
def notificacoes_dropdown(request):
    """
    HTMX endpoint: Returns pending chamados as HTML partial for notification dropdown.
    """
    chamados_pendentes = Chamado.objects.select_related('maquina', 'requisitante').filter(
        status='pendente'
    ).order_by('-data_abertura')[:10]
    
    return render(request, 'assets/partials/_notificacoes_dropdown.html', {
        'chamados_pendentes': chamados_pendentes
    })

@login_required
def aprovar_chamado(request, chamado_id):
    if request.method == 'POST':
        with transaction.atomic():
            # Lock da linha para prevenir race conditions
            chamado = Chamado.objects.select_for_update().get(id=chamado_id)
            
            # Verificação 1: Chamado já foi processado?
            if chamado.status != 'pendente':
                error_msg = "Este chamado já foi processado."
                if request.headers.get('HX-Request'):
                    response = HttpResponse(status=409)  # Conflict
                    response['HX-Trigger'] = json.dumps({
                        "showToast": {"message": error_msg, "type": "warning"}
                    })
                    return response
                messages.warning(request, error_msg)
                return redirect('kanban_view')
            
            # Verificação 2: Já existe OS para este chamado?
            os_existente = Atividade.objects.filter(
                descricao__contains=f"CHAMADO #{chamado.id}:"
            ).first()
            
            if os_existente:
                error_msg = f"Já existe uma OS (#{os_existente.id}) para este chamado."
                if request.headers.get('HX-Request'):
                    response = HttpResponse(status=409)
                    response['HX-Trigger'] = json.dumps({
                        "showToast": {"message": error_msg, "type": "warning"}
                    })
                    return response
                messages.warning(request, error_msg)
                return redirect('kanban_view')
            
            # Validação: Técnico obrigatório
            tecnicos_ids = request.POST.getlist('tecnico')
            if not tecnicos_ids:
                error_msg = "Selecione um técnico."
                if request.headers.get('HX-Request'):
                    response = HttpResponse(status=400)
                    response['HX-Trigger'] = json.dumps({
                        "showToast": {"message": error_msg, "type": "error"}
                    })
                    return response
                messages.error(request, error_msg)
                return redirect('kanban_view')
            
            # Criar OS
            data_planejada_str = request.POST.get('data_planejada')
            data_planejada = data_planejada_str if data_planejada_str else timezone.now()

            nova_os = Atividade.objects.create(
                maquina=chamado.maquina,
                descricao=f"CHAMADO #{chamado.id}: {chamado.descricao_problema[:50]}",
                data_planejada=data_planejada,
                duracao_estimada=timedelta(hours=2),
                status='aberta'
            )
            nova_os.colaboradores.set(tecnicos_ids)
            
            # Atualizar status do chamado
            chamado.status = 'aprovado'
            chamado.save()
            
            # Resposta HTMX: Retornar Kanban atualizado
            if request.headers.get('HX-Request'):
                # Recalcular dados do Kanban
                atividades_queryset = Atividade.objects.select_related('maquina', 'procedimento_base').prefetch_related('colaboradores').all()
                atividades_sequenciadas = sequenciar_atividades(atividades_queryset)
                
                abertas = [a for a in atividades_sequenciadas if a.status == 'aberta']
                executando = [a for a in atividades_sequenciadas if a.status == 'executando']
                pausadas = [a for a in atividades_sequenciadas if a.status == 'pausada']
                concluidas = [a for a in atividades_sequenciadas if a.status == 'finalizada'][:10]
                chamados_pendentes = Chamado.objects.select_related('maquina', 'requisitante').filter(status='pendente').order_by('-data_abertura')
                
                tecnicos = User.objects.all()
                
                ctx = {
                    'abertas': abertas,
                    'executando': executando,
                    'pausadas': pausadas,
                    'concluidas': concluidas,
                    'chamados_pendentes': chamados_pendentes,
                    'tecnicos': tecnicos
                }
                
                response = render(request, 'assets/partials/_kanban_board.html', ctx)
                response['HX-Trigger'] = json.dumps({
                    "showToast": {"message": "Chamado aprovado com sucesso!", "type": "success"}
                })
                return response
            
            messages.success(request, "Chamado Aprovado.")
            return redirect('kanban_view')

@login_required
def home(request):
    """
    Nova Landing Page Interna (Home).
    """
    return render(request, 'assets/home.html')

def get_kanban_context(request):
    """
    Helper para centralizar a lógica de busca e filtragem do Kanban/Lista.
    """
    view_mode = request.GET.get('mode') or request.POST.get('mode') or 'board'
    filtro_data = request.GET.get('filtro_data') or request.POST.get('filtro_data') or 'recente'
    data_especifica = request.GET.get('data_especifica') or request.POST.get('data_especifica')
    
    # Busca dados
    atividades_queryset = Atividade.objects.select_related('maquina', 'procedimento_base').prefetch_related('colaboradores', 'logs__usuario').all()
    atividades_sequenciadas = sequenciar_atividades(atividades_queryset)

    # Separar atividades operacionais
    abertas = [a for a in atividades_sequenciadas if a.status == 'aberta']
    executando = [a for a in atividades_sequenciadas if a.status == 'executando']
    pausadas = [a for a in atividades_sequenciadas if a.status == 'pausada']
    todas_concluidas = [a for a in atividades_sequenciadas if a.status == 'finalizada']
    
    # Lógica de Filtragem (Melhorada para lidar com datas nulas e Ordenação)
    agora = timezone.now()
    
    # Helper para pegar a data de "vencimento" ou conclusão real
    def get_ref_date(act):
        if act.ultima_interacao: return act.ultima_interacao.date()
        # Fallback para o último log se existir
        last_log = act.logs.all().order_by('-data_registro').first()
        if last_log: return last_log.data_registro.date()
        return None

    # Ordenamos todas as concluídas pela data de término (DESC) antes de filtrar/fatiar
    # Para o Python sorted, precisamos lidar com None
    todas_concluidas = sorted(
        todas_concluidas, 
        key=lambda x: x.ultima_interacao or timezone.make_aware(datetime.min), 
        reverse=True
    )

    if filtro_data == 'hoje':
        concluidas = [a for a in todas_concluidas if get_ref_date(a) == agora.date()]
        label_concluidas = "Concluídas (Hoje)"
    elif filtro_data == 'mes':
        concluidas = [a for a in todas_concluidas if get_ref_date(a) and get_ref_date(a).month == agora.month and get_ref_date(a).year == agora.year]
        label_concluidas = "Concluídas (Este Mês)"
    elif filtro_data == 'ano':
        concluidas = [a for a in todas_concluidas if get_ref_date(a) and get_ref_date(a).year == agora.year]
        label_concluidas = "Concluídas (Este Ano)"
    elif filtro_data == 'custom' and data_especifica:
        try:
            dt_obj = datetime.strptime(data_especifica, '%Y-%m-%d').date()
            concluidas = [a for a in todas_concluidas if get_ref_date(a) == dt_obj]
            label_concluidas = f"Concluídas ({dt_obj.strftime('%d/%m/%Y')})"
        except (ValueError, TypeError):
            concluidas = todas_concluidas[:50]
            label_concluidas = "Concluídas (Recentes)"
    else:
        concluidas = todas_concluidas[:50]
        label_concluidas = "Concluídas (Recentes)"
    
    chamados_pendentes = Chamado.objects.select_related('maquina', 'requisitante').filter(status='pendente').order_by('-data_abertura')
    atividades_pendentes = [a for a in atividades_sequenciadas if a.status != 'finalizada'] + concluidas

    return {
        'view_mode': view_mode,
        'filtro_data': filtro_data,
        'data_especifica': data_especifica,
        'label_concluidas': label_concluidas,
        'chamados_pendentes': chamados_pendentes,
        'chamados_pendentes_count': chamados_pendentes.count(),
        'abertas': abertas,
        'executando': executando,
        'pausadas': pausadas,
        'concluidas': concluidas,
        'atividades': atividades_pendentes,
        'tecnicos': User.objects.all(),
        'is_recente': filtro_data == 'recente',
        'is_hoje': filtro_data == 'hoje',
        'is_mes': filtro_data == 'mes',
        'is_ano': filtro_data == 'ano',
        'is_custom': filtro_data == 'custom',
    }

@login_required
def kanban_view(request):
    ctx = get_kanban_context(request)
    if request.headers.get('HX-Request') and request.headers.get('HX-Target') == 'kanban-container':
        if ctx['view_mode'] == 'list':
            return render(request, 'assets/partials/_kanban_list.html', ctx)
        return render(request, 'assets/partials/_kanban_board.html', ctx)
    return render(request, 'assets/kanban.html', ctx)

@login_required
def logout_view(request):
    logout(request)
    return redirect('login')