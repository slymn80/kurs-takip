from datetime import date, timedelta, datetime
from flask.cli import with_appcontext
import click
from .extensions import db, bcrypt
from .models import User, Organization, Location, CourseType, Student, Course, Enrollment, Session, Teacher, Attendance, AuditLog, Event, Message, Announcement, ApiToken, PlacementQuestion
from .security import hash_api_token
from .services.placement import create_question_group
import secrets


def register_cli(app):
    app.cli.add_command(seed)
    app.cli.add_command(fix_timezones)
    app.cli.add_command(create_test_admin)
    app.cli.add_command(create_test_user)
    app.cli.add_command(seed_demo)
    app.cli.add_command(create_api_token)
    app.cli.add_command(placement_refresh_pool)


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


@click.command("seed-demo")
@with_appcontext
def seed_demo():
    admin = User.query.filter_by(username="admin").first()
    if not admin:
        admin = User(
            username="admin",
            full_name="Admin Kullanıcı",
            role="admin",
            password_hash=bcrypt.generate_password_hash("Admin123!").decode("utf-8"),
            must_change_password=False,
            is_active=True
        )
        db.session.add(admin)
        db.session.flush()

    teacher_users = []
    for idx in range(1, 4):
        username = f"teacher{idx}"
        user = User.query.filter_by(username=username).first()
        if not user:
            user = User(
                username=username,
                full_name=f"Öğretmen {idx}",
                role="teacher",
                password_hash=bcrypt.generate_password_hash(f"Teacher{idx}123!").decode("utf-8"),
                must_change_password=False,
                is_active=True
            )
            db.session.add(user)
            db.session.flush()
        teacher_users.append(user)

    teachers = []
    for idx, user in enumerate(teacher_users, start=1):
        existing = Teacher.query.filter_by(user_id=user.id).first()
        if not existing:
            existing = Teacher(
                user_id=user.id,
                full_name=user.full_name,
                title="teacher",
                branch="mathematics",
                phone=f"+7777000000{idx}",
                email=f"teacher{idx}@example.com"
            )
            db.session.add(existing)
        teachers.append(existing)

    organizations = []
    for idx in range(1, 4):
        name = f"Kurum {idx}"
        org = Organization.query.filter_by(name=name).first()
        if not org:
            org = Organization(
                name=name,
                responsible_person=f"Sorumlu {idx}",
                phone=f"+7777111000{idx}",
                email=f"kurum{idx}@example.com"
            )
            db.session.add(org)
        organizations.append(org)

    locations = []
    for idx in range(1, 4):
        name = f"Yer {idx}"
        loc = Location.query.filter_by(name=name).first()
        if not loc:
            loc = Location(
                name=name,
                capacity=20 + idx,
                has_smart_board=bool(idx % 2)
            )
            db.session.add(loc)
        locations.append(loc)

    course_types = []
    for idx in range(1, 4):
        name = f"Kurs Tipi {idx}"
        ct = CourseType.query.filter_by(name=name).first()
        if not ct:
            ct = CourseType(
                name=name,
                course_hours=40 + idx * 10,
                delivery_mode="in_person",
                description=f"Kurs tipi açıklaması {idx}"
            )
            db.session.add(ct)
        course_types.append(ct)

    students = []
    for idx in range(1, 4):
        name = f"Kursiyer {idx}"
        student = Student.query.filter_by(full_name=name).first()
        if not student:
            student = Student(
                full_name=name,
                iin=f"99010112345{idx}",
                education_level="university",
                phone=f"+7777222000{idx}",
                email=f"student{idx}@example.com"
            )
            db.session.add(student)
        students.append(student)

    db.session.flush()

    courses = []
    for idx in range(1, 4):
        title = f"Deneme Kursu {idx}"
        course = Course.query.filter_by(title=title).first()
        if not course:
            course = Course(
                organization_id=organizations[idx - 1].id,
                course_type_id=course_types[idx - 1].id,
                location_id=locations[idx - 1].id,
                teacher_id=teachers[idx - 1].id,
                teacher_user_id=teachers[idx - 1].user_id,
                title=title,
                start_date=date.today(),
                end_date=date.today() + timedelta(days=45),
                schedule_json={"days": ["mon", "wed"], "start_time": "10:00", "end_time": "11:30"},
                capacity=20,
                status="active",
                created_by_user_id=admin.id
            )
            db.session.add(course)
        courses.append(course)

    db.session.flush()

    for idx, course in enumerate(courses, start=1):
        for s_idx in range(1, 4):
            session_date = date.today() + timedelta(days=s_idx * 7)
            existing = Session.query.filter_by(course_id=course.id, session_date=session_date).first()
            if not existing:
                db.session.add(Session(course_id=course.id, session_date=session_date, lesson_delivered=True))

        student = students[idx - 1]
        existing_enrollment = Enrollment.query.filter_by(course_id=course.id, student_id=student.id).first()
        if not existing_enrollment:
            db.session.add(Enrollment(course_id=course.id, student_id=student.id))

    db.session.commit()
    click.echo("Demo veri oluşturuldu: her tablodan en az 3 kayıt.")


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


@click.command("create-api-token")
@click.option("--username", required=True, help="Token oluşturulacak kullanıcı adı")
@click.option("--name", default="default", help="Token adı/etiketi")
@with_appcontext
def create_api_token(username, name):
    user = User.query.filter_by(username=username).first()
    if not user:
        click.echo("Kullanıcı bulunamadı.")
        return
    raw_token = secrets.token_urlsafe(32)
    token = ApiToken(
        user_id=user.id,
        name=name,
        token_hash=hash_api_token(raw_token),
        is_active=True
    )
    db.session.add(token)
    db.session.commit()
    click.echo(f"API token oluşturuldu ({username}). Bu token sadece bir kez gösterilir:")
    click.echo(raw_token)


@click.command("placement-refresh-pool")
@click.option("--count", default=30, type=int, show_default=True, help="Aktif soru sayısı")
@click.option("--auto-approve", is_flag=True, help="Soruları otomatik onayla")
@with_appcontext
def placement_refresh_pool(count, auto_approve):
    PlacementQuestion.query.update({
        PlacementQuestion.is_active: False,
        PlacementQuestion.is_approved: False
    })
    db.session.commit()
    create_question_group(count=count)
    if auto_approve:
        PlacementQuestion.query.filter_by(is_active=True).update({PlacementQuestion.is_approved: True})
        db.session.commit()
        click.echo(f"Seviye sınavı soru havuzu yenilendi ve onaylandı. Aktif soru sayısı: {count}")
    else:
        click.echo(f"Seviye sınavı soru havuzu yenilendi. Onay bekliyor. Aktif soru sayısı: {count}")


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
