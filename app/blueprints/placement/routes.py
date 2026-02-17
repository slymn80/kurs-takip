from datetime import datetime
import json
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import current_user
from ...extensions import db
from ...models import (
    PlacementCandidate,
    PlacementTest,
    PlacementQuestion,
    PlacementTestQuestion,
    PlacementAnswer
)
from ...services.placement import pick_questions, score_to_level, SKILL_LABELS, _openai_model, DIFFICULTY_WEIGHT


placement_bp = Blueprint("placement", __name__)


@placement_bp.route("/placement", methods=["GET", "POST"])
def landing():
    iin = (request.form.get("iin") or request.args.get("iin") or "").strip()
    candidate = PlacementCandidate.query.filter_by(iin=iin).first() if iin else None
    tests = []
    if candidate:
        tests = PlacementTest.query.filter_by(candidate_id=candidate.id).order_by(PlacementTest.started_at.desc()).all()

    if request.method == "POST":
        full_name = (request.form.get("full_name") or "").strip()
        phone = (request.form.get("phone") or "").strip()
        email = (request.form.get("email") or "").strip()
        if not iin or not full_name:
            flash("IIN ve Ad Soyad zorunludur.", "error")
            return render_template("placement/landing.html", candidate=candidate, tests=tests, iin=iin)
        if not candidate:
            candidate = PlacementCandidate(iin=iin, full_name=full_name, phone=phone, email=email)
            db.session.add(candidate)
            db.session.commit()
        else:
            candidate.full_name = full_name
            candidate.phone = phone
            candidate.email = email
            db.session.add(candidate)
            db.session.commit()
        return redirect(url_for("placement.start_test", candidate_id=candidate.id))

    return render_template("placement/landing.html", candidate=candidate, tests=tests, iin=iin)


@placement_bp.route("/placement/start/<int:candidate_id>", methods=["GET", "POST"])
def start_test(candidate_id):
    candidate = PlacementCandidate.query.get_or_404(candidate_id)
    if request.method == "POST":
        try:
            questions = pick_questions(count=30)
        except Exception as exc:
            db.session.rollback()
            flash(f"Soru havuzu oluşturulamadı: {exc}", "error")
            return render_template("placement/start.html", candidate=candidate), 400
        test = PlacementTest(
            candidate_id=candidate.id,
            started_at=datetime.utcnow(),
            model_used=_openai_model(),
            mode="pool"
        )
        db.session.add(test)
        db.session.flush()
        for idx, q in enumerate(questions, start=1):
            db.session.add(PlacementTestQuestion(
                test_id=test.id,
                question_id=q.id,
                question_order=idx
            ))
        db.session.commit()
        return redirect(url_for("placement.take_test", test_id=test.id))
    return render_template("placement/start.html", candidate=candidate)


@placement_bp.route("/placement/test/<int:test_id>", methods=["GET", "POST"])
def take_test(test_id):
    test = PlacementTest.query.get_or_404(test_id)
    if test.completed_at:
        return redirect(url_for("placement.result", test_id=test.id))

    rows = (
        db.session.query(PlacementTestQuestion, PlacementQuestion)
        .join(PlacementQuestion, PlacementQuestion.id == PlacementTestQuestion.question_id)
        .filter(PlacementTestQuestion.test_id == test.id)
        .order_by(PlacementTestQuestion.question_order.asc())
        .all()
    )

    if request.method == "POST":
        correct = 0
        total = len(rows)
        weighted_correct = 0.0
        weighted_total = 0.0
        for link, question in rows:
            selected = request.form.get(f"q_{question.id}")
            selected_index = int(selected) if selected is not None and selected.isdigit() else None
            is_correct = selected_index == question.correct_index
            weight = DIFFICULTY_WEIGHT.get(question.difficulty, 1.0)
            weighted_total += weight
            if is_correct:
                correct += 1
                weighted_correct += weight
            db.session.add(PlacementAnswer(
                test_id=test.id,
                question_id=question.id,
                selected_index=selected_index,
                is_correct=is_correct
            ))
        score_percent = round((weighted_correct / weighted_total) * 100, 2) if weighted_total else 0
        test.correct_count = correct
        test.total_questions = total
        test.score_percent = score_percent
        test.level = score_to_level(score_percent)
        test.completed_at = datetime.utcnow()
        db.session.add(test)
        db.session.commit()
        return redirect(url_for("placement.result", test_id=test.id))

    questions = []
    for link, question in rows:
        questions.append({
            "id": question.id,
            "order": link.question_order,
            "skill": SKILL_LABELS.get(question.skill, question.skill),
            "difficulty": question.difficulty,
            "prompt": question.prompt,
            "options": json.loads(question.options_json)
        })
    return render_template("placement/test.html", test=test, questions=questions)


@placement_bp.route("/placement/result/<int:test_id>")
def result(test_id):
    test = PlacementTest.query.get_or_404(test_id)
    candidate = PlacementCandidate.query.get_or_404(test.candidate_id)
    answers = PlacementAnswer.query.filter_by(test_id=test.id).all()
    total = test.total_questions or 0
    correct = test.correct_count or 0
    return render_template(
        "placement/result.html",
        test=test,
        candidate=candidate,
        total=total,
        correct=correct
    )
