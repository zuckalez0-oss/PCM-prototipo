from django.urls import path
from . import views

urlpatterns = [
    # --- ROTA PRINCIPAL (Home) ---
    path('', views.home, name='home'), 
    
    # --- KANBAN / LISTA (Antiga Lista Atividades) ---
    path('kanban/', views.kanban_view, name='kanban_view'),
    # Mantendo rota antiga redirecionando ou como alias se necessário, mas removendo do menu
    # path('lista/', views.lista_atividades, name='lista_atividades'), 

    # --- DASHBOARD E ANÁLISE (Novas Funcionalidades) ---
    path('dashboard/', views.dashboard_analitico, name='dashboard_analitico'), # O novo painel com gráficos
    path('api/gantt/dados/', views.dados_gantt, name='dados_gantt'), # A API que alimenta o gráfico Gantt

    # --- GESTÃO DE CHAMADOS ---
    path('chamado/novo/', views.abrir_chamado, name='abrir_chamado'),
    path('notificacoes/', views.notificacoes_dropdown, name='notificacoes_dropdown'),
    path('chamado/aprovar/<int:chamado_id>/', views.aprovar_chamado, name='aprovar_chamado'),
    path('chamado/recusar/<int:chamado_id>/', views.recusar_chamado, name='recusar_chamado'),

    # --- AÇÕES NAS ATIVIDADES (Operacional) ---
    # Atribuição de Técnicos
    path('atividade/<int:atividade_id>/atribuir/', views.atribuir_tecnicos, name='atribuir_tecnicos'),
    
    # Mudança de Status (HTMX usa muito isso)
    path('status/<int:atividade_id>/<str:novo_status>/', views.alterar_status, name='alterar_status'),
    
    # Cancelamento (A rota que estava faltando a view antes)
    path('atividade/cancelar/<int:atividade_id>/', views.cancelar_atividade, name='cancelar_atividade'),

    # --- SISTEMA ---
    path('logout/', views.logout_view, name='logout'),
]