import datetime
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime
from app.core.database import Base


class GoogleSheetsConfig(Base):
    __tablename__ = "google_sheets_configs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(100), default="default", unique=True, index=True, nullable=False)

    # Google Spreadsheet details
    spreadsheet_id = Column(String(255), nullable=True)
    spreadsheet_url = Column(Text, nullable=True)
    worksheet_name = Column(String(255), default="EventDhara Catalog", nullable=False)

    # Authenticated Google Account Info
    connected_email = Column(String(255), nullable=True)
    connected_account_name = Column(String(255), nullable=True)
    is_connected = Column(Boolean, default=False, nullable=False)

    # Encrypted OAuth Credentials (Fernet AES)
    access_token = Column(Text, nullable=True)
    refresh_token = Column(Text, nullable=True)
    token_expiry = Column(DateTime, nullable=True)
    token_uri = Column(String(255), default="https://oauth2.googleapis.com/token", nullable=False)
    client_id = Column(String(255), nullable=True)
    client_secret = Column(String(255), nullable=True)
    scopes = Column(Text, nullable=True)

    # Synchronization state
    last_synced_at = Column(DateTime, nullable=True)
    last_sync_status = Column(String(50), nullable=True)
    last_sync_message = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False)

    def __repr__(self):
        return f"<GoogleSheetsConfig user={self.user_id} connected={self.is_connected} sheet_id={self.spreadsheet_id}>"
