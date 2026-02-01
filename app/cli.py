from datetime import date, timedelta, datetime
from flask.cli import with_appcontext
import click
from .extensions import db, bcrypt
from .models import User, Organization, Location, CourseType, Student, Course, Enrollment, Session, Teacher, Attendance, AuditLog, Event, Message, Announcement


def register_cli(app):
    app.cli.add_command(seed)
    app.cli.add_command(fix_timezones)
    app.cli.add_command(create_test_admin)
    app.cli.add_command(create_test_user)


@click.command("seed")
@with_appcontext
def seed():
    if User.query.first():
        click.echo("Database already seeded.")
        return

    admin = User(
        username="admin",
        full_name="Admin Kullanıcı",
        role="admin",
        password_hash=bcrypt.generate_password_hash("Admin123!").decode("utf-8"),
        must_change_password=False
    )
    coordinator = User(
        username="coordinator",
        full_name="Koordinatör",
        role="coordinator",
        password_hash=bcrypt.generate_password_hash("Coordinator123!").decode("utf-8"),
        must_change_password=False
    )
    teacher_user = User(
        username="teacher",
        full_name="Öğretmen",
        role="teacher",
        password_hash=bcrypt.generate_password_hash("Teacher123!").decode("utf-8"),
        must_change_password=False
    )
    db.session.add_all([admin, coordinator, teacher_user])
    db.session.flush()

    teacher_profile = Teacher(
        user_id=teacher_user.id,
        full_name=teacher_user.full_name,
        title="teacher",
        branch="mathematics",
        phone="+77770000000",
        email="teacher@example.com"
    )
    db.session.add(teacher_profile)

    org = Organization(name="Eğitim Kurumu", responsible_person="Ayşe Yılmaz", phone="+77770001111", email="kurum@example.com")
    loc = Location(name="Sınıf 1A", capacity=20, has_smart_board=True)
    ctype = CourseType(name="Hazırlık", course_hours=60, delivery_mode="in_person", description="Hazırlık sınıfı")
    db.session.add_all([org, loc, ctype])
    db.session.flush()

    course = Course(
        organization_id=org.id,
        course_type_id=ctype.id,
        location_id=loc.id,
        teacher_id=teacher_profile.id,
        teacher_user_id=teacher_user.id,
        title="Hazırlık Kursu",
        start_date=date.today(),
        end_date=date.today() + timedelta(days=30),
        schedule_json={"days": ["mon", "wed", "fri"], "start_time": "09:00", "end_time": "10:30"},
        capacity=20,
        status="active",
        created_by_user_id=admin.id
    )
    db.session.add(course)
    db.session.flush()

    student = Student(full_name="Örnek Kursiyer", iin="990101123456", education_level="university", phone="+77770000000")
    db.session.add(student)
    db.session.flush()

    db.session.add(Enrollment(course_id=course.id, student_id=student.id))
    db.session.add(Session(course_id=course.id, session_date=date.today(), start_time=None, end_time=None, lesson_delivered=True))

    db.session.commit()
    click.echo("Seed completed.")


@click.command("create-test-admin")
@with_appcontext
def create_test_admin():
    existing = User.query.filter_by(username="testadmin").first()
    if existing:
        click.echo("Test admin zaten var: testadmin")
        return
    user = User(
        username="testadmin",
        full_name="Test Admin",
        role="admin",
        password_hash=bcrypt.generate_password_hash("Test123!").decode("utf-8"),
        must_change_password=False,
        is_active=True
    )
    db.session.add(user)
    db.session.commit()
    click.echo("Test admin oluşturuldu: testadmin / Test123!")


@click.command("create-test-user")
@with_appcontext
def create_test_user():
    existing = User.query.filter_by(username="test").first()
    if existing:
        click.echo("Test kullanıcı zaten var: test")
        return
    user = User(
        username="test",
        full_name="Test Kullanıcı",
        role="admin",
        password_hash=bcrypt.generate_password_hash("Test123!").decode("utf-8"),
        must_change_password=False,
        is_active=True
    )
    db.session.add(user)
    db.session.commit()
    click.echo("Test kullanıcı oluşturuldu: test / Test123!")


@click.command("fix-timezones")
@with_appcontext
def fix_timezones():
    offset = datetime.now().astimezone().utcoffset() or timedelta(0)
    if offset == timedelta(0):
        click.echo("Yerel zaman ofseti 0. Dönüşüm yapılmadı.")
        return

    models = [
        (User, ["created_at"]),
        (Student, ["created_at"]),
        (Course, ["created_at"]),
        (Enrollment, ["enrolled_at"]),
        (Session, ["created_at"]),
        (Attendance, ["marked_at"]),
        (AuditLog, ["created_at"]),
        (Event, ["created_at"]),
        (Message, ["created_at"]),
        (Announcement, ["created_at"])
    ]

    updated = 0
    for model, fields in models:
        for item in model.query.all():
            changed = False
            for field in fields:
                value = getattr(item, field, None)
                if not value:
                    continue
                setattr(item, field, value - offset)
                changed = True
            if changed:
                updated += 1
    db.session.commit()
    click.echo(f"Saat dönüşümü tamamlandı. Güncellenen kayıt: {updated}")
