from assets.models import Chamado

def notifications(request):
    if request.user.is_authenticated:
        count = Chamado.objects.filter(status='pendente').count()
        return {'chamados_pendentes_count': count}
    return {}
