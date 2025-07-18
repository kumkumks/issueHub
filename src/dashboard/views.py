from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.http import HttpResponseForbidden
from core.models import UserProfile

@login_required
def dashboard_view(request):
    slug = request.GET.get('user')
    if not slug or not hasattr(request.user, 'profile') or request.user.profile.slug != slug:
        return HttpResponseForbidden('You are not allowed to access this dashboard.')
    user = request.user
    user_type = getattr(user.profile, 'user_type', None)
    template_map = {
        'central_admin': 'dashboard/dashboard_central_admin.html',
        'institution_admin': 'dashboard/dashboard_institution_admin.html',
        'departement_incharge': 'dashboard/dashboard_departement_incharge.html',
        'room_incharge': 'dashboard/dashboard_room_incharge.html',
        'maintainer': 'dashboard/dashboard_maintainer.html',
        'general_user': 'dashboard/dashboard_general_user.html',
    }
    context_map = {
        'central_admin': {'user': user, 'user_type': user_type, 'admin_message': 'Central admin specific context.'},
        'institution_admin': {'user': user, 'user_type': user_type, 'institution_message': 'Institution admin context.'},
        'departement_incharge': {'user': user, 'user_type': user_type, 'department_message': 'Department incharge context.'},
        'room_incharge': {'user': user, 'user_type': user_type, 'room_message': 'Room incharge context.'},
        'maintainer': {'user': user, 'user_type': user_type, 'maintainer_message': 'Maintainer context.'},
        'general_user': {'user': user, 'user_type': user_type, 'general_message': 'General user context.'},
    }
    template = template_map.get(user_type, 'dashboard/dashboard.html')
    context = context_map.get(user_type, {'user': user, 'user_type': user_type})
    return render(request, template, context)
