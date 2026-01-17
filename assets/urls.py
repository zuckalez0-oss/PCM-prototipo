from django.urls import path
from . import views

urlpatterns = [
    # Rotas de Lista e Chamados
    path('lista/', views.lista_atividades, name='lista_atividades'),
    path('chamado/novo/', views.abrir_chamado, name='abrir_chamado'),
    path('chamado/aprovar/<int:chamado_id>/', views.aprovar_chamado, name='aprovar_chamado'),
    path('chamado/recusar/<int:chamado_id>/', views.recusar_chamado, name='recusar_chamado'),
    
    # Rotas de Operação (Técnicos e Status)
    path('atividade/tecnicos/<int:atividade_id>/', views.atribuir_tecnicos, name='atribuir_tecnicos'),
    path('status/<int:atividade_id>/<str:novo_status>/', views.alterar_status, name='alterar_status'),
    
    # --- NOVAS ROTAS (DASHBOARD & GANTT) ---
    # Substituímos a antiga 'pagina_gantt' por 'dashboard_analitico'
    path('dashboard/', views.dashboard_analitico, name='dashboard_analitico'),
    
    # API que alimenta o gráfico
    path('api/gantt/dados/', views.dados_gantt, name='dados_gantt'),
]