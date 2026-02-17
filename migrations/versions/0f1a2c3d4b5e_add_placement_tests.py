"""add placement test tables

Revision ID: 0f1a2c3d4b5e
Revises: 6c4e2b1a9d3f
Create Date: 2026-02-16 23:50:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0f1a2c3d4b5e"
down_revision = "6c4e2b1a9d3f"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "placement_candidates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("iin", sa.String(length=20), nullable=False),
        sa.Column("full_name", sa.String(length=120), nullable=False),
        sa.Column("phone", sa.String(length=30)),
        sa.Column("email", sa.String(length=120)),
        sa.Column("created_at", sa.DateTime(), nullable=True)
    )
    op.create_unique_constraint("uq_placement_candidates_iin", "placement_candidates", ["iin"])

    op.create_table(
        "placement_questions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("skill", sa.String(length=20), nullable=False),
        sa.Column("difficulty", sa.String(length=10), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("options_json", sa.Text(), nullable=False),
        sa.Column("correct_index", sa.Integer(), nullable=False),
        sa.Column("explanation", sa.Text()),
        sa.Column("created_at", sa.DateTime(), nullable=True)
    )

    op.create_table(
        "placement_tests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("candidate_id", sa.Integer(), sa.ForeignKey("placement_candidates.id"), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("total_questions", sa.Integer(), nullable=True),
        sa.Column("correct_count", sa.Integer(), nullable=True),
        sa.Column("score_percent", sa.Float(), nullable=True),
        sa.Column("level", sa.String(length=10)),
        sa.Column("model_used", sa.String(length=40)),
        sa.Column("mode", sa.String(length=20))
    )

    op.create_table(
        "placement_test_questions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("test_id", sa.Integer(), sa.ForeignKey("placement_tests.id"), nullable=False),
        sa.Column("question_id", sa.Integer(), sa.ForeignKey("placement_questions.id"), nullable=False),
        sa.Column("question_order", sa.Integer(), nullable=False)
    )

    op.create_table(
        "placement_answers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("test_id", sa.Integer(), sa.ForeignKey("placement_tests.id"), nullable=False),
        sa.Column("question_id", sa.Integer(), sa.ForeignKey("placement_questions.id"), nullable=False),
        sa.Column("selected_index", sa.Integer()),
        sa.Column("is_correct", sa.Boolean(), nullable=True)
    )


def downgrade():
    op.drop_table("placement_answers")
    op.drop_table("placement_test_questions")
    op.drop_table("placement_tests")
    op.drop_table("placement_questions")
    op.drop_table("placement_candidates")
