ALTER TABLE meetings
  ADD COLUMN is_deleted TINYINT(1) NOT NULL DEFAULT 0,
  ADD COLUMN deleted_at DATETIME NULL;

CREATE INDEX idx_meetings_user_deleted_date ON meetings(user_id, is_deleted, date);
