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


# Seus Models e Forms
from .models import Atividade, AtividadeLog, Maquina, Chamado, PlanoPreventivo
from .forms import AtividadeForm
from .utils import sequenciar_atividades

# --- ROBÔ DE AUTOMAÇÃO (Executa ao abrir o dashboard) ---
def verificar_e_gerar_preventivas():
    hoje = timezone.now().date()
    # Pega planos ativos cuja data é hoje ou anterior (caso tenha passado o dia sem abrir o sistema)
    planos_vencidos = PlanoPreventivo.objects.filter(ativo=True, proxima_data__lte=hoje)
    
    geradas = 0
    for plano in planos_vencidos:
        # Cria a Atividade
        Atividade.objects.create(
            maquina=plano.maquina,
            descricao=f"[AUTO] {plano.nome}",
            data_planejada=plano.proxima_data,
            eh_preventiva=True,
            procedimento_base=plano.procedimento_padrao, # Se houver
            duracao_estimada=timedelta(hours=2), # Padrão
            status='aberta'
        )
        
        # Joga a data do plano para o futuro
        plano.proxima_data = plano.proxima_data + timedelta(days=plano.frequencia_dias)
        plano.save()
        geradas += 1
    return geradas

# --- VIEWS PRINCIPAIS ---

@login_required
def dashboard_analitico(request):
    # 1. RODA O ROBÔ
    novas_ops = verificar_e_gerar_preventivas()
    if novas_ops > 0:
        messages.info(request, f"{novas_ops} preventivas geradas.")

    # 2. Lógica para Salvar Nova Tarefa (Se vier do Modal do Dashboard)
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
            messages.success(request, "Nova atividade agendada via Dashboard!")
            return redirect('dashboard_analitico')
    else:
        form = AtividadeForm()

    # 3. DADOS DE ANÁLISE (Mantidos)
    quebras_por_maquina = Atividade.objects.filter(eh_preventiva=False).values('maquina__codigo').annotate(total=Count('id')).order_by('-total')[:5]
    labels_quebra = [item['maquina__codigo'] for item in quebras_por_maquina]
    data_quebra = [item['total'] for item in quebras_por_maquina]
    planos_futuros = PlanoPreventivo.objects.filter(ativo=True).order_by('proxima_data')[:10]
    
    # Lista de Técnicos para o Filtro do Gantt
    tecnicos = User.objects.all()

    context = {
        'labels_quebra': labels_quebra,
        'data_quebra': data_quebra,
        'planos_futuros': planos_futuros,
        'form': form,      # Enviamos o formulário
        'tecnicos': tecnicos # Enviamos lista de técnicos para o filtro
    }
    
    return render(request, 'assets/dashboard_completo.html', context)

@login_required
def dados_gantt(request):
    """ API Enriquecida para o Gantt """
    try:
        atividades_db = Atividade.objects.all()
        atividades = sequenciar_atividades(atividades_db)
        
        dados = []
        agora = timezone.now()

        for act in atividades:
            progresso = 0
            if act.status == 'executando': progresso = 50
            elif act.status == 'finalizada': progresso = 100
            elif act.status == 'pausada': progresso = 25

            # Lista de nomes e IDs para filtros
            tecnicos_nomes = [t.first_name or t.username for t in act.colaboradores.all()]
            tecnicos_ids = [str(t.id) for t in act.colaboradores.all()]
            
            nome_formatado = ", ".join(tecnicos_nomes)
            tempo_exibicao = f"{act.tempo_decimal:.2f}h"

            # Lógica de Atraso Visual
            custom_class = f'gantt-status-{act.status}'
            
            # Se não acabou e já passou da data fim calculada -> ATRASADO (Vermelho)
            if act.status not in ['finalizada', 'cancelada'] and act.fim_calculado < agora:
                custom_class = 'gantt-atrasado'
            elif getattr(act, 'eh_emergencial', False):
                custom_class = 'gantt-emergencial'

            dados.append({
                'id': str(act.id),
                'name': f"[{act.maquina.codigo}] {act.descricao[:25]}...",
                'full_name': f"#{act.id} - {act.descricao}", # Nome completo para o modal
                'description': act.descricao, # Descrição completa
                'start': act.inicio_calculado.isoformat(),
                'end': act.fim_calculado.isoformat(),
                'progress': progresso,
                'custom_class': custom_class,
                # Metadados para filtros e modal
                'tech_ids': tecnicos_ids, 
                'tech_names': ", ".join(tecnicos_nomes),
                'status': act.status,
                'maquina': act.maquina.codigo
            })
        
        return JsonResponse(dados, safe=False)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required
def lista_atividades(request):
    # ... (Mantenha sua view de lista_atividades exatamente como estava no seu código anterior) ...
    # Ela já estava correta com o histórico unificado.
    # Vou resumir aqui para economizar espaço, mas use a versão completa que você já tem.
    
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

    atividades_queryset = Atividade.objects.all()
    atividades_sequenciadas = sequenciar_atividades(atividades_queryset)

    atividades_pendentes = [a for a in atividades_sequenciadas if a.status not in ['finalizada', 'cancelada']]
    concluidas = [a for a in atividades_sequenciadas if a.status == 'finalizada']
    chamados_pendentes = Chamado.objects.filter(status='pendente').order_by('-prioridade_indicada')
    recusados = Chamado.objects.filter(status='recusado').order_by('-data_abertura')

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

# ... Mantenha as outras views (alterar_status, abrir_chamado, etc) iguais ...
@login_required
def alterar_status(request, atividade_id, novo_status):
    atividade = get_object_or_404(Atividade, id=atividade_id)
    justificativa = request.POST.get('justificativa', '')
    usuario = request.user
    atividade.status = novo_status
    if novo_status == 'pausada': atividade.motivo_pausa = justificativa
    elif novo_status == 'executando': 
        atividade.motivo_pausa = None
        atividade.ultima_interacao = timezone.now()
    atividade.save()
    
    # Log simplificado
    AtividadeLog.objects.create(atividade=atividade, usuario=usuario, status_novo=novo_status, descricao=f"Status: {novo_status} | {justificativa}")

    cor_status = {'aberta': 'status-aberta', 'executando': 'status-executando', 'pausada': 'status-pausada', 'finalizada': 'status-finalizada'}.get(novo_status, '')
    html_retorno = f'<span class="status-badge {cor_status}">{atividade.get_status_display()}</span>'
    if novo_status == 'pausada' and justificativa: html_retorno += f'<div class="pause-reason fade-in"><i class="fas fa-exclamation-circle me-1"></i>{justificativa}</div>'
    return HttpResponse(html_retorno)

@login_required
def atribuir_tecnicos(request, atividade_id):
    if request.method == 'POST':
        atividade = get_object_or_404(Atividade, id=atividade_id)
        tecnicos_ids = request.POST.getlist('tecnicos') 
        
        atividade.colaboradores.clear()
        if tecnicos_ids:
            for t_id in tecnicos_ids:
                atividade.colaboradores.add(t_id)
            messages.success(request, f"Equipe da OS #{atividade.id} atualizada com sucesso!")
        else:
            messages.warning(request, "Atenção: A OS ficou sem técnicos vinculados.")
            
        # CORREÇÃO: Redireciona para a página anterior (Dashboard ou Lista)
        referer = request.META.get('HTTP_REFERER')
        if referer:
            return redirect(referer)
        return redirect('lista_atividades') # Fallback

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
        nova_os = Atividade.objects.create(
            maquina=chamado.maquina, descricao=f"CHAMADO #{chamado.id}: {chamado.descricao_problema[:50]}",
            data_planejada=timezone.now(), duracao_estimada=timedelta(hours=2), status='aberta'
        )
        nova_os.colaboradores.set(tecnicos_ids)
        chamado.status = 'aprovado'
        chamado.save()
    return redirect('lista_atividades')

# Adicione isso no seu assets/views.py

@login_required
def cancelar_atividade(request, atividade_id):
    if request.method == 'POST':
        atividade = get_object_or_404(Atividade, id=atividade_id)
        motivo = request.POST.get('motivo')
        
        atividade.motivo_cancelamento = motivo
        atividade.status = 'cancelada'
        atividade.save()
        
        # Opcional: Gerar Log
        AtividadeLog.objects.create(
            atividade=atividade,
            usuario=request.user,
            status_novo='cancelada',
            descricao=f"Atividade Cancelada. Motivo: {motivo}"
        )
        
        messages.warning(request, f"Atividade #{atividade.id} cancelada.")
    return redirect('lista_atividades')

@login_required
def recusar_chamado(request, chamado_id):
    if request.method == 'POST':
        chamado = get_object_or_404(Chamado, id=chamado_id)
        chamado.motivo_resposta = request.POST.get('motivo')
        chamado.status = 'recusado'
        chamado.save()
    return redirect('lista_atividades')

@login_required
def logout_view(request):
    logout(request)
    return redirect('login')