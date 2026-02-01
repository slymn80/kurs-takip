from flask_wtf import FlaskForm
from flask_wtf.file import FileField
from wtforms import StringField, PasswordField, SubmitField, SelectField, TextAreaField, DateField, IntegerField, BooleanField, TimeField
from wtforms.validators import DataRequired, Length, Optional, Email


class LoginForm(FlaskForm):
    username = StringField("Kullanıcı Adı", validators=[DataRequired(), Length(max=80)])
    password = PasswordField("Şifre", validators=[DataRequired()])
    submit = SubmitField("Giriş")


class ChangePasswordForm(FlaskForm):
    password = PasswordField("Yeni Şifre", validators=[DataRequired(), Length(min=8)])
    submit = SubmitField("Kaydet")


class PasswordUpdateForm(FlaskForm):
    current_password = PasswordField("Mevcut Şifre", validators=[DataRequired()])
    new_password = PasswordField("Yeni Şifre", validators=[DataRequired(), Length(min=8)])
    confirm_password = PasswordField("Yeni Şifre (Tekrar)", validators=[DataRequired(), Length(min=8)])
    submit = SubmitField("Şifreyi Güncelle")


class OrganizationForm(FlaskForm):
    name = StringField("Kurum Adı", validators=[DataRequired(), Length(max=120)])
    responsible_person = StringField("Sorumlu Personel", validators=[DataRequired(), Length(max=120)])
    phone = StringField("Telefon", validators=[DataRequired(), Length(max=30)])
    email = StringField("E-posta", validators=[DataRequired(), Email(), Length(max=120)])
    address = StringField("Adres", validators=[Optional(), Length(max=200)])
    notes = TextAreaField("Not")
    submit = SubmitField("Kaydet")


class LocationForm(FlaskForm):
    name = StringField("Yer Adı", validators=[DataRequired(), Length(max=120)])
    address = StringField("Adres", validators=[Optional(), Length(max=200)])
    capacity = IntegerField("Kapasite", validators=[Optional()])
    has_smart_board = BooleanField("Akıllı Tahta")
    notes = TextAreaField("Not")
    submit = SubmitField("Kaydet")


class CourseTypeForm(FlaskForm):
    name = StringField("Kurs Tipi", validators=[DataRequired(), Length(max=120)])
    course_hours = IntegerField("Kurs Saati", validators=[DataRequired()])
    delivery_mode = SelectField(
        "Öğretim Şekli",
        choices=[
            ("in_person", "Yüz yüze"),
            ("remote", "Uzaktan"),
            ("hybrid", "Hibrit")
        ],
        validators=[DataRequired()]
    )
    description = TextAreaField("Açıklama")
    submit = SubmitField("Kaydet")


class TeacherForm(FlaskForm):
    full_name = StringField("Ad Soyad", validators=[DataRequired(), Length(max=120)])
    title = SelectField(
        "Öğretmen / Akademisyen",
        choices=[("teacher", "Öğretmen"), ("academician", "Akademisyen")],
        validators=[DataRequired()]
    )
    branch = SelectField(
        "Branş",
        choices=[
            ("turkish", "Türkçe"),
            ("english", "İngilizce"),
            ("kazakh", "Kazakça"),
            ("russian", "Rusça"),
            ("mathematics", "Matematik"),
            ("it", "Bilişim Teknolojileri"),
            ("music", "Müzik"),
            ("other", "Diğer")
        ],
        validators=[DataRequired()]
    )
    phone = StringField("Telefon", validators=[DataRequired(), Length(max=30)])
    email = StringField("E-posta", validators=[DataRequired(), Email(), Length(max=120)])
    user_id = SelectField("Kullanıcı (opsiyonel)", coerce=int)
    notes = TextAreaField("Not")
    submit = SubmitField("Kaydet")


class StudentForm(FlaskForm):
    full_name = StringField("Ad Soyad", validators=[DataRequired(), Length(max=120)])
    iin = StringField("IIN", validators=[DataRequired(), Length(max=20)])
    education_level = SelectField(
        "Eğitim Durumu",
        choices=[
            ("primary", "İlkokul"),
            ("middle", "Ortaokul"),
            ("high", "Lise"),
            ("university", "Üniversite"),
            ("other", "Diğer")
        ],
        validators=[DataRequired()]
    )
    course_id = SelectField("Kursa Kaydet (opsiyonel)", coerce=int)
    phone = StringField("Telefon", validators=[Optional(), Length(max=30)])
    email = StringField("E-posta", validators=[Optional(), Email(), Length(max=120)])
    photo = FileField("Öğrenci Fotoğrafı")
    id_image = FileField("Kimlik Görseli")
    notes = TextAreaField("Not")
    submit = SubmitField("Kaydet")


class CourseForm(FlaskForm):
    organization_id = SelectField("Kurum", coerce=int)
    course_type_id = SelectField("Kurs Tipi", coerce=int)
    location_id = SelectField("Yer", coerce=int)
    teacher_id = SelectField("Öğretmen", coerce=int)
    title = StringField("Başlık", validators=[DataRequired(), Length(max=200)])
    term = SelectField(
        "Dönem",
        choices=[("fall", "Güz Dönemi"), ("spring", "Bahar Dönemi")],
        validators=[DataRequired()]
    )
    start_date = DateField("Başlangıç", validators=[DataRequired()])
    end_date = DateField("Bitiş", validators=[DataRequired()])
    capacity = IntegerField("Kapasite", validators=[Optional()])
    schedule_days = SelectField("Günler", choices=[("mon","Pzt"),("tue","Sal"),("wed","Çar"),("thu","Per"),("fri","Cum"),("sat","Cmt"),("sun","Paz")])
    start_time = TimeField("Başlangıç Saati", validators=[Optional()])
    end_time = TimeField("Bitiş Saati", validators=[Optional()])
    description = TextAreaField("Açıklama")
    submit = SubmitField("Kaydet")


class SessionForm(FlaskForm):
    session_date = DateField("Tarih", validators=[DataRequired()])
    start_time = TimeField("Başlangıç Saati", validators=[Optional()])
    end_time = TimeField("Bitiş Saati", validators=[Optional()])
    topic = StringField("Konu", validators=[Optional(), Length(max=200)])
    submit = SubmitField("Kaydet")


class UserForm(FlaskForm):
    username = StringField("Kullanıcı Adı", validators=[DataRequired(), Length(max=80)])
    full_name = StringField("Ad Soyad", validators=[DataRequired(), Length(max=120)])
    phone = StringField("Telefon", validators=[Optional(), Length(max=30)])
    email = StringField("E-posta", validators=[Optional(), Email(), Length(max=120)])
    role = SelectField("Rol", choices=[("teacher","Teacher"),("coordinator","Coordinator"),("principal","Principal"),("attache","Attache"),("admin","Admin")])
    is_active = BooleanField("Aktif")
    submit = SubmitField("Kaydet")

