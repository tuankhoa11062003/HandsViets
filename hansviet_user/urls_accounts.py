from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

app_name = 'auth'

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('register/', views.register_view, name='register'),
    # Logout allows GET to prevent 405 in static menus
    path('logout/', views.logout_view, name='logout'),
]
