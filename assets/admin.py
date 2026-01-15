from django.contrib import admin
from .models import Maquina, Atividade, ProcedimentoPreventivo

@admin.register(Maquina)
class MaquinaAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'nome')
    search_fields = ('codigo', 'nome')

@admin.register(ProcedimentoPreventivo)
class ProcedimentoPreventivoAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'nome', 'duracao_estimada_padrao')

@admin.register(Atividade)
class AtividadeAdmin(admin.ModelAdmin):
    filter_horizontal = ('colaboradores',) 
    list_display = ('id', 'maquina', 'status', 'eh_emergencial')
    # O que aparece na tabela principal do Admin
    list_display = ('id', 'maquina', 'descricao', 'colaboradores', 'status', 'data_planejada', 'tempo_total_gasto')
    
    # Filtros laterais para facilitar a vida do gestor (Escalabilidade!)
    list_filter = ('status', 'colaboradores', 'maquina', 'data_planejada')

    # Campos que permitem busca rápida
    search_fields = ('descricao', 'maquina__nome', 'maquina__codigo')
    
    # Permite editar o status e o colaborador direto na lista, sem precisar abrir a atividade
    list_editable = ('status', 'colaboradores')

    # Organização dos campos dentro do formulário de edição
    fieldsets = (
        ('Informações Básicas', {
            'fields': ('maquina', 'descricao', 'colaboradores', 'status')
        }),
        ('Planejamento (Gantt)', {
            'fields': ('duracao_estimada', 'data_planejada')
        }),
        ('Execução Real', {
            'fields': ('tempo_total_gasto', 'ultima_interacao'),
            'classes': ('collapse',) # Deixa essa seção escondida por padrão
        }),
    
        
    )