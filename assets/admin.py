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
    # 1. Configurações de Interface
    filter_horizontal = ('colaboradores',) 
    
    # 2. O que aparece na tabela (colaboradores substituído por exibir_tecnicos)
    list_display = (
        'id', 'maquina', 'descricao', 'exibir_tecnicos', 
        'status', 'data_planejada', 'tempo_total_gasto'
    )
    
    # 3. Filtros laterais
    list_filter = ('status', 'maquina', 'data_planejada')

    # 4. Busca rápida
    search_fields = ('descricao', 'maquina__nome', 'maquina__codigo')
    
    # 5. Edição direta na lista (Removido colaboradores pois o Django não permite em ManyToMany)
    list_editable = ('status',)

    # 6. Organização do formulário de edição
    fieldsets = (
        ('Informações Básicas', {
            'fields': ('maquina', 'descricao', 'colaboradores', 'status', 'motivo_pausa')
        }),
        ('Planejamento (Gantt)', {
            'fields': ('duracao_estimada', 'data_planejada', 'eh_emergencial')
        }),
        ('Execução Real', {
            'fields': ('tempo_total_gasto', 'ultima_interacao'),
            'classes': ('collapse',) 
        }),
    )

    # 7. Função Auxiliar para exibir múltiplos técnicos na lista
    def exibir_tecnicos(self, obj):
        return ", ".join([t.first_name or t.username for t in obj.colaboradores.all()])
    
    exibir_tecnicos.short_description = 'Técnicos Responsáveis'