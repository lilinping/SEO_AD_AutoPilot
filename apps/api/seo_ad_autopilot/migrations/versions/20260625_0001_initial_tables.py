"""Create initial tables: analysis_tasks, ranking_snapshots, content_versions, debate_logs.

Revision ID: 0001_initial
Revises:
Create Date: 2026-06-25
"""
from __future__ import annotations
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # analysis_tasks — DB-005
    op.create_table(
        "analysis_tasks",
        sa.Column("id",          sa.String(36),  primary_key=True),
        sa.Column("url",         sa.Text(),       nullable=False),
        sa.Column("status",      sa.String(20),   nullable=False, default="queued"),
        sa.Column("percent",     sa.Integer(),    nullable=False, default=0),
        sa.Column("agent_filter", sa.JSON(),      nullable=True),
        sa.Column("dry_run",     sa.Boolean(),    nullable=False, default=False),
        sa.Column("locale",      sa.String(10),   nullable=False, default="en"),
        sa.Column("result",      sa.JSON(),       nullable=True),
        sa.Column("error",       sa.Text(),       nullable=True),
        sa.Column("tenant_id",   sa.String(36),   nullable=True, index=True),
        sa.Column("created_at",  sa.Float(),      nullable=False),
        sa.Column("updated_at",  sa.Float(),      nullable=True),
    )

    # ranking_snapshots — DB-003
    op.create_table(
        "ranking_snapshots",
        sa.Column("id",            sa.String(36), primary_key=True),
        sa.Column("url",           sa.Text(),     nullable=False),
        sa.Column("keyword",       sa.Text(),     nullable=False),
        sa.Column("position",      sa.Integer(),  nullable=True),
        sa.Column("search_engine", sa.String(20), nullable=False, default="google"),
        sa.Column("locale",        sa.String(10), nullable=False, default="en"),
        sa.Column("device",        sa.String(10), nullable=False, default="desktop"),
        sa.Column("serp_features", sa.JSON(),     nullable=True),
        sa.Column("tenant_id",     sa.String(36), nullable=True, index=True),
        sa.Column("snapshot_date", sa.String(10), nullable=False),   # YYYY-MM-DD
        sa.Column("created_at",    sa.Float(),    nullable=False),
    )
    op.create_index("ix_ranking_url_keyword_date", "ranking_snapshots",
                    ["url", "keyword", "snapshot_date"])

    # content_versions — DB-004
    op.create_table(
        "content_versions",
        sa.Column("version_id",   sa.String(36), primary_key=True),
        sa.Column("content_id",   sa.String(255),nullable=False, index=True),
        sa.Column("version",      sa.String(20), nullable=False),
        sa.Column("content_json", sa.JSON(),     nullable=False),
        sa.Column("author",       sa.String(100),nullable=False, default="agent"),
        sa.Column("change_note",  sa.Text(),     nullable=True),
        sa.Column("metadata_json",sa.JSON(),     nullable=True),
        sa.Column("is_active",    sa.Boolean(),  nullable=False, default=True),
        sa.Column("tenant_id",    sa.String(36), nullable=True, index=True),
        sa.Column("created_at",   sa.Float(),    nullable=False),
    )

    # debate_logs — DB-007
    op.create_table(
        "debate_logs",
        sa.Column("id",            sa.String(36), primary_key=True),
        sa.Column("task_id",       sa.String(36), nullable=True, index=True),
        sa.Column("topic",         sa.Text(),     nullable=False),
        sa.Column("proposer_role", sa.String(50), nullable=False),
        sa.Column("participants",  sa.JSON(),     nullable=True),
        sa.Column("rounds",        sa.JSON(),     nullable=True),
        sa.Column("consensus_score",sa.Float(),   nullable=True),
        sa.Column("resolution",    sa.Text(),     nullable=True),
        sa.Column("tenant_id",     sa.String(36), nullable=True, index=True),
        sa.Column("created_at",    sa.Float(),    nullable=False),
    )

    # ad_recommendations — DB-006
    op.create_table(
        "ad_recommendations",
        sa.Column("id",            sa.String(36), primary_key=True),
        sa.Column("url",           sa.Text(),     nullable=False),
        sa.Column("platforms",     sa.JSON(),     nullable=False),
        sa.Column("site_data",     sa.JSON(),     nullable=True),
        sa.Column("tenant_id",     sa.String(36), nullable=True, index=True),
        sa.Column("created_at",    sa.Float(),    nullable=False),
    )


def downgrade() -> None:
    op.drop_table("ad_recommendations")
    op.drop_table("debate_logs")
    op.drop_table("content_versions")
    op.drop_index("ix_ranking_url_keyword_date", "ranking_snapshots")
    op.drop_table("ranking_snapshots")
    op.drop_table("analysis_tasks")
