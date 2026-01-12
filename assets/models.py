from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

class Maquina(models.Model):
    nome = models.CharField(max_length=100)
    codigo = models.CharField(max_length=50, unique=True) # Ex: TORNO-01

    def __str__(self):
        return f"{self.codigo} - {self.nome}"
    
class ProcedimentoPreventivo(models.Model):
    codigo = models.CharField(max_length=50, unique=True, verbose_name="Código da Preventiva")
    nome = models.CharField(max_length=200)
    instrucoes = models.TextField(blank=True, help_text="Passo a passo técnico")
    duracao_estimada_padrao = models.DurationField(help_text="Tempo padrão para esta tarefa")   
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
    ]

    maquina = models.ForeignKey(Maquina, on_delete=models.CASCADE)
    descricao = models.CharField(max_length=255) # Ex: Troca de Rolamento
    colaborador = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='aberta')
    
    # Planejamento (Gantt)
    duracao_estimada = models.DurationField(help_text="Tempo previsto (Ex: 02:00:00 para 2h)")
    data_planejada = models.DateTimeField(default=timezone.now)
    
    # Realizado
    tempo_total_gasto = models.DurationField(default=timezone.timedelta(0))
    ultima_interacao = models.DateTimeField(null=True, blank=True)

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