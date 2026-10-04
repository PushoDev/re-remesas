from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import AdminUserCreationForm, UserChangeForm

from .models import Profile, User


class UserCreationForm(AdminUserCreationForm):
    # Crear usuarios por email; `username` se rellena con el email.

    class Meta(AdminUserCreationForm.Meta):
        model = User
        fields = ('email',)

    def save(self, commit=True):
        self.instance.username = self.cleaned_data['email'].strip().lower()
        return super().save(commit=commit)


class UserEditForm(UserChangeForm):
    class Meta(UserChangeForm.Meta):
        model = User


class ProfileInline(admin.StackedInline):
    model = Profile
    can_delete = False
    extra = 0
    fields = ('is_membership_active', 'membership_expires_at', 'membership_status', 'created_at')
    readonly_fields = ('membership_status', 'created_at')

    @admin.display(description='Estado de membresía')
    def membership_status(self, obj):
        return obj.membership_status if obj.pk else '-'


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    form = UserEditForm
    add_form = UserCreationForm
    inlines = [ProfileInline]

    list_display = ('email', 'first_name', 'last_name', 'is_staff', 'is_active', 'membership')
    list_filter = ('is_staff', 'is_active', 'profile__is_membership_active')
    search_fields = ('email', 'first_name', 'last_name')
    ordering = ('email',)
    list_select_related = ('profile',)
    readonly_fields = ('last_login', 'date_joined')

    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Datos personales', {'fields': ('first_name', 'last_name')}),
        ('Permisos', {'fields': (
            'is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions',
        )}),
        ('Fechas', {'fields': ('last_login', 'date_joined')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'usable_password', 'password1', 'password2'),
        }),
    )

    @admin.display(description='Membresía')
    def membership(self, obj):
        return obj.profile.membership_status

    def get_inline_instances(self, request, obj=None):
        # Al crear un usuario, el perfil se crea mediante el signal `post_save`;
        # mostrar el inline aquí intentaría crear un segundo.
        return super().get_inline_instances(request, obj) if obj else []

    def save_model(self, request, obj, form, change):
        obj.username = obj.email.strip().lower()  # keep username == email
        super().save_model(request, obj, form, change)
