from django.contrib import admin
from django import forms
from .models import Genre, Movie, Favorite, WatchHistory, Rating

class MovieAdminForm(forms.ModelForm):
    duracion_display = forms.CharField(
        label='Duración (HH:MM:SS o MM:SS)',
        required=True,
        help_text='Ingresa la duración en formato HH:MM:SS (ej: 1:30:45) o MM:SS (ej: 90:45)',
        widget=forms.TextInput(attrs={'placeholder': 'HH:MM:SS'})
    )
    
    class Meta:
        model = Movie
        fields = ['titulo', 'descripcion', 'duracion_display', 'año_publicacion', 'imagen', 'enlace_stream', 'generos']
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            horas = self.instance.duracion // 3600
            minutos = (self.instance.duracion % 3600) // 60
            segundos = self.instance.duracion % 60
            if horas > 0:
                self.fields['duracion_display'].initial = f"{horas}:{minutos:02d}:{segundos:02d}"
            else:
                self.fields['duracion_display'].initial = f"{minutos}:{segundos:02d}"
        if 'duracion' in self.fields:
            del self.fields['duracion']
    
    def clean_duracion_display(self):
        duracion_str = self.cleaned_data.get('duracion_display', '').strip()
        
        if not duracion_str:
            raise forms.ValidationError("La duración es requerida")
        
        try:
            partes = duracion_str.split(':')
            
            if len(partes) == 3:
                horas, minutos, segundos = map(int, partes)
            elif len(partes) == 2:
                horas = 0
                minutos, segundos = map(int, partes)
            else:
                raise ValueError("Formato inválido")
            
            if not (0 <= minutos < 60 and 0 <= segundos < 60):
                raise ValueError("Minutos y segundos deben estar entre 0-59")
            
            duracion_segundos = horas * 3600 + minutos * 60 + segundos
            
            if duracion_segundos <= 0:
                raise forms.ValidationError("La duración debe ser mayor a 0 segundos")
            
            return duracion_segundos
        
        except (ValueError, TypeError):
            raise forms.ValidationError(
                "Formato de duración inválido. Usa HH:MM:SS o MM:SS (ej: 1:30:45 o 90:45)"
            )
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.duracion = self.cleaned_data['duracion_display']
        if commit:
            instance.save()
        return instance

@admin.register(Genre)
class GenreAdmin(admin.ModelAdmin):
    list_display = ['nombre']
    search_fields = ['nombre']
    ordering = ['nombre']


@admin.register(Movie)
class MovieAdmin(admin.ModelAdmin):
    form = MovieAdminForm
    list_display = ['titulo', 'año_publicacion', 'duracion_formateada', 'fecha_agregado']
    list_filter = ['generos', 'año_publicacion', 'fecha_agregado']
    search_fields = ['titulo', 'descripcion', 'año_publicacion', 'generos__nombre']
    ordering = ['-fecha_agregado']
    date_hierarchy = 'fecha_agregado'
    
    fieldsets = (
        ('Información Básica', {
            'fields': ('titulo', 'descripcion', 'año_publicacion', 'generos')
        }),
        ('Detalles Técnicos', {
            'fields': ('duracion_display', 'enlace_stream', 'imagen')
        }),
    )
    
    def duracion_formateada(self, obj):
        return obj.duracion_formateada()
    duracion_formateada.short_description = 'Duración'


@admin.register(Favorite)
class FavoriteAdmin(admin.ModelAdmin):
    list_display = ['usuario', 'pelicula', 'fecha_agregado']
    list_filter = ['fecha_agregado']
    search_fields = ['usuario__username', 'pelicula__titulo']
    ordering = ['-fecha_agregado']
    date_hierarchy = 'fecha_agregado'
    
    autocomplete_fields = ['usuario', 'pelicula']


@admin.register(WatchHistory)
class WatchHistoryAdmin(admin.ModelAdmin):
    list_display = ['usuario', 'pelicula', 'timestamp_display', 'progreso_display', 'completado', 'ultima_visualizacion']
    list_filter = ['completado', 'ultima_visualizacion']
    search_fields = ['usuario__username', 'pelicula__titulo']
    ordering = ['-ultima_visualizacion']
    date_hierarchy = 'ultima_visualizacion'
    autocomplete_fields = ['usuario', 'pelicula']
    
    readonly_fields = ['ultima_visualizacion']
    
    def timestamp_display(self, obj):
        minutos = obj.timestamp // 60
        segundos = obj.timestamp % 60
        return f"{minutos}:{segundos:02d}"
    timestamp_display.short_description = 'Tiempo (mm:ss)'
    
    def progreso_display(self, obj):
        porcentaje = obj.progreso_porcentaje()
        return f"{porcentaje:.1f}%"
    progreso_display.short_description = 'Progreso'

@admin.register(Rating)
class RatingAdmin(admin.ModelAdmin):
    list_display = ['usuario', 'pelicula', 'puntuacion', 'fecha_creacion']
    list_filter = ['puntuacion', 'fecha_creacion']
    search_fields = ['usuario__username', 'pelicula__titulo', 'resena']
    readonly_fields = ['fecha_creacion', 'fecha_modificacion']
    autocomplete_fields = ['usuario', 'pelicula']
    
    fieldsets = (
        ('Información Básica', {
            'fields': ('usuario', 'pelicula', 'puntuacion')
        }),
        ('Reseña', {
            'fields': ('resena',)
        }),
        ('Fechas', {
            'fields': ('fecha_creacion', 'fecha_modificacion'),
            'classes': ('collapse',)
        }),
    )