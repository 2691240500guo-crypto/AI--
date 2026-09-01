-- 人才档案域菜单种子（幂等，参照 hy 分支 scripts/hq_add_talent_menu.py 规格）
-- 1) AI 智能档案 父菜单
INSERT INTO sys_menu (parent_id, title, icon, path, component, perm, type, sort, status, created_at)
SELECT 0, 'AI 智能档案', NULL, '/talent', 'talent/List', 'talent:list', 2, 10, 1, NOW()
WHERE NOT EXISTS (SELECT 1 FROM sys_menu WHERE title = 'AI 智能档案');

-- 2) 三个子菜单
INSERT INTO sys_menu (parent_id, title, icon, path, component, perm, type, sort, status, created_at)
SELECT m.id, '人才档案管理', NULL, '/talent/list', 'talent/List', 'talent:list', 2, 1, 1, NOW()
FROM sys_menu m WHERE m.title = 'AI 智能档案'
AND NOT EXISTS (SELECT 1 FROM sys_menu WHERE title = '人才档案管理');

INSERT INTO sys_menu (parent_id, title, icon, path, component, perm, type, sort, status, created_at)
SELECT m.id, '简历智能解析', NULL, '/talent/upload', 'talent/ResumeImport', 'talent:parse', 2, 2, 1, NOW()
FROM sys_menu m WHERE m.title = 'AI 智能档案'
AND NOT EXISTS (SELECT 1 FROM sys_menu WHERE title = '简历智能解析');

INSERT INTO sys_menu (parent_id, title, icon, path, component, perm, type, sort, status, created_at)
SELECT m.id, '标签管理', NULL, '/talent/tags', 'talent/tags', 'talent:tag', 2, 3, 1, NOW()
FROM sys_menu m WHERE m.title = 'AI 智能档案'
AND NOT EXISTS (SELECT 1 FROM sys_menu WHERE title = '标签管理');

-- 3) 给超管角色挂权限（幂等）
INSERT INTO sys_role_menu (role_id, menu_id)
SELECT r.id, m.id FROM sys_role r, sys_menu m
WHERE r.code = 'admin' AND m.title IN ('AI 智能档案', '人才档案管理', '简历智能解析', '标签管理')
AND NOT EXISTS (
    SELECT 1 FROM sys_role_menu rm
    WHERE rm.role_id = r.id AND rm.menu_id = m.id
);
