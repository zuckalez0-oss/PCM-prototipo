from django.shortcuts import render, redirect, get_object_or_404  # Adicionado: redirect e get_object_or_404
from django.http import HttpResponse, JsonResponse
from django.utils import timezone  # Adicionado: timezone para as datas
from datetime import timedelta     # Adicionado: timedelta para cálculos de tempo
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.models import User
from django.contrib import messages 

from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout

from .models import Atividade, AtividadeLog # Import log


from .models import Atividade, Maquina, ProcedimentoPreventivo, Chamado 


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
            ## -- sol de ajuste, colocar tempo real com 2 casas decimais -- ##
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
    justificativa = request.POST.get('justificativa', '') # Pega o motivo do modal
    usuario = request.user

    # 1. Atualiza Status e Motivo no Objeto Principal
    atividade.status = novo_status
    if novo_status == 'pausada':
        atividade.motivo_pausa = justificativa
    elif novo_status == 'executando':
        atividade.motivo_pausa = None # Limpa motivo se voltar a rodar
        atividade.ultima_interacao = timezone.now()
    
    atividade.save()

    # 2. Cria o Log para o Histórico Detalhado
    descricao_log = f"Alterado para {novo_status.upper()}"
    if justificativa:
        descricao_log += f": {justificativa}"
    
    AtividadeLog.objects.create(
        atividade=atividade,
        usuario=usuario,
        status_novo=novo_status,
        descricao=descricao_log
    )

    # 3. Retorna o HTML atualizado (COM A JUSTIFICATIVA)
    # Importante: Retornamos o badge E a div de justificativa
    cor_status = {
        'aberta': 'status-aberta', 'executando': 'status-executando',
        'pausada': 'status-pausada', 'finalizada': 'status-finalizada'
    }.get(novo_status, '')

    html_retorno = f'<span class="status-badge {cor_status}">{atividade.get_status_display()}</span>'
    
    if novo_status == 'pausada' and justificativa:
        html_retorno += f'<div class="pause-reason fade-in"><i class="fas fa-exclamation-circle me-1"></i>{justificativa}</div>'
    
    return HttpResponse(html_retorno)
@login_required
def atribuir_tecnicos(request, atividade_id):
    if request.method == 'POST':
        atividade = get_object_or_404(Atividade, id=atividade_id)
        # Pega a lista de IDs enviados pelo select multiple
        tecnicos_ids = request.POST.getlist('tecnicos') 
        
        # Limpa os atuais e adiciona os novos
        atividade.colaboradores.clear()
        if tecnicos_ids:
            for t_id in tecnicos_ids:
                atividade.colaboradores.add(t_id)
            
            messages.success(request, f"Equipe da OS #{atividade.id} atualizada com sucesso!")
        else:
            messages.warning(request, "Atenção: A OS ficou sem técnicos vinculados.")
            
        return redirect('lista_atividades')

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
    try:
        atividades_db = Atividade.objects.all()
        atividades = sequenciar_atividades(atividades_db)
        
        dados = []
        for act in atividades:
            progresso = 0
            if act.status == 'executando': progresso = 50
            elif act.status == 'finalizada': progresso = 100
            elif act.status == 'pausada': progresso = 25

            tecnicos_nomes = ", ".join([t.first_name or t.username for t in act.colaboradores.all()])
            
            # Usando o tempo decimal formatado
            tempo_exibicao = f"{act.tempo_decimal:.2f}h"

            dados.append({
                'id': str(act.id),
                'name': f"[{tecnicos_nomes}] ({tempo_exibicao}) {act.maquina.codigo}: {act.descricao[:15]}",
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