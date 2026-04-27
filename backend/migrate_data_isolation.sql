-- migrate_data_isolation.sql
-- 请在您的数据库工具（如 Navicat、DataGrip 或 mysql 命令行）中执行以下脚本

-- 1. 为 meetings 表新增 user_id 列，并分配默认归属
ALTER TABLE meetings ADD COLUMN user_id VARCHAR(50);
UPDATE meetings SET user_id = 'admin' WHERE user_id IS NULL;

-- 2. 为 contacts 表新增 user_id 列，并分配默认归属
ALTER TABLE contacts ADD COLUMN user_id VARCHAR(50);
UPDATE contacts SET user_id = 'admin' WHERE user_id IS NULL;

-- 3. 升级 contacts 表使其具备系统账号登录能力
ALTER TABLE contacts ADD COLUMN username VARCHAR(50) UNIQUE;
ALTER TABLE contacts ADD COLUMN hashed_password VARCHAR(255);
ALTER TABLE contacts ADD COLUMN role VARCHAR(20) DEFAULT 'user';

-- 为已有的测试数据设定 username 和默认密码 '123456' ($2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjIQG8INfO)
UPDATE contacts SET username = 'admin', role = 'admin', hashed_password = '$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjIQG8INfO' WHERE name = '管理员';
UPDATE contacts SET username = 'zhang', role = 'user',  hashed_password = '$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjIQG8INfO' WHERE name = '张伟';
UPDATE contacts SET username = 'li',    role = 'user',  hashed_password = '$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjIQG8INfO' WHERE name = '李娜';
UPDATE contacts SET username = 'wang',  role = 'user',  hashed_password = '$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjIQG8INfO' WHERE name = '王芳';
