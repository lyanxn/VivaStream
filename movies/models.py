from django.db import models
from django.contrib.auth.models import User

class Genre(models.Model):
    nombre = models.CharField(max_length=100, unique=True)
    
    class Meta:
        verbose_name = "Género"
        verbose_name_plural = "Géneros"
        ordering = ['nombre']
    
    def __str__(self):
        return self.nombre


class Movie(models.Model):
    titulo = models.CharField(max_length=200)
    descripcion = models.TextField()
    duracion = models.IntegerField(help_text="Duración en segundos (ej: 5430 = 1:30:30)")
    año_publicacion = models.IntegerField(null=True, blank=True, help_text="Año de publicación de la película")
    imagen = models.ImageField(upload_to='posters/', blank=True, null=True)
    enlace_stream = models.URLField(max_length=500)
    generos = models.ManyToManyField(
        Genre,
        related_name='peliculas',
        blank=True,
        help_text="Una película puede pertenecer a múltiples géneros"
    )
    fecha_agregado = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Película"
        verbose_name_plural = "Películas"
        ordering = ['-fecha_agregado']
    
    def __str__(self):
        return self.titulo
    
    def duracion_minutos(self):
        return self.duracion // 60
    
    def duracion_formateada(self):
        horas = self.duracion // 3600
        minutos = (self.duracion % 3600) // 60
        segundos = self.duracion % 60
        
        if horas > 0:
            return f"{horas}:{minutos:02d}:{segundos:02d}"
        else:
            return f"{minutos}:{segundos:02d}"
    
    def calificacion_promedio(self):
        calificaciones = self.calificaciones.all()  # type: ignore[attr-defined]
        if calificaciones.exists():
            suma = sum(c.puntuacion for c in calificaciones)
            return round(suma / calificaciones.count(), 1)
        return 0
    
    def total_calificaciones(self):
        return self.calificaciones.count()  # type: ignore[attr-defined]


class Favorite(models.Model):
    usuario = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='favoritos'
    )
    pelicula = models.ForeignKey(
        Movie, 
        on_delete=models.CASCADE, 
        related_name='favoritos'
    )
    fecha_agregado = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Favorito"
        verbose_name_plural = "Favoritos"
        unique_together = ['usuario', 'pelicula']
        ordering = ['-fecha_agregado']
    
    def __str__(self):
        return f"{self.usuario.username} - {self.pelicula.titulo}"


class WatchHistory(models.Model):
    usuario = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='historial'
    )
    pelicula = models.ForeignKey(
        Movie, 
        on_delete=models.CASCADE, 
        related_name='visualizaciones'
    )
    timestamp = models.IntegerField(
        default=0, 
        help_text="Tiempo en segundos donde se pausó"
    )
    ultima_visualizacion = models.DateTimeField(auto_now=True)
    completado = models.BooleanField(default=False)
    
    class Meta:
        verbose_name = "Historial de Visualización"
        verbose_name_plural = "Historiales de Visualización"
        unique_together = ['usuario', 'pelicula']
        ordering = ['-ultima_visualizacion']
    
    def __str__(self):
        return f"{self.usuario.username} viendo {self.pelicula.titulo}"
    
    def progreso_porcentaje(self):
        if self.pelicula.duracion > 0:
            porcentaje = (self.timestamp / self.pelicula.duracion) * 100
            return round(porcentaje, 1)
        return 0
    
class Rating(models.Model):
    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name='calificaciones')
    pelicula = models.ForeignKey(Movie, on_delete=models.CASCADE, related_name='calificaciones')
    
    puntuacion = models.IntegerField(
        choices=[(i, f'{i} estrella{"s" if i > 1 else ""}') for i in range(1, 6)],
        help_text='Calificación de 1 a 5 estrellas'
    )
    
    resena = models.TextField(
        blank=True,
        max_length=500,
        help_text='Reseña opcional (máximo 500 caracteres)'
    )
    
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_modificacion = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Calificación"
        verbose_name_plural = "Calificaciones"
        unique_together = ['usuario', 'pelicula']
        ordering = ['-fecha_creacion']
    
    def __str__(self):
        return f"{self.usuario.username} - {self.pelicula.titulo}: {self.puntuacion}⭐"
