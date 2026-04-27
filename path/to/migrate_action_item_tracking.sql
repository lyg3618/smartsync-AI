-- 检查并只在不存在时添加列
SET @col_exists = 0;
SELECT COUNT(*) INTO @col_exists 
FROM INFORMATION_SCHEMA.COLUMNS 
WHERE TABLE_SCHEMA = DATABASE() 
AND TABLE_NAME = 'action_items' 
AND COLUMN_NAME = 'progress_note';

SET @sql = IF(@col_exists = 0, 
    'ALTER TABLE action_items ADD COLUMN progress_note TEXT NULL',
    'SELECT "Column already exists" as message');

PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;