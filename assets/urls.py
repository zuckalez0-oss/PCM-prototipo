from django.urls import path
from . import views

urlpatterns = [
    # O primeiro parâmetro é o que aparece na URL
    # O segundo é a função dentro do views.py
    path('', views.lista_atividades, name='lista_atividades'), 
    path('status/<int:atividade_id>/<str:novo_status>/', views.alterar_status, name='alterar_status'),
    path('gantt/', views.pagina_gantt, name='pagina_gantt'),
    path('api/gantt/dados/', views.dados_gantt, name='dados_gantt'),

    
]