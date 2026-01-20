from django.contrib.auth.forms import UserCreationForm, AuthenticationForm, PasswordResetForm, SetPasswordForm
from django.contrib.auth.models import User
from django import forms
from django_recaptcha.fields import ReCaptchaField
from django_recaptcha.widgets import ReCaptchaV2Checkbox   # type: ignore
from django.core.exceptions import ValidationError as DjangoValidationError
import re


def validate_email_domain(email):
    """Valida que el email tenga un dominio conocido válido."""
    dominios_permitidos = {
        'gmail.com', 'hotmail.com', 'outlook.com', 'yahoo.com', 'mail.com',
        'protonmail.com', 'icloud.com', 'aol.com', 'zoho.com', 'yandex.com',
        'tutanota.com', 'fastmail.com', 'mailbox.org', 'mailfence.com',
        'telefonica.es', 'terra.es', 'hispavista.es', 'wanadoo.es',
    }
    
    patron_email = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(patron_email, email):
        raise DjangoValidationError('Por favor ingresa una dirección de correo válida.')
    
    dominio = email.split('@')[1].lower()
    
    if dominio not in dominios_permitidos:
        raise DjangoValidationError(
            f'El dominio de correo "{dominio}" no está permitido. '
            f'Por favor usa un proveedor de correo conocido (Gmail, Outlook, Yahoo, etc.)'
        )


class CustomPasswordResetForm(PasswordResetForm):
    """Formulario personalizado para solicitar recuperación de contraseña."""
    email = forms.EmailField(
        max_length=254,
        label='Correo Electrónico',
        widget=forms.EmailInput(attrs={
            'class': 'w-full px-4 py-3 bg-black border-2 border-gray-600 text-white text-base rounded-lg focus:outline-none focus:border-netflix-red focus:ring-2 focus:ring-netflix-red transition placeholder-gray-500',
            'placeholder': 'Ingresa tu correo electrónico'
        })
    )
    
    def clean_email(self):
        email = self.cleaned_data['email']
        if not User.objects.filter(email=email).exists():
            raise forms.ValidationError(
                'No existe una cuenta con este correo electrónico.',
                code='invalid_email'
            )
        return email


class CustomSetPasswordForm(SetPasswordForm):
    """Formulario personalizado para cambiar contraseña."""
    new_password1 = forms.CharField(
        label="Nueva contraseña",
        widget=forms.PasswordInput(attrs={
            'class': 'w-full px-4 py-3 bg-black border-2 border-gray-600 text-white text-base rounded-lg focus:outline-none focus:border-netflix-red focus:ring-2 focus:ring-netflix-red transition placeholder-gray-500',
            'placeholder': 'Nueva contraseña',
            'autocomplete': 'new-password'
        })
    )
    new_password2 = forms.CharField(
        label="Confirmar nueva contraseña",
        widget=forms.PasswordInput(attrs={
            'class': 'w-full px-4 py-3 bg-black border-2 border-gray-600 text-white text-base rounded-lg focus:outline-none focus:border-netflix-red focus:ring-2 focus:ring-netflix-red transition placeholder-gray-500',
            'placeholder': 'Confirmar contraseña',
            'autocomplete': 'new-password'
        })
    )
    
    def clean_new_password2(self):
        password1 = self.cleaned_data.get('new_password1')
        password2 = self.cleaned_data.get('new_password2')
        if password1 and password2 and password1 != password2:
            raise forms.ValidationError('Las contraseñas no coinciden.')
        return password2
    
    def save(self, commit=True):
        """Guarda la nueva contraseña del usuario."""
        user = self.user
        user.set_password(self.cleaned_data['new_password1'])
        if commit:
            user.save()
        return user


class CustomAuthenticationForm(AuthenticationForm):
    captcha = ReCaptchaField(widget=ReCaptchaV2Checkbox)
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].label = 'Usuario'
        self.fields['password'].label = 'Contraseña'
    
    def confirm_login_allowed(self, user):
        if not user.is_active:
            raise forms.ValidationError(
                'Esta cuenta está inactiva. Por favor, revisa tu correo para el enlace de activación.',
                code='inactive',
            )
        
    def get_invalid_login_error(self):
        return forms.ValidationError(
            'Usuario o contraseña incorrectos.',
            code='invalid_login',
        )

class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField(
        required=True,
        help_text='Se enviará un correo de verificación a esta dirección.',
        validators=[validate_email_domain]
    )
    captcha = ReCaptchaField(widget=ReCaptchaV2Checkbox)

    class Meta(UserCreationForm.Meta): # type: ignore
        model = User
        fields = ('username', 'email')

    def __init__(self, *args, **kwargs):
        super(CustomUserCreationForm, self).__init__(*args, **kwargs)
        self.fields['username'].label = 'Usuario'
        self.fields['username'].help_text = None # type: ignore
        self.fields['email'].label = 'Correo Electrónico'
        self.fields['password1'].label = 'Contraseña'
        self.fields['password2'].label = 'Confirmar Contraseña'
        self.fields['password2'].help_text = 'Introduce la misma contraseña de antes, para verificar.'
        self.fields['password1'].help_text = (
            '<ul class="list-disc list-inside text-sm">'
            '<li>Debe contener al menos 8 caracteres.</li>'
            '<li>No puede ser una contraseña común.</li>'
            '<li>No puede ser completamente numérica.</li>'
            '</ul>'
        )
        
        self.fields['username'].error_messages = {
            'unique': 'Este nombre de usuario ya está en uso.',
        }
        self.fields['email'].error_messages = {}

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError('Este correo electrónico ya está en uso.')
        return email
    
    def clean_password2(self):
        password1 = self.cleaned_data.get('password1')
        password2 = self.cleaned_data.get('password2')
        if password1 and password2 and password1 != password2:
            raise forms.ValidationError('Las contraseñas no coinciden.')
        return password2

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.is_active = False
        if commit:
            user.save()
        return user
