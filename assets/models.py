from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta

class Maquina(models.Model):
    nome = models.CharField(max_length=100)
    codigo = models.CharField(max_length=50, unique=True) # Ex: TORNO-01

    def __str__(self):
        return f"{self.codigo} - {self.nome}"
    
class PlanoPreventivo(models.Model):
    nome = models.CharField(max_length=100, help_text="Ex: Lubrificação Semanal")
    maquina = models.ForeignKey(Maquina, on_delete=models.CASCADE)
    procedimento_padrao = models.ForeignKey('ProcedimentoPreventivo', on_delete=models.SET_NULL, null=True, blank=True)
    frequencia_dias = models.IntegerField(help_text="A cada quantos dias deve ocorrer?")
    proxima_data = models.DateField(help_text="Data da próxima geração automática")
    ativo = models.BooleanField(default=True)
    def __str__(self):
        return f"{self.nome} - {self.maquina.codigo} (Cada {self.frequencia_dias} dias)"
    
class ProcedimentoPreventivo(models.Model):
    codigo = models.CharField(max_length=50, unique=True, verbose_name="Código da Preventiva")
    nome = models.CharField(max_length=200)
    instrucoes = models.TextField(blank=True, help_text="Passo a passo técnico")
    duracao_estimada_padrao = models.DurationField(help_text="Tempo padrão para esta tarefa")
    plano_origem = models.ForeignKey(PlanoPreventivo, on_delete=models.SET_NULL, null=True, blank=True)   
    def __str__(self):
        return f"{self.codigo} - {self.nome}" 

class Atividade(models.Model):
    eh_emergencial = models.BooleanField(default=False, verbose_name="Emergencial (Corta fila)")
    STATUS_CHOICES = [
        ('aberta', 'Aberta'),
        ('executando', 'Em Execução'),
        ('pausada', 'Pausada'),
        ('finalizada', 'Finalizada'),
        ('parada', 'Parada/Cancelada'),
        ('cancelada', 'Cancelada'),
    ]

    maquina = models.ForeignKey(Maquina, on_delete=models.CASCADE)
    descricao = models.CharField(max_length=255) # Ex: Troca de Rolamento
    colaboradores = models.ManyToManyField(User, related_name='atividades')
    motivo_pausa = models.TextField(blank=True, null=True)
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='aberta')
    motivo_cancelamento = models.TextField(null=True, blank=True)
    instrucoes_tecnicas = models.TextField(null=True, blank=True) 
    
    # Planejamento (Gantt)
    duracao_estimada = models.DurationField(help_text="Tempo previsto (Ex: 02:00:00 para 2h)")
    data_planejada = models.DateTimeField(default=timezone.now)
    
    # Realizado
    tempo_total_gasto = models.DurationField(default=timezone.timedelta(0))
    tempo_total_pausa = models.DurationField(default=timezone.timedelta(0))
    ultima_interacao = models.DateTimeField(null=True, blank=True)

    @property
    def duration_seconds(self):
        total = self.tempo_total_gasto.total_seconds()
        if self.status == 'executando' and self.ultima_interacao:
            # Adiciona o tempo decorrido desde a última interação até agora
            delta = (timezone.now() - self.ultima_interacao).total_seconds()
            total += delta
        return int(total)

    # Novos campos para a lógica de Preventiva
    eh_preventiva = models.BooleanField(default=False, verbose_name="É uma manutenção preventiva?")
    procedimento_base = models.ForeignKey(
        ProcedimentoPreventivo, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        verbose_name="Procedimento de Origem"
    )


    def __str__(self):
        return f"{self.maquina.codigo} - {self.descricao}"
    
class Chamado(models.Model):
    STATUS_CHAMADO = [
        ('pendente', 'Pendente (Triagem)'),
        ('aprovado', 'Aprovado (Virou OS)'),
        ('recusado', 'Recusado'),
        
    ]
    motivo_resposta = models.TextField(null=True, blank=True, verbose_name="Motivo da Recusa/Resposta")
    PRIORIDADE_CHOICES = [
        (1, 'Baixa - Pode aguardar'),
        (2, 'Média - Monitorar'),
        (3, 'Alta - Urgente'),
    ]

    maquina = models.ForeignKey(Maquina, on_delete=models.CASCADE)
    requisitante = models.ForeignKey(User, on_delete=models.CASCADE)
    descricao_problema = models.TextField()
    prioridade_indicada = models.IntegerField(choices=PRIORIDADE_CHOICES, default=1)
    maquina_parada = models.BooleanField(default=False)
    data_abertura = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHAMADO, default='pendente')

    def __str__(self):
        return f"Chamado {self.id} - {self.maquina.codigo}"
    

class AtividadeLog(models.Model):
    atividade = models.ForeignKey(Atividade, on_delete=models.CASCADE, related_name='logs')
    usuario = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    status_novo = models.CharField(max_length=20)
    descricao = models.CharField(max_length=255, blank=True, null=True) 
    duracao = models.DurationField(null=True, blank=True)
    data_registro = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.atividade.id} - {self.status_novo} - {self.data_registro}"

class AcessoLog(models.Model):
    usuario = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    path = models.CharField(max_length=255)
    method = models.CharField(max_length=10)
    status_code = models.IntegerField()
    user_agent = models.TextField(null=True, blank=True)
    data_acesso = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Log de Acesso"
        verbose_name_plural = "Logs de Acesso"
        ordering = ['-data_acesso']

    def __str__(self):
        user_display = self.usuario.username if self.usuario else "Anônimo"
        return f"{self.data_acesso.strftime('%d/%m %H:%M')} - {user_display} - {self.path} ({self.status_code})"