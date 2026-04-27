CREATE TABLE IF NOT EXISTS meeting_minutes_templates (
  id INT PRIMARY KEY AUTO_INCREMENT,
  user_id VARCHAR(50) NOT NULL,
  name VARCHAR(120) NOT NULL,
  content MEDIUMTEXT NOT NULL,
  is_default TINYINT(1) NOT NULL DEFAULT 0,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

CREATE INDEX idx_minutes_templates_user_updated
  ON meeting_minutes_templates(user_id, updated_at);
