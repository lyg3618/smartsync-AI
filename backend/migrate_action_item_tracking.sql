ALTER TABLE action_items MODIFY COLUMN status ENUM('pending','in_progress','done') NOT NULL DEFAULT 'pending';

ALTER TABLE action_items ADD COLUMN is_viewed TINYINT(1) NOT NULL DEFAULT 0;
ALTER TABLE action_items ADD COLUMN viewed_at DATETIME NULL;
ALTER TABLE action_items ADD COLUMN completed_at DATETIME NULL;
ALTER TABLE action_items ADD COLUMN progress_note TEXT NULL;
