ALTER TABLE action_items
  ADD COLUMN updated_after_dispatch TINYINT(1) NOT NULL DEFAULT 0,
  ADD COLUMN last_dispatched_at DATETIME NULL;

CREATE INDEX idx_action_items_meeting_updated
  ON action_items(meeting_id, updated_after_dispatch);
