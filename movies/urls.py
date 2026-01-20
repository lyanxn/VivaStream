from django.urls import path
from . import views

app_name = 'movies'

urlpatterns = [
    path('', views.home, name='home'),
    path('peliculas/', views.movies_catalog, name='movies_catalog'),
    path('pelicula/<int:movie_id>/', views.movie_detail, name='movie_detail'),
    path('favorito/toggle/<int:movie_id>/', views.toggle_favorite, name='toggle_favorite'),
    path('mis-favoritos/stats/', views.favorites_stats, name='favorites_stats'),
    path('registro/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('mis-favoritos/', views.favorites_view, name='favorites'),
    path('ver/<int:movie_id>/', views.watch_movie, name='watch_movie'),
    path('progreso/<int:movie_id>/', views.update_watch_progress, name='update_progress'),
    path('buscar/', views.search_movies, name='search'),
    path('calificar/<int:movie_id>/', views.rate_movie, name='rate_movie'),
    path('activate/<uidb64>/<token>/', views.activate, name='activate'),
    path('reenviar-activacion/', views.resend_activation_email, name='resend_activation'),
    path('landing/', views.landing_page, name='landing_page'),
    path('recuperar-contrasena/', views.password_reset_request, name='password_reset'),
    path('recuperar-contrasena/enviado/', views.password_reset_done, name='password_reset_done'),
    path('recuperar-contrasena/reset/<uidb64>/<token>/', views.password_reset_confirm, name='password_reset_confirm'),
    path('cambiar-contrasena/', views.change_password_request, name='change_password'),
    path('cambiar-contrasena/confirmar/<uidb64>/<token>/', views.confirm_change_password, name='confirm_change_password'),
    path('mi-perfil/', views.user_profile, name='profile'),
]
