from django.urls import path
from . import views

urlpatterns = [
    # O primeiro parâmetro é o que aparece na URL
    # O segundo é a função dentro do views.py
    path('', views.lista_atividades, name='lista_atividades'), 
    path('status/<int:atividade_id>/<str:novo_status>/', views.alterar_status, name='alterar_status'),
    path('gantt/', views.pagina_gantt, name='pagina_gantt'),
    path('api/gantt/dados/', views.dados_gantt, name='dados_gantt'),

    path('chamado/novo/', views.abrir_chamado, name='abrir_chamado'),
    path('chamado/aprovar/<int:chamado_id>/', views.aprovar_chamado, name='aprovar_chamado'),
    path('chamado/recusar/<int:chamado_id>/', views.recusar_chamado, name='recusar_chamado'),
    path('atividade/cancelar/<int:atividade_id>/', views.cancelar_atividade, name='cancelar_atividade'),
    
]