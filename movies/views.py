from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, logout
from django.contrib.auth.tokens import default_token_generator
from django.contrib.auth.models import User
from django.contrib.sites.shortcuts import get_current_site
from django.urls import reverse
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from .forms import CustomUserCreationForm, CustomAuthenticationForm
from django_ratelimit.decorators import ratelimit
from django.contrib import messages
from django.http import HttpResponse
from django.views.decorators.http import require_POST
from .models import Movie, Genre, Favorite, WatchHistory, Rating
from django.db.models import Q, Avg, Count
from django.utils.html import escape
import re
import logging
from django.utils import timezone
from datetime import timedelta
from django.conf import settings

logger = logging.getLogger('movies')
security_logger = logging.getLogger('django.security')

def get_movie_suggestion(user):
    try:
        generos_favoritos = Genre.objects.filter(
            peliculas__favoritos__usuario=user
        ).distinct()
        
        if not generos_favoritos.exists():
            generos_favoritos = Genre.objects.filter(
                peliculas__visualizaciones__usuario=user
            ).distinct()
        
        peliculas_vistas = Movie.objects.filter(
            Q(visualizaciones__usuario=user) | Q(favoritos__usuario=user)
        ).distinct()
        
        sugerencias = Movie.objects.filter(
            generos__in=generos_favoritos
        ).exclude(
            id__in=peliculas_vistas
        ).distinct().annotate(
            calificacion=Avg('calificaciones__puntuacion'),
            num_calificaciones=Count('calificaciones')
        ).order_by('-calificacion', '-num_calificaciones', '-fecha_agregado')
        
        if sugerencias.exists():
            return sugerencias.first()
        
        pelicula_popular = Movie.objects.exclude(
            id__in=peliculas_vistas
        ).annotate(
            calificacion=Avg('calificaciones__puntuacion'),
            num_calificaciones=Count('calificaciones')
        ).order_by('-calificacion', '-num_calificaciones', '-fecha_agregado').first()
        
        return pelicula_popular
    
    except Exception as e:
        logger.error(f"Error al obtener sugerencia para usuario {user.username}: {e}")
        return Movie.objects.order_by('?').first()

def home(request):
    if not request.user.is_authenticated:
        return landing_page(request)
    
    peliculas_continuar = []
    historial_activo = WatchHistory.objects.filter(
        usuario=request.user,
        completado=False,
        timestamp__gt=0
    ).select_related('pelicula').order_by('-ultima_visualizacion')
    
    for historial in historial_activo:
        porcentaje = historial.progreso_porcentaje()
        if 5 <= porcentaje < 95:
            peliculas_continuar.append({
                'pelicula': historial.pelicula,
                'progreso': porcentaje,
                'timestamp': historial.timestamp,
                'ultima_visualizacion': historial.ultima_visualizacion
            })
    
    peliculas_continuar = peliculas_continuar[:6]
    
    generos_usuario_stats = Genre.objects.filter(
        peliculas__visualizaciones__usuario=request.user
    ).distinct().annotate(
        num_vistas=Count('peliculas__visualizaciones', filter=Q(peliculas__visualizaciones__usuario=request.user)),
        calificacion_promedio=Avg('peliculas__calificaciones__puntuacion', filter=Q(peliculas__calificaciones__usuario=request.user))
    ).order_by('-num_vistas', '-calificacion_promedio')[:2]
    
    generos_usuario = []
    for genero in generos_usuario_stats:
        peliculas = genero.peliculas.all()[:10]
        generos_usuario.append({
            'genero': genero,
            'peliculas': peliculas
        })
    
    peliculas_top_vistas = Movie.objects.annotate(
        num_vistas=Count('visualizaciones')
    ).order_by('-num_vistas')[:5]
    
    genero_global = Genre.objects.filter(
        peliculas__isnull=False
    ).distinct().annotate(
        num_vistas=Count('peliculas__visualizaciones'),
        calificacion_promedio=Avg('peliculas__calificaciones__puntuacion')
    ).order_by('-num_vistas', '-calificacion_promedio').first()
    
    peliculas_genero_global = []
    if genero_global:
        peliculas_genero_global = genero_global.peliculas.all()[:10]
    
    pelicula_sugerida = get_movie_suggestion(request.user)
    
    context = {
        'pelicula_sugerida': pelicula_sugerida,
        'peliculas_continuar': peliculas_continuar,
        'generos_usuario': generos_usuario,
        'peliculas_top_vistas': peliculas_top_vistas,
        'genero_global': genero_global,
        'peliculas_genero_global': peliculas_genero_global,
        'titulo_pagina': 'Inicio'
    }
    
    return render(request, 'movies/pages/home.html', context)


@login_required
def movies_catalog(request):
    generos_con_peliculas = Genre.objects.filter(peliculas__isnull=False).distinct()
    
    peliculas_por_genero = {}
    for genero in generos_con_peliculas:
        peliculas_por_genero[genero] = genero.peliculas.all() # type: ignore
    
    context = {
        'peliculas_por_genero': peliculas_por_genero,
        'titulo_pagina': 'Catálogo de Películas'
    }
    
    return render(request, 'movies/pages/catalog.html', context)


def landing_page(request):
    peliculas_con_calificaciones = Movie.objects.filter(
        calificaciones__isnull=False
    ).distinct().prefetch_related('calificaciones')
    
    peliculas_con_promedio = [
        (pelicula, pelicula.calificacion_promedio()) 
        for pelicula in peliculas_con_calificaciones 
        if pelicula.calificacion_promedio() > 0
    ]
    
    peliculas_con_promedio.sort(key=lambda x: x[1], reverse=True)
    peliculas_destacadas = [pelicula for pelicula, _ in peliculas_con_promedio[:6]]
    
    if len(peliculas_destacadas) < 6:
        otras_peliculas = Movie.objects.exclude(
            id__in=[p.id for p in peliculas_destacadas] # type: ignore
        ).order_by('-fecha_agregado')[:6-len(peliculas_destacadas)]
        peliculas_destacadas.extend(otras_peliculas)
    
    total_peliculas = Movie.objects.count()
    total_generos = Genre.objects.count()
    
    context = {
        'peliculas_destacadas': peliculas_destacadas,
        'total_peliculas': total_peliculas,
        'total_generos': total_generos,
        'is_landing_page': True,
    }
    
    return render(request, 'movies/pages/landing.html', context)

@login_required
def movie_detail(request, movie_id):
    pelicula = get_object_or_404(Movie, id=movie_id)
    
    es_favorito = False
    progreso = None
    rating_usuario = None
    
    if request.user.is_authenticated:
        es_favorito = Favorite.objects.filter(
            usuario=request.user,
            pelicula=pelicula
        ).exists()
        
        progreso = WatchHistory.objects.filter(
            usuario=request.user,
            pelicula=pelicula
        ).first()
        
        rating_usuario = Rating.objects.filter(
            usuario=request.user,
            pelicula=pelicula
        ).first()
    
    generos_pelicula = pelicula.generos.all()  # type: ignore
    
    peliculas_relacionadas = Movie.objects.filter(
        generos__in=generos_pelicula
    ).exclude(
        id=pelicula.id # type: ignore
    ).distinct().annotate(
        generos_comunes=Count('generos', filter=Q(generos__in=generos_pelicula))
    ).order_by('-generos_comunes', '-fecha_agregado')[:8]
    
    context = {
        'pelicula': pelicula,
        'es_favorito': es_favorito,
        'progreso': progreso,
        'peliculas_relacionadas': peliculas_relacionadas,
        'rating_usuario': rating_usuario,
    }
    
    return render(request, 'movies/pages/movie_detail.html', context)

@login_required
@require_POST
def toggle_favorite(request, movie_id):
    pelicula = get_object_or_404(Movie, id=movie_id)
    
    favorito, created = Favorite.objects.get_or_create(
        usuario=request.user,
        pelicula=pelicula
    )
    
    if not created:
        favorito.delete()
        es_favorito = False
    else:
        es_favorito = True
    
    referer = request.META.get('HTTP_REFERER', '')
    
    if 'mis-favoritos' in referer and not es_favorito:
        favoritos_restantes = Favorite.objects.filter(usuario=request.user).exists()
        response = HttpResponse('')
        response['X-Favoritos-Restantes'] = 'true' if favoritos_restantes else 'false'
        return response
    
    return render(request, 'movies/components/favorite_button.html', {
        'pelicula': pelicula,
        'es_favorito': es_favorito
    })


def register_view(request):
    if request.user.is_authenticated:
        return redirect('movies:home')
    
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            
            send_activation_email(request, user)
            
            messages.info(request, 'Te hemos enviado un email de verificación. Por favor revisa tu bandeja de entrada.')
            logger.info(f'Nuevo registro: usuario={user.username}, email={user.email}, requiere verificación')
            
            return render(request, 'movies/registration/account_activation_sent.html', {
                'email': user.email,
                'is_register_page': True
            })
    else:
        form = CustomUserCreationForm()
        
    return render(request, 'movies/auth/register.html', {'form': form, 'is_register_page': True})


def send_activation_email(request, user):
    current_site = get_current_site(request)
    mail_subject = 'Activa tu cuenta de VivaStream'
    message = render_to_string('movies/registration/account_activation_email.html', {
        'user': user,
        'domain': current_site.domain,
        'protocol': 'https' if request.is_secure() else 'http',
        'uid': urlsafe_base64_encode(force_bytes(user.pk)),
        'token': default_token_generator.make_token(user),
    })
    send_mail(mail_subject, message, settings.DEFAULT_FROM_EMAIL, [user.email], html_message=message)


def resend_activation_email(request):
    if request.user.is_authenticated:
        return redirect('movies:home')
    
    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        
        try:
            user = User.objects.get(email=email)
            
            if user.is_active:
                messages.warning(request, 'Esta cuenta ya está activada.')
                return redirect('movies:login')
            
            send_activation_email(request, user)
            logger.info(f'Email de activación reenviado a: {email}')
            
            return render(request, 'movies/registration/account_activation_sent.html', {
                'email': email,
                'is_resend': True,
                'is_register_page': True
            })
        
        except User.DoesNotExist:
            messages.info(request, 'Si existe una cuenta con ese email, recibirás un correo de activación.')
            return render(request, 'movies/registration/account_activation_sent.html', {
                'email': email,
                'is_resend': True,
                'is_register_page': True
            })
    
    return render(request, 'movies/registration/resend_activation.html', {
        'is_register_page': True
    })

def activate(request, uidb64, token):
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except(TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None
    
    if user is not None and default_token_generator.check_token(user, token):
        token_age = timezone.now() - user.date_joined
        max_age = timedelta(days=getattr(settings, 'ACCOUNT_ACTIVATION_TOKEN_EXPIRY_DAYS', 3))
        
        if token_age > max_age:
            return render(request, 'movies/registration/account_activation_invalid.html', {
                'is_expired': True,
                'is_login_page': True
            })
        
        user.is_active = True
        user.save()
        login(request, user)
        logger.info(f'Cuenta activada: usuario={user.username}')
        return redirect('movies:home')
    else:
        return render(request, 'movies/registration/account_activation_invalid.html', {
            'is_expired': False,
            'is_login_page': True
        })


@ratelimit(key='ip', rate='5/m', method='POST', block=False)
def login_view(request):
    if request.user.is_authenticated:
        return redirect('movies:home')
    
    was_limited = getattr(request, 'limited', False)
    if was_limited:
        security_logger.warning(
            f'Rate limit excedido en login. IP: {request.META.get("REMOTE_ADDR")}'
        )
        return render(request, 'movies/errors/rate_limited.html', {
            'retry_after': 60,
            'attempts_allowed': 5,
            'is_rate_limited_page': True,
        })
    
    if request.method == 'POST':
        form = CustomAuthenticationForm(request, data=request.POST)
        
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            
            logger.info(f'Login exitoso: usuario={user.username}, IP={request.META.get("REMOTE_ADDR")}')
            
            next_url = request.GET.get('next', 'movies:home')
            return redirect(next_url)
        else:
            username_attempt = request.POST.get('username', 'unknown')
            security_logger.warning(
                f'Intento de login fallido: usuario={username_attempt}, IP={request.META.get("REMOTE_ADDR")}'
            )
            
            if 'captcha' not in form.errors:
                if form.non_field_errors():
                    for error in form.non_field_errors():
                        messages.error(request, str(error))
                else:
                    messages.error(request, 'Usuario o contraseña incorrectos.')
    else:
        form = CustomAuthenticationForm()
    
    return render(request, 'movies/auth/login.html', {'form': form, 'is_login_page': True})


@login_required
def logout_view(request):
    username = request.user.username if request.user.is_authenticated else 'anonymous'
    ip_address = request.META.get('REMOTE_ADDR')
    
    logout(request)
    logger.info(f'Logout exitoso: usuario={username}, IP={ip_address}')
    
    response = redirect('movies:landing_page')
    
    return response


@login_required
def favorites_view(request):
    favoritos = Favorite.objects.filter(usuario=request.user).select_related('pelicula').prefetch_related('pelicula__generos')
    
    genero_filter = request.GET.get('genero', '')
    order_by = request.GET.get('order', '-fecha_agregado')
    
    if genero_filter:
        favoritos = [
            fav for fav in favoritos 
            if fav.pelicula.generos.filter(id=genero_filter).exists()  # type: ignore
        ]
    
    if order_by == 'titulo':
        favoritos = sorted(favoritos, key=lambda x: x.pelicula.titulo)
    elif order_by == '-titulo':
        favoritos = sorted(favoritos, key=lambda x: x.pelicula.titulo, reverse=True)
    elif order_by == 'fecha_agregado':
        favoritos = sorted(favoritos, key=lambda x: x.fecha_agregado)
    else:  # '-fecha_agregado' (por defecto)
        favoritos = sorted(favoritos, key=lambda x: x.fecha_agregado, reverse=True)
    
    peliculas_favoritas = [favorito.pelicula for favorito in favoritos]
    
    total_favoritos = len(peliculas_favoritas)
    duracion_total = sum(pelicula.duracion for pelicula in peliculas_favoritas) // 60
    
    generos_count = {}
    for pelicula in peliculas_favoritas:
        for genero in pelicula.generos.all():  # type: ignore
            genero_nombre = genero.nombre
            generos_count[genero_nombre] = generos_count.get(genero_nombre, 0) + 1
    
    generos_favoritos = sorted(generos_count.items(), key=lambda x: x[1], reverse=True)[:3]
    
    todos_los_generos = Genre.objects.filter(peliculas__in=[p.id for p in peliculas_favoritas]).distinct().order_by('nombre')
    
    context = {
        'peliculas_favoritas': peliculas_favoritas,
        'total_favoritos': total_favoritos,
        'duracion_total': duracion_total,
        'generos_favoritos': generos_favoritos,
        'todos_los_generos': todos_los_generos,
        'genero_filter': genero_filter,
        'order_by': order_by,
    }
    
    if request.headers.get('HX-Request'):
        return render(request, 'movies/pages/favorites_partial.html', context)
    
    return render(request, 'movies/pages/favorites.html', context)

@login_required
def favorites_stats(request):
    usuario = request.user
    
    favoritos = Favorite.objects.filter(usuario=usuario).select_related('pelicula')
    peliculas_favoritas = [favorito.pelicula for favorito in favoritos]
    
    total_favoritos = len(peliculas_favoritas)
    duracion_total = sum(p.duracion_minutos or 0 for p in peliculas_favoritas)
    
    generos_contador = {}
    for pelicula in peliculas_favoritas:
        for genero in pelicula.generos.all():
            generos_contador[genero.nombre] = generos_contador.get(genero.nombre, 0) + 1
    
    generos_favoritos = sorted(
        generos_contador.items(),
        key=lambda x: x[1],
        reverse=True
    )[:4]
    
    context = {
        'total_favoritos': total_favoritos,
        'duracion_total': duracion_total,
        'generos_favoritos': generos_favoritos,
    }
    
    return render(request, 'movies/components/favorites_stats.html', context)

@login_required
def watch_movie(request, movie_id):
    pelicula = get_object_or_404(Movie, id=movie_id)
    
    historial = WatchHistory.objects.filter(
        usuario=request.user,
        pelicula=pelicula
    ).first()
    
    timestamp_inicial = historial.timestamp if historial else 0
    
    context = {
        'pelicula': pelicula,
        'timestamp_inicial': timestamp_inicial,
        'historial': historial,
    }
    
    return render(request, 'movies/pages/watch.html', context)

@login_required
@require_POST
def update_watch_progress(request, movie_id):
    pelicula = get_object_or_404(Movie, id=movie_id)
    
    timestamp = int(request.POST.get('timestamp', 0))
    
    porcentaje_visto = (timestamp / pelicula.duracion) * 100 if pelicula.duracion > 0 else 0
    completado = porcentaje_visto >= 90
    
    historial, created = WatchHistory.objects.get_or_create(
        usuario=request.user,
        pelicula=pelicula,
        defaults={'timestamp': timestamp, 'completado': completado}
    )
    
    if not created:
        historial.timestamp = timestamp
        historial.completado = completado
        historial.save()
    
    return HttpResponse(status=200)

@login_required
def search_movies(request):
    query = request.GET.get('q', '').strip()
    
    query_display = escape(query)
    
    resultados = []
    error = None
    
    if query and len(query) >= 2:
        try:
            resultados = Movie.objects.filter(
                Q(titulo__icontains=query) | 
                Q(descripcion__icontains=query)
            ).prefetch_related('generos')[:15]
        except Exception as e:
            error = "Error en la búsqueda"
    
    return render(request, 'movies/components/search_results.html', {
        'resultados': resultados,
        'query': query_display,
        'query_length': len(query),
        'error': error
    })

@login_required
@require_POST
def rate_movie(request, movie_id):
    pelicula = get_object_or_404(Movie, id=movie_id)
    
    puntuacion = request.POST.get('puntuacion')
    
    try:
        puntuacion = int(puntuacion)
        if puntuacion < 1 or puntuacion > 5:
            raise ValueError
    except (ValueError, TypeError):
        return HttpResponse('Puntuación inválida', status=400)
    
    rating, created = Rating.objects.update_or_create(
        usuario=request.user,
        pelicula=pelicula,
        defaults={
            'puntuacion': puntuacion,
        }
    )
    
    if created:
        logger.info(f'Nueva calificación: {request.user.username} calificó {pelicula.titulo} con {puntuacion} estrellas')
    else:
        logger.info(f'Calificación actualizada: {request.user.username} cambió calificación de {pelicula.titulo} a {puntuacion} estrellas')
    
    context = {
        'pelicula': pelicula,
        'rating_usuario': rating,
        'calificacion_promedio': pelicula.calificacion_promedio(),
        'total_calificaciones': pelicula.total_calificaciones(),
    }
    
    return render(request, 'movies/components/rating_display.html', context)


@ratelimit(key='ip', rate='3/h', method='POST', block=False)
def password_reset_request(request):
    from .forms import CustomPasswordResetForm
    
    if request.user.is_authenticated:
        return redirect('movies:home')
    
    was_limited = getattr(request, 'limited', False)
    if was_limited:
        security_logger.warning(
            f'Rate limit excedido en password reset. IP: {request.META.get("REMOTE_ADDR")}'
        )
        messages.error(request, 'Has solicitado demasiados resets de contraseña. Intenta más tarde.')
        return render(request, 'movies/auth/password_reset.html', {
            'retry_after': 3600,
            'rate_limited': True,
            'is_password_reset_page': True
        })
    
    if request.method == 'POST':
        form = CustomPasswordResetForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            user = User.objects.get(email=email)
            
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = default_token_generator.make_token(user)
            
            current_site = get_current_site(request)
            reset_path = reverse('movies:password_reset_confirm', kwargs={'uidb64': uid, 'token': token})
            reset_url = f"{request.scheme}://{current_site.domain}{reset_path}"
            
            subject = 'Recupera tu contraseña de VivaStream'
            html_message = render_to_string(
                'movies/email/password_reset_email.html',
                {
                    'user': user,
                    'reset_url': reset_url,
                    'domain': current_site.domain,
                }
            )
            
            try:
                send_mail(
                    subject,
                    f'Haz clic en este enlace para recuperar tu contraseña: {reset_url}',
                    settings.DEFAULT_FROM_EMAIL,
                    [email],
                    html_message=html_message,
                    fail_silently=False,
                )
                logger.info(f'Email de recuperación enviado a: {email}')
                return redirect('movies:password_reset_done')
            except Exception as e:
                logger.error(f'Error enviando email de recuperación: {str(e)}')
                messages.error(request, 'Hubo un error al enviar el email. Por favor intenta más tarde.')
    else:
        form = CustomPasswordResetForm()
    
    return render(request, 'movies/auth/password_reset.html', {'form': form, 'is_password_reset_page': True})


def password_reset_done(request):
    return render(request, 'movies/auth/password_reset_done.html', {'is_password_reset_page': True})


@ratelimit(key='ip', rate='5/h', method='POST', block=False)
def password_reset_confirm(request, uidb64, token):
    from .forms import CustomSetPasswordForm
    
    was_limited = getattr(request, 'limited', False)
    if was_limited:
        messages.error(request, 'Demasiados intentos. Por favor intenta más tarde.')
        return render(request, 'movies/auth/password_reset_confirm.html', {
            'rate_limited': True,
            'is_password_reset_page': True
        })
    
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None
    
    if user is not None and default_token_generator.check_token(user, token):
        if request.method == 'POST':
            form = CustomSetPasswordForm(user, request.POST)
            if form.is_valid():
                form.save()
                logger.info(f'Contraseña cambiada exitosamente para usuario: {user.username}')
                if request.user.is_authenticated:
                    logout(request)
                return redirect('movies:login')
        else:
            form = CustomSetPasswordForm(user)
        
        return render(request, 'movies/auth/password_reset_confirm.html', {
            'form': form,
            'uidb64': uidb64,
            'token': token,
            'valid_link': True,
            'is_password_reset_page': True
        })
    else:
        logger.warning(f'Intento de reset con token inválido. IP: {request.META.get("REMOTE_ADDR")}')
        return render(request, 'movies/auth/password_reset_confirm.html', {
            'valid_link': False,
            'error_message': 'El enlace de recuperación es inválido o ha expirado.',
            'is_password_reset_page': True
        })


@login_required
def user_profile(request):
    from .models import WatchHistory
    from django.utils import timezone
    from datetime import timedelta
    
    user = request.user
    
    fecha_registro = user.date_joined
    dias_registrado = (timezone.now() - fecha_registro).days
    
    historiales = WatchHistory.objects.filter(usuario=user)
    
    total_horas_vistas = 0
    peliculas_completadas = 0
    peliculas_en_progreso = 0
    
    for historial in historiales:
        total_horas_vistas += historial.pelicula.duracion // 3600
        
        if historial.completado:
            peliculas_completadas += 1
        else:
            peliculas_en_progreso += 1
    
    genero_mas_visto = None
    if historiales.exists():
        genero_mas_visto = (
            Genre.objects
            .annotate(vistas=Count('peliculas__visualizaciones', distinct=True))
            .filter(vistas__gt=0)
            .order_by('-vistas')
            .first()
        )
    
    ultimas_peliculas = historiales.select_related('pelicula').order_by('-ultima_visualizacion')[:5]
    
    context = {
        'fecha_registro': fecha_registro,
        'dias_registrado': dias_registrado,
        'total_horas_vistas': total_horas_vistas,
        'peliculas_completadas': peliculas_completadas,
        'peliculas_en_progreso': peliculas_en_progreso,
        'genero_mas_visto': genero_mas_visto,
        'ultimas_peliculas': ultimas_peliculas,
    }
    
    return render(request, 'movies/pages/profile.html', context)


@login_required
def change_password_request(request):
    user = request.user
    
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    
    current_site = get_current_site(request)
    confirm_path = reverse('movies:confirm_change_password', kwargs={'uidb64': uid, 'token': token})
    confirm_url = f"{request.scheme}://{current_site.domain}{confirm_path}"
    
    subject = 'Verifica tu solicitud de cambio de contraseña - VivaStream'
    html_message = render_to_string(
        'movies/email/change_password_email.html',
        {
            'user': user,
            'protocol': request.scheme,
            'domain': current_site.domain,
            'uid': uid,
            'token': token,
        }
    )
    
    try:
        send_mail(
            subject,
            f'Haz clic en este enlace para cambiar tu contraseña: {confirm_url}',
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
            html_message=html_message,
            fail_silently=False,
        )
        logger.info(f'Email de cambio de contraseña enviado a: {user.email}')
        return render(request, 'movies/auth/change_password.html', {'is_password_reset_page': True})
    except Exception as e:
        logger.error(f'Error enviando email de cambio de contraseña: {str(e)}')
        messages.error(request, 'Hubo un error al enviar el email. Por favor intenta más tarde.')
        return redirect('movies:profile')


@ratelimit(key='ip', rate='5/h', method='POST', block=False)
def confirm_change_password(request, uidb64, token):
    from .forms import CustomSetPasswordForm
    
    was_limited = getattr(request, 'limited', False)
    if was_limited:
        messages.error(request, 'Demasiados intentos. Por favor intenta más tarde.')
        return render(request, 'movies/auth/change_password_confirm.html', {
            'rate_limited': True,
            'is_password_reset_page': True
        })
    
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None
    
    if user is not None and default_token_generator.check_token(user, token):
        if request.user.is_authenticated and request.user.pk != user.pk:
            logger.warning(
                f'Usuario {request.user.username} intentó cambiar contraseña de {user.username}. '
                f'Sesión incorrecta - logout automático. IP: {request.META.get("REMOTE_ADDR")}'
            )
            logout(request)
            messages.warning(
                request, 
                f'Detectamos que estabas logueado con otra cuenta. Hemos cerrado esa sesión por seguridad. '
                f'Ahora puedes proceder con el cambio de contraseña de tu cuenta {user.username}.'
            )
        
        if request.method == 'POST':
            form = CustomSetPasswordForm(user, request.POST)
            if form.is_valid():
                form.save()
                logger.info(f'Contraseña cambiada exitosamente desde perfil para usuario: {user.username}')
                
                logout(request)
                
                security_logger.warning(
                    f'Usuario {user.username} cambió su contraseña desde el perfil. Sesión cerrada por seguridad.'
                )
                
                return redirect('movies:login')
        else:
            form = CustomSetPasswordForm(user)
        
        return render(request, 'movies/auth/change_password_confirm.html', {
            'form': form,
            'uidb64': uidb64,
            'token': token,
            'valid_link': True,
            'target_user': user,
            'is_password_reset_page': True
        })
    else:
        logger.warning(f'Intento de cambio de contraseña con token inválido. IP: {request.META.get("REMOTE_ADDR")}')
        return render(request, 'movies/auth/change_password_confirm.html', {
            'valid_link': False,
            'error_message': 'El enlace de cambio de contraseña es inválido o ha expirado.',
            'is_password_reset_page': True
        })
