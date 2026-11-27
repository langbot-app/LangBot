"""Long-lived instance identity keys used by the Harness wire protocol."""

import sqlalchemy

from .base import Base


class HarnessInstanceKey(Base):
    __tablename__ = 'harness_instance_keys'

    kid = sqlalchemy.Column(sqlalchemy.String(128), primary_key=True)
    x25519_pub = sqlalchemy.Column(sqlalchemy.Text, nullable=False)
    ed25519_pub = sqlalchemy.Column(sqlalchemy.Text, nullable=False)
    priv_ciphertext = sqlalchemy.Column(sqlalchemy.Text, nullable=False)
    status = sqlalchemy.Column(sqlalchemy.String(16), nullable=False, server_default='active')
    created_at = sqlalchemy.Column(
        sqlalchemy.DateTime(timezone=True), nullable=False, server_default=sqlalchemy.func.now()
    )
    retired_at = sqlalchemy.Column(sqlalchemy.DateTime(timezone=True), nullable=True)
    transition = sqlalchemy.Column(sqlalchemy.JSON, nullable=True)


class HarnessKeyAck(Base):
    __tablename__ = 'harness_key_acks'

    rotation_id = sqlalchemy.Column(sqlalchemy.String(36), primary_key=True)
    device_id = sqlalchemy.Column(sqlalchemy.String(36), primary_key=True)
