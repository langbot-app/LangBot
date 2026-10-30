"""Shared, stable identities for resource URLs embedded in conversation payloads."""

import sqlalchemy as sa

from .base import Base


class ResourceURL(Base):
    __tablename__ = 'resource_urls'

    id = sa.Column(sa.String(36), primary_key=True)
    url = sa.Column(sa.Text, nullable=True)
    url_hash = sa.Column(sa.String(64), nullable=True, unique=True)
    canonical_id = sa.Column(sa.String(36), sa.ForeignKey('resource_urls.id'), nullable=True)
    created_at = sa.Column(sa.DateTime, nullable=False)
    last_checked_at = sa.Column(sa.DateTime, nullable=True)
    updated_at = sa.Column(sa.DateTime, nullable=False)

    __table_args__ = (
        sa.CheckConstraint(
            '(canonical_id IS NULL AND url IS NOT NULL AND url_hash IS NOT NULL) '
            'OR (canonical_id IS NOT NULL AND url IS NULL AND url_hash IS NULL)',
            name='ck_resource_url_canonical',
        ),
    )
